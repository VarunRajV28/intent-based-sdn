# orchestrator/orchestrator.py
# Owner: Varun
# Purpose: Interactive CLI - the main entry point for the demo.
#
# Usage (from the repo root):
#   python orchestrator/orchestrator.py [--start-monitor] [--real-twin]
#                                       [--controller-host 127.0.0.1] [--store PATH]
#
# Commands:
#   <intent text>   parse -> decompose -> twin.check -> store -> deploy (HTTP)
#                   e.g.  block guest from server | disable h3 | block h2 and h5 |
#                         isolate h4 | enable h3 | allow h2 and h5 | remove intent 1
#   list            show all intents saved in the store
#   remove N        delete intent N (DELETE /rules/N on every controller)
#   status          GET /status from every controller
#   log             show the last events from the store's event log
#   help / quit
#
# The twin is a STUB (always Safe) until Karthik's orchestrator/twin.py is ready;
# start with --real-twin to call his twin.check(topology, intent, subpolicies) instead.

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import requests

# Make "from orchestrator import ..." work whether started as
#   python orchestrator/orchestrator.py   or   python -m orchestrator.orchestrator
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orchestrator import decomposer, store  # noqa: E402
from orchestrator import parser as intent_parser  # noqa: E402

TOPOLOGY_PATH = REPO_ROOT / "shared" / "topology.json"
HTTP_TIMEOUT_S = 3.0
REVOKE_ACTIONS = ("enable", "allow", "remove")

HELP = (
    "Type an intent in plain English, or a command:\n"
    "  block guest from server | block h2 and h5 | isolate h4 | disable h3 | deactivate h3\n"
    "  enable h3 | allow h2 and h5 | remove intent N\n"
    "  list | status | log | help | quit"
)


# --------------------------------------------------------------------------
# Twin (safety checker)
# --------------------------------------------------------------------------
def twin_check_stub(topology, intent, subpolicies):
    """Stand-in for Karthik's twin.check (section 4.7): everything is Safe."""
    return {"safe": True, "reason": "stub", "blocked_pairs": []}


def load_twin_check(use_real):
    """Return the twin.check function to use (stub unless --real-twin works)."""
    if use_real:
        try:
            from orchestrator import twin
            if callable(getattr(twin, "check", None)):
                print("[twin] using orchestrator/twin.py")
                return twin.check
            print("[twin] twin.py has no check() yet - falling back to the stub")
        except Exception as exc:    # ImportError or an error inside twin.py
            print("[twin] could not import twin.py (%s) - falling back to the stub" % exc)
    return twin_check_stub


# --------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------
def load_topology(path=TOPOLOGY_PATH):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def controller_urls(topology, host):
    """{"c1": "http://127.0.0.1:8081", ...} from topology.json."""
    return {c["id"]: "http://%s:%d" % (host, int(c["rest_port"])) for c in topology["controllers"]}


def short_match(match):
    parts = []
    if "ipv4_src" in match:
        parts.append("src=" + match["ipv4_src"])
    if "ipv4_dst" in match:
        parts.append("dst=" + match["ipv4_dst"])
    return " ".join(parts) or "(any)"


def print_policy(policy):
    shown = {k: v for k, v in policy.items() if v is not None}
    print("  policy: " + json.dumps(shown))


def print_subpolicies(subpolicies):
    """Group sub-policies by controller and dpid for the demo."""
    if not subpolicies:
        print("  (no rules)")
        return
    for cid in sorted({s["controller"] for s in subpolicies}):
        print("  controller %s:" % cid)
        for dpid in sorted({s["dpid"] for s in subpolicies if s["controller"] == cid}):
            for s in (x for x in subpolicies if x["controller"] == cid and x["dpid"] == dpid):
                print("    s%d (dpid %d)  %s  %s  priority %d"
                      % (dpid, dpid, s["action"].upper(), short_match(s["match"]), s["priority"]))
    print("  total: %d rule(s) on %d switch(es)"
          % (len(subpolicies), len({s["dpid"] for s in subpolicies})))


def _post_ok(resp):
    try:
        return resp.status_code == 200 and resp.json().get("ok") is True
    except ValueError:
        return False


# --------------------------------------------------------------------------
# The orchestrator
# --------------------------------------------------------------------------
class Orchestrator:
    def __init__(self, topology, controller_host="127.0.0.1", twin_check=twin_check_stub):
        self.topology = topology
        self.urls = controller_urls(topology, controller_host)
        self.twin_check = twin_check

    # ---- HTTP ----------------------------------------------------------
    def deploy(self, intent_id, subpolicies):
        """POST every sub-policy to the controller that currently owns its switch.

        Returns the number of failures."""
        ownership = store.get_ownership()           # may differ from default after a failover
        failures = 0
        for sp in subpolicies:
            cid = ownership.get(str(sp["dpid"]), sp["controller"])
            body = dict(sp, controller=cid, intent_id=intent_id)
            label = "%s s%d %s" % (cid, sp["dpid"], short_match(sp["match"]))
            try:
                resp = requests.post(self.urls[cid] + "/rules", json=body, timeout=HTTP_TIMEOUT_S)
                ok = _post_ok(resp)
                detail = "" if ok else " (%s)" % resp.text.strip()[:80]
            except requests.RequestException as exc:
                ok, detail = False, " (%s)" % type(exc).__name__
            print("    [%s] POST /rules -> %s%s" % ("OK" if ok else "FAIL", label, detail))
            failures += 0 if ok else 1
        return failures

    def undeploy(self, intent_id):
        """DELETE /rules/<id> on every controller; unreachable ones only produce a warning."""
        for cid in sorted(self.urls):
            try:
                resp = requests.delete("%s/rules/%d" % (self.urls[cid], intent_id), timeout=HTTP_TIMEOUT_S)
                ok = _post_ok(resp)
                extra = ""
                if ok:
                    extra = " (%s rule(s) removed)" % resp.json().get("removed", "?")
                print("    [%s] DELETE /rules/%d -> %s%s" % ("OK" if ok else "FAIL", intent_id, cid, extra))
            except requests.RequestException as exc:
                print("    [WARN] %s unreachable (%s) - skipped" % (cid, type(exc).__name__))

    # ---- commands ------------------------------------------------------
    def handle(self, text):
        """Process one line of input (intent or command). Returns False to quit."""
        line = text.strip()
        word = line.lower()
        if not line:
            return True
        if word in ("quit", "exit", "q"):
            return False
        if word in ("help", "?"):
            print(HELP)
        elif word in ("list", "ls"):
            self.cmd_list()
        elif word == "status":
            self.cmd_status()
        elif word == "log":
            self.cmd_log()
        else:
            self.handle_intent(line)
        return True

    def cmd_list(self):
        intents = store.list_intents()
        if not intents:
            print("  (no intents stored)")
        for i in intents:
            switches = sorted({s["dpid"] for s in i.get("subpolicies", [])})
            print("  #%-3d [%-7s] %-34s %2d rule(s) on dpids %s"
                  % (i["id"], i.get("status", "?"), i.get("text", ""),
                     len(i.get("subpolicies", [])), switches))

    def cmd_status(self):
        ownership = store.get_ownership()
        for cid in sorted(self.urls):
            try:
                data = requests.get(self.urls[cid] + "/status", timeout=HTTP_TIMEOUT_S).json()
                print("  %s  UP    masters dpids %s   %s rule(s)   (%s)"
                      % (cid, data.get("mastered_dpids"), data.get("rule_count"), self.urls[cid]))
            except (requests.RequestException, ValueError):
                print("  %s  DOWN  (%s not reachable)" % (cid, self.urls[cid]))
        print("  store ownership: " + ", ".join(
            "s%s->%s" % (d, ownership[d]) for d in sorted(ownership, key=int)))

    def cmd_log(self):
        events = store.get_events(limit=10)
        if not events:
            print("  (event log is empty)")
        for e in events:
            print("  " + json.dumps(e))

    def handle_intent(self, text):
        # 1. PARSE -------------------------------------------------------
        print("[1/5] Parse")
        try:
            policy = intent_parser.parse(text)
        except ValueError as exc:
            print("  ERROR: %s" % exc)
            return
        print_policy(policy)

        # enable / allow / remove: cancel stored intents, nothing new to deploy
        if policy["action"] in REVOKE_ACTIONS:
            self.revoke(policy)
            return

        # 2. DECOMPOSE ---------------------------------------------------
        print("[2/5] Decompose into per-controller rules")
        try:
            subpolicies = decomposer.decompose(policy, self.topology)
        except ValueError as exc:
            print("  ERROR: %s" % exc)
            return
        print_subpolicies(subpolicies)

        # Same intent already active? Do not install it twice.
        for old in store.list_intents():
            if all(old.get(k) == policy[k] for k in ("action", "src", "dst", "target", "two_way")):
                print("  Already active as intent #%d - nothing to do." % old["id"])
                return

        # 3. TWIN CHECK --------------------------------------------------
        print("[3/5] Digital-twin safety check")
        try:
            verdict = self.twin_check(self.topology, policy, subpolicies)
        except Exception as exc:
            print("  ERROR: twin check crashed (%s: %s). Intent NOT deployed." % (type(exc).__name__, exc))
            return
        print("  verdict: %s - %s" % ("SAFE" if verdict["safe"] else "UNSAFE", verdict["reason"]))
        if verdict.get("blocked_pairs"):
            print("  blocked pairs: " + ", ".join("%s->%s" % tuple(p) for p in verdict["blocked_pairs"]))
        if not verdict["safe"]:
            print("  REJECTED: intent was not saved or deployed.")
            store.log_event({"type": "intent_rejected", "text": text, "reason": verdict["reason"]})
            return

        # 4. STORE -------------------------------------------------------
        print("[4/5] Save to intent store")
        intent = dict(policy, text=text, status="active", subpolicies=subpolicies)
        intent_id = store.add_intent(intent)
        print("  saved as intent #%d" % intent_id)

        # 5. DEPLOY ------------------------------------------------------
        print("[5/5] Deploy to controllers")
        failures = self.deploy(intent_id, subpolicies)
        if failures:
            store.set_intent_status(intent_id, "partial")
            store.log_event({"type": "intent_partial", "intent_id": intent_id, "failed_rules": failures})
            print("  WARNING: %d of %d rule(s) not delivered. Intent #%d is saved (status 'partial');"
                  " a failover re-installs saved rules, or 'remove %d' and retry."
                  % (failures, len(subpolicies), intent_id, intent_id))
        else:
            store.log_event({"type": "intent_deployed", "intent_id": intent_id, "text": text})
            print("  DEPLOYED intent #%d (%d rules)." % (intent_id, len(subpolicies)))

    def revoke(self, policy):
        """enable / allow / remove: delete matching intents from controllers and the store."""
        print("[2/3] Find matching intents")
        matches = decomposer.find_intents_to_revoke(policy, store.list_intents(), self.topology)
        if not matches:
            print("  No stored intent matches - nothing to do. (Type 'list' to see intents.)")
            return
        for m in matches:
            print("  intent #%d: %s" % (m["id"], m.get("text", "")))
        print("[3/3] Remove rules and delete from store")
        for m in matches:
            self.undeploy(m["id"])
            store.remove_intent(m["id"])
            store.log_event({"type": "intent_removed", "intent_id": m["id"], "text": m.get("text", "")})
            print("  REMOVED intent #%d." % m["id"])


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="Intent-based SDN orchestrator CLI")
    ap.add_argument("--start-monitor", action="store_true", help="also launch orchestrator/monitor.py")
    ap.add_argument("--real-twin", action="store_true", help="use Karthik's twin.check instead of the stub")
    ap.add_argument("--controller-host", default="127.0.0.1", help="host the controllers' REST APIs run on")
    ap.add_argument("--store", help="path of the store JSON (default shared/store.json)")
    args = ap.parse_args()

    if args.store:
        store.set_store_path(args.store)
    topology = load_topology()
    orch = Orchestrator(topology, args.controller_host, load_twin_check(args.real_twin))

    monitor_proc = None
    if args.start_monitor:
        monitor_proc = subprocess.Popen([sys.executable, str(REPO_ROOT / "orchestrator" / "monitor.py")],
                                        cwd=str(REPO_ROOT))
        print("[monitor] started (pid %d)" % monitor_proc.pid)

    print("Intent-based SDN orchestrator. Type 'help' for commands, 'quit' to leave.")
    try:
        while True:
            try:
                line = input("sdn> ")
            except EOFError:
                break
            print()
            if not orch.handle(line):
                break
            print()
    except KeyboardInterrupt:
        print()
    finally:
        if monitor_proc and monitor_proc.poll() is None:
            monitor_proc.terminate()


if __name__ == "__main__":
    main()
