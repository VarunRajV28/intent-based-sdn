# orchestrator/store.py
# Owner: Varun
# Purpose: Process-safe JSON file wrapper for the shared intent store (section 4.4).
#
# File: shared/store.json
#   {
#     "intents":   [ {id, text, action, src, dst, status, subpolicies:[...]}, ... ],
#     "ownership": { "1": "c1", ..., "6": "c3" },   # dpid (as string) -> controller id
#     "event_log": [ {time, type, ...}, ... ],
#     "next_id":   N                                # next intent id (never re-used)
#   }
#
# Locking: the orchestrator CLI and Karthik's monitor.py are separate processes that
# both write this file. Every public function takes an exclusive lock on
# "store.json.lock" (msvcrt on Windows, fcntl on Linux/macOS - both standard library),
# reads the JSON, changes it, and writes it back atomically (temp file + os.replace).
#
# Public functions (section 4.4):
#   add_intent, remove_intent, list_intents, get_ownership, set_ownership,
#   intents_for_dpids, log_event
# Extra helpers: get_intent, set_intent_status, get_events, set_store_path, reset_store

from __future__ import annotations

import contextlib
import copy
import json
import os
import threading
import time
from pathlib import Path

try:                      # Windows
    import msvcrt
except ImportError:       # pragma: no cover
    msvcrt = None
try:                      # Linux / macOS
    import fcntl
except ImportError:       # pragma: no cover
    fcntl = None

REPO_ROOT = Path(__file__).resolve().parent.parent
# Override with the SDN_STORE_PATH environment variable (the tests do this).
STORE_PATH = Path(os.environ.get("SDN_STORE_PATH") or (REPO_ROOT / "shared" / "store.json"))

DEFAULT_OWNERSHIP = {"1": "c1", "2": "c1", "3": "c2", "4": "c2", "5": "c3", "6": "c3"}
LOCK_TIMEOUT_S = 10.0

_thread_lock = threading.RLock()   # serialises threads inside one process


def set_store_path(path):
    """Point the store at a different JSON file (used by tests)."""
    global STORE_PATH
    STORE_PATH = Path(path)


# --------------------------------------------------------------------------
# Locking
# --------------------------------------------------------------------------
def _lock_file(fh):
    """Acquire an exclusive lock on an open lock file, waiting up to LOCK_TIMEOUT_S."""
    deadline = time.time() + LOCK_TIMEOUT_S
    while True:
        try:
            fh.seek(0)
            if msvcrt is not None:
                msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)       # lock byte 0
            elif fcntl is not None:
                fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return
        except (OSError, IOError):
            if time.time() > deadline:
                raise TimeoutError("Could not lock %s within %.0fs" % (STORE_PATH, LOCK_TIMEOUT_S))
            time.sleep(0.05)


def _unlock_file(fh):
    fh.seek(0)
    if msvcrt is not None:
        msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
    elif fcntl is not None:
        fcntl.flock(fh.fileno(), fcntl.LOCK_UN)


@contextlib.contextmanager
def _locked():
    """Exclusive lock for one read-modify-write cycle (thread- and process-safe)."""
    with _thread_lock:
        STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
        lock_path = str(STORE_PATH) + ".lock"
        fh = open(lock_path, "a+b")
        try:
            if os.path.getsize(lock_path) == 0:   # msvcrt needs at least 1 byte to lock
                fh.write(b"0")
                fh.flush()
            _lock_file(fh)
            try:
                yield
            finally:
                _unlock_file(fh)
        finally:
            fh.close()


# --------------------------------------------------------------------------
# Raw load / save (call ONLY while holding the lock)
# --------------------------------------------------------------------------
def _fresh():
    return {"intents": [], "ownership": dict(DEFAULT_OWNERSHIP), "event_log": [], "next_id": 1}


def _load():
    if not STORE_PATH.exists() or STORE_PATH.stat().st_size == 0:
        return _fresh()
    with open(STORE_PATH, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError as exc:
            raise RuntimeError("%s is not valid JSON (%s). Fix or delete it." % (STORE_PATH, exc))
    base = _fresh()
    for key, default in base.items():     # tolerate files missing a key
        data.setdefault(key, default)
    return data


def _save(data):
    tmp = str(STORE_PATH) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.flush()
        os.fsync(f.fileno())
    for attempt in range(20):             # Windows: antivirus may briefly hold the file
        try:
            os.replace(tmp, STORE_PATH)
            return
        except PermissionError:
            if attempt == 19:
                raise
            time.sleep(0.05)


# --------------------------------------------------------------------------
# Public API (section 4.4)
# --------------------------------------------------------------------------
def add_intent(intent):
    """Store a new intent, assign it the next free id, return that id.

    The id is never re-used, even after remove_intent (rule cookies = intent id)."""
    with _locked():
        data = _load()
        used = [i.get("id", 0) for i in data["intents"]]
        new_id = max([data["next_id"]] + [u + 1 for u in used])
        stored = copy.deepcopy(intent)
        stored["id"] = new_id
        stored.setdefault("status", "active")
        data["intents"].append(stored)
        data["next_id"] = new_id + 1
        _save(data)
        return new_id


def remove_intent(intent_id):
    """Delete an intent. Returns True if it existed."""
    with _locked():
        data = _load()
        kept = [i for i in data["intents"] if i.get("id") != intent_id]
        if len(kept) == len(data["intents"]):
            return False
        data["intents"] = kept
        _save(data)
        return True


def list_intents():
    """All stored intents (list of dicts, oldest first)."""
    with _locked():
        return copy.deepcopy(_load()["intents"])


def get_intent(intent_id):
    """One intent by id, or None."""
    for intent in list_intents():
        if intent.get("id") == intent_id:
            return intent
    return None


def set_intent_status(intent_id, status):
    """Change an intent's status field ("active", "partial", ...). Returns True if found."""
    with _locked():
        data = _load()
        for intent in data["intents"]:
            if intent.get("id") == intent_id:
                intent["status"] = status
                _save(data)
                return True
        return False


def get_ownership():
    """{dpid_str: controller_id} - who is currently master of each switch."""
    with _locked():
        return dict(_load()["ownership"])


def set_ownership(dpid, controller_id):
    """Record that controller_id now owns switch dpid (used after a takeover)."""
    with _locked():
        data = _load()
        data["ownership"][str(dpid)] = controller_id
        _save(data)


def intents_for_dpids(dpids):
    """Intents that have at least one sub-policy on one of the given dpids.

    Returned intents are copies whose "subpolicies" list is FILTERED down to just
    those dpids, so the caller can feed them straight into POST /takeover. Each
    returned dict still has "id" (= the rule cookie / intent_id)."""
    wanted = {int(d) for d in dpids}
    result = []
    with _locked():
        intents = _load()["intents"]
    for intent in intents:
        subs = [copy.deepcopy(s) for s in intent.get("subpolicies", [])
                if int(s.get("dpid", -1)) in wanted]
        if subs:
            trimmed = copy.deepcopy(intent)
            trimmed["subpolicies"] = subs
            result.append(trimmed)
    return result


def log_event(event):
    """Append an event dict to the event log (a "time" stamp is added if missing)."""
    entry = dict(event)
    entry.setdefault("time", time.strftime("%Y-%m-%d %H:%M:%S"))
    with _locked():
        data = _load()
        data["event_log"].append(entry)
        _save(data)


def get_events(limit=None):
    """The event log (most recent `limit` entries if given)."""
    with _locked():
        events = _load()["event_log"]
    return copy.deepcopy(events[-limit:] if limit else events)


def reset_store():
    """Wipe everything back to an empty store (used by tests / demo reset)."""
    with _locked():
        _save(_fresh())
