# orchestrator/tests/test_decomposer.py
# Owner: Varun
# Unit tests for orchestrator/decomposer.py (loads the real shared/topology.json).
#
# Run from the repo root:  python -m pytest orchestrator/tests -v

import json
from pathlib import Path

import pytest

from orchestrator.decomposer import decompose, find_intents_to_revoke, resolve_hosts
from orchestrator.parser import parse

TOPO_PATH = Path(__file__).resolve().parents[2] / "shared" / "topology.json"


@pytest.fixture(scope="module")
def topo():
    with open(TOPO_PATH, encoding="utf-8") as f:
        return json.load(f)


def subs(text, topo):
    return decompose(parse(text), topo)


def dpids(rules):
    return {r["dpid"] for r in rules}


def keys(rules):
    return {(r["dpid"], r["match"].get("ipv4_src"), r["match"].get("ipv4_dst")) for r in rules}


# ---------------------------------------------------------------- block ----
def test_block_guest_from_server_hits_s1_s2_s5_s6(topo):
    rules = subs("block guest from server", topo)
    assert dpids(rules) == {1, 2, 5, 6}
    assert {r["controller"] for r in rules if r["dpid"] in (1, 2)} == {"c1"}
    assert {r["controller"] for r in rules if r["dpid"] in (5, 6)} == {"c3"}


def test_block_guest_from_server_exact_rules(topo):
    rules = subs("block guest from server", topo)
    # 4 host pairs (h1,h2 -> h5,h6), each on source switch + destination switch = 8 rules
    assert len(rules) == 8
    assert (1, "10.0.1.1", "10.0.3.1") in keys(rules)   # ingress copy of h1 -> h5
    assert (5, "10.0.1.1", "10.0.3.1") in keys(rules)   # destination copy of h1 -> h5
    # one-way: no rule for server -> guest
    assert not any(r["match"].get("ipv4_src", "").startswith("10.0.3.") for r in rules)


def test_rule_format_matches_section_4_2(topo):
    for r in subs("block guest from server", topo):
        assert set(r) == {"controller", "dpid", "match", "action", "priority"}
        assert r["action"] == "drop" and r["priority"] == 100
        assert r["match"]["eth_type"] == 2048
        assert "ipv4_src" in r["match"] or "ipv4_dst" in r["match"]
        assert set(r["match"]) <= {"eth_type", "ipv4_src", "ipv4_dst"}


def test_arp_is_never_matched(topo):
    for text in ("block guest from server", "disable h3", "isolate guest", "block h2 and h5"):
        assert all(r["match"]["eth_type"] != 0x0806 for r in subs(text, topo))


def test_block_two_way_hosts(topo):
    rules = subs("block h2 and h5", topo)
    # h2 (s2/c1) <-> h5 (s5/c3): 2 directions x 2 switches, all distinct
    assert keys(rules) == {
        (2, "10.0.1.2", "10.0.3.1"), (5, "10.0.1.2", "10.0.3.1"),
        (5, "10.0.3.1", "10.0.1.2"), (2, "10.0.3.1", "10.0.1.2"),
    }


def test_block_hosts_on_same_switch_are_deduplicated(topo):
    # h1 and h2 are different switches, so use a group vs itself on one host pair:
    # "block h3 and h3" is rejected by the parser; use policy directly with a same-switch pair.
    topo2 = json.loads(json.dumps(topo))
    for h in topo2["hosts"]:
        if h["name"] == "h2":
            h["switch"] = 1                      # put h2 on s1 as well
    rules = decompose(parse("block h1 and h2"), topo2)
    assert len(rules) == len(keys(rules))        # no duplicates
    assert dpids(rules) == {1}
    assert len(rules) == 2                       # h1->h2 and h2->h1, one rule each (src+dst copy merge)


def test_no_duplicate_rules_anywhere(topo):
    for text in ("block guest from server", "block guest and server", "isolate guest",
                 "isolate h4", "disable h3", "block staff and staff"):
        rules = subs(text, topo)
        assert len(rules) == len(keys(rules)), text


def test_group_to_same_group_skips_self_pairs(topo):
    rules = subs("block staff from staff", topo)     # h3->h4 and h4->h3 only
    assert keys(rules) == {
        (3, "10.0.2.1", "10.0.2.2"), (4, "10.0.2.1", "10.0.2.2"),
        (4, "10.0.2.2", "10.0.2.1"), (3, "10.0.2.2", "10.0.2.1"),
    }


# -------------------------------------------------------------- disable ----
def test_disable_h3_gives_exactly_two_wildcard_rules_on_s3(topo):
    rules = subs("disable h3", topo)
    assert len(rules) == 2
    assert dpids(rules) == {3}
    assert {r["controller"] for r in rules} == {"c2"}
    matches = sorted(rules, key=lambda r: sorted(r["match"]))
    assert {"eth_type": 2048, "ipv4_src": "10.0.2.1"} in [r["match"] for r in matches]
    assert {"eth_type": 2048, "ipv4_dst": "10.0.2.1"} in [r["match"] for r in matches]


def test_deactivate_is_same_as_disable(topo):
    assert subs("deactivate h3", topo) == subs("disable h3", topo)


def test_disable_group_gives_two_rules_per_host(topo):
    rules = subs("disable guest", topo)
    assert len(rules) == 4 and dpids(rules) == {1, 2}


# -------------------------------------------------------------- isolate ----
def test_isolate_host_is_two_wildcard_rules_on_its_switch(topo):
    rules = subs("isolate h4", topo)
    assert len(rules) == 2 and dpids(rules) == {4}
    assert {"eth_type": 2048, "ipv4_src": "10.0.2.2"} in [r["match"] for r in rules]
    assert {"eth_type": 2048, "ipv4_dst": "10.0.2.2"} in [r["match"] for r in rules]


def test_isolate_group_blocks_outsiders_but_not_inside_traffic(topo):
    rules = subs("isolate guest", topo)
    guests = {"10.0.1.1", "10.0.1.2"}
    for r in rules:
        s, d = r["match"]["ipv4_src"], r["match"]["ipv4_dst"]    # pair rules, no wildcards
        assert (s in guests) != (d in guests)                    # exactly one end is a guest
    assert dpids(rules) == {1, 2, 3, 4, 5, 6}


# -------------------------------------------------- controller assignment ----
def test_controller_matches_default_owner(topo):
    owner = {s["dpid"]: s["default_owner"] for s in topo["switches"]}
    for text in ("block guest from server", "isolate guest", "disable h5", "block h1 and h6"):
        for r in subs(text, topo):
            assert r["controller"] == owner[r["dpid"]]


def test_output_is_deterministic_and_sorted(topo):
    a = subs("block guest and server", topo)
    assert a == subs("block guest and server", topo)
    assert [r["dpid"] for r in a] == sorted(r["dpid"] for r in a)


# ----------------------------------------------------- revoke actions ----
@pytest.mark.parametrize("text", ["enable h3", "allow h2 and h5", "remove intent 1"])
def test_revoke_actions_produce_no_rules(topo, text):
    assert subs(text, topo) == []


def test_resolve_hosts(topo):
    assert [h["name"] for h in resolve_hosts("server", topo)] == ["h5", "h6"]
    assert [h["name"] for h in resolve_hosts("h3", topo)] == ["h3"]
    with pytest.raises(ValueError):
        resolve_hosts("nobody", topo)


def test_find_intents_enable_matches_disable_and_isolate(topo):
    intents = [
        {"id": 1, "action": "disable", "target": "h3"},
        {"id": 2, "action": "isolate", "target": "h3"},
        {"id": 3, "action": "disable", "target": "h4"},
        {"id": 4, "action": "block", "src": "guest", "dst": "server"},
    ]
    found = find_intents_to_revoke(parse("enable h3"), intents, topo)
    assert [i["id"] for i in found] == [1, 2]


def test_find_intents_enable_group_covers_member_hosts(topo):
    intents = [{"id": 1, "action": "disable", "target": "h3"},
               {"id": 2, "action": "disable", "target": "h1"}]
    assert [i["id"] for i in find_intents_to_revoke(parse("enable staff"), intents, topo)] == [1]
    # enabling one host does not cancel a whole-group disable
    intents = [{"id": 1, "action": "disable", "target": "staff"}]
    assert find_intents_to_revoke(parse("enable h3"), intents, topo) == []


def test_find_intents_allow_matches_either_direction(topo):
    intents = [{"id": 1, "action": "block", "src": "h2", "dst": "h5"},
               {"id": 2, "action": "block", "src": "guest", "dst": "server"}]
    assert [i["id"] for i in find_intents_to_revoke(parse("allow h5 and h2"), intents, topo)] == [1]
    assert [i["id"] for i in find_intents_to_revoke(parse("allow server and guest"), intents, topo)] == [2]
    assert find_intents_to_revoke(parse("allow h1 and h6"), intents, topo) == []


def test_find_intents_remove_by_id(topo):
    intents = [{"id": 1, "action": "block"}, {"id": 2, "action": "disable"}]
    assert [i["id"] for i in find_intents_to_revoke(parse("remove intent 2"), intents, topo)] == [2]
    assert find_intents_to_revoke(parse("remove intent 9"), intents, topo) == []
