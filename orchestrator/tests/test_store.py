# orchestrator/tests/test_store.py
# Owner: Varun
# Unit tests for orchestrator/store.py (uses a temp file, never shared/store.json).

import json
import subprocess
import sys
from pathlib import Path

import pytest

from orchestrator import store

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def temp_store(tmp_path):
    old = store.STORE_PATH
    store.set_store_path(tmp_path / "store.json")
    yield
    store.set_store_path(old)


def intent(dpids=(1,), text="x"):
    return {"text": text, "action": "block",
            "subpolicies": [{"dpid": d, "controller": "c1",
                             "match": {"eth_type": 2048, "ipv4_src": "10.0.1.1"},
                             "action": "drop", "priority": 100} for d in dpids]}


def test_add_assigns_incrementing_ids_and_never_reuses():
    assert store.add_intent(intent()) == 1
    assert store.add_intent(intent()) == 2
    assert store.remove_intent(2)
    assert store.add_intent(intent()) == 3          # 2 is not handed out again


def test_list_get_remove():
    i = store.add_intent(intent(text="hello"))
    assert [x["id"] for x in store.list_intents()] == [i]
    assert store.get_intent(i)["text"] == "hello" and store.get_intent(i)["status"] == "active"
    assert store.remove_intent(i) is True
    assert store.remove_intent(i) is False
    assert store.list_intents() == []


def test_ownership_defaults_and_set():
    assert store.get_ownership() == {"1": "c1", "2": "c1", "3": "c2", "4": "c2", "5": "c3", "6": "c3"}
    store.set_ownership(1, "c2")
    store.set_ownership(2, "c2")
    own = store.get_ownership()
    assert own["1"] == "c2" and own["2"] == "c2" and own["5"] == "c3"


def test_intents_for_dpids_filters_subpolicies():
    a = store.add_intent(intent(dpids=(1, 5)))
    b = store.add_intent(intent(dpids=(3,)))
    got = store.intents_for_dpids([1, 2])
    assert [g["id"] for g in got] == [a]
    assert [s["dpid"] for s in got[0]["subpolicies"]] == [1]       # dpid 5 trimmed away
    assert [g["id"] for g in store.intents_for_dpids([3, 5])] == [a, b]
    assert store.intents_for_dpids([6]) == []


def test_log_event_adds_time_and_keeps_order():
    store.log_event({"type": "a"})
    store.log_event({"type": "b", "time": "T"})
    ev = store.get_events()
    assert [e["type"] for e in ev] == ["a", "b"] and "time" in ev[0] and ev[1]["time"] == "T"


def test_status_update_and_persistence_on_disk():
    i = store.add_intent(intent())
    assert store.set_intent_status(i, "partial") and not store.set_intent_status(99, "x")
    on_disk = json.loads(store.STORE_PATH.read_text())
    assert on_disk["intents"][0]["status"] == "partial"
    assert set(on_disk) >= {"intents", "ownership", "event_log"}


def test_corrupt_file_gives_clear_error():
    store.STORE_PATH.write_text("{not json")
    with pytest.raises(RuntimeError):
        store.list_intents()


def test_two_processes_writing_at_once_lose_nothing():
    code = ("import sys; from orchestrator import store; store.set_store_path(sys.argv[1]);"
            "[store.add_intent({'text': sys.argv[2], 'subpolicies': []}) for _ in range(15)]")
    procs = [subprocess.Popen([sys.executable, "-c", code, str(store.STORE_PATH), "p%d" % n],
                              cwd=str(REPO_ROOT)) for n in range(3)]
    assert all(p.wait(timeout=60) == 0 for p in procs)
    ids = [i["id"] for i in store.list_intents()]
    assert len(ids) == 45 and len(set(ids)) == 45                  # no lost updates, no duplicate ids
