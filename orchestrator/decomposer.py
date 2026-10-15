# orchestrator/decomposer.py
# Owner: Varun
# Purpose: Expand a policy dict (parser.py) into sub-policies (section 4.2):
#          one drop rule per (controller, dpid, match).
#
# Sub-policy format (what the controllers' POST /rules receives, plus intent_id):
#   {"controller": "c1", "dpid": 1,
#    "match": {"eth_type": 2048, "ipv4_src": "10.0.1.1", "ipv4_dst": "10.0.3.1"},
#    "action": "drop", "priority": 100}
#
# Rules of the game:
#   * eth_type is always 2048 (IPv4). ARP (0x0806) is never matched, so ARP is never blocked.
#   * A missing ipv4_src / ipv4_dst means "wildcard".
#   * Host-PAIR rules (block, isolate GROUP): for every (src_host, dst_host) pair we
#     place the rule on the source host's switch (ingress) AND on the destination
#     host's switch (second line of defence).
#   * Host-LEVEL rules (disable HOST, isolate HOST): exactly two wildcard rules on that
#     host's own switch - one with only ipv4_src, one with only ipv4_dst.
#   * Duplicates on the same (dpid, match) are removed; output order is deterministic.
#   * "controller" = the switch's default_owner from topology.json.
#
# enable / allow / remove create NO rules: decompose() returns [] for them and
# find_intents_to_revoke() tells the orchestrator which stored intents to delete.

from __future__ import annotations

ETH_TYPE_IPV4 = 2048
DROP_PRIORITY = 100
_REVOKE_ACTIONS = ("enable", "allow", "remove")


# --------------------------------------------------------------------------
# Topology helpers
# --------------------------------------------------------------------------
def _groups(topology):
    """{group_name: [host names]} - from topology["groups"] or the hosts' group field."""
    if topology.get("groups"):
        return topology["groups"]
    groups = {}
    for host in topology["hosts"]:
        groups.setdefault(host["group"], []).append(host["name"])
    return groups


def resolve_hosts(entity, topology):
    """Turn a group name ("guest") or host name ("h3") into a list of host dicts."""
    by_name = {h["name"]: h for h in topology["hosts"]}
    if entity in by_name:
        return [by_name[entity]]
    groups = _groups(topology)
    if entity in groups:
        return [by_name[n] for n in groups[entity]]
    raise ValueError("Unknown group or host '%s'" % entity)


def _owner_map(topology):
    return {int(s["dpid"]): s["default_owner"] for s in topology["switches"]}


# --------------------------------------------------------------------------
# Decomposition
# --------------------------------------------------------------------------
def decompose(policy, topology):
    """Policy dict -> sorted list of sub-policy dicts (may be [] for revoke actions)."""
    action = policy["action"]
    if action in _REVOKE_ACTIONS:
        return []

    owners = _owner_map(topology)
    rules = {}   # (dpid, ipv4_src, ipv4_dst) -> sub-policy; the key makes duplicates impossible

    def add(dpid, src_ip, dst_ip):
        dpid = int(dpid)
        match = {"eth_type": ETH_TYPE_IPV4}
        if src_ip:
            match["ipv4_src"] = src_ip      # omitted key = wildcard
        if dst_ip:
            match["ipv4_dst"] = dst_ip
        rules.setdefault((dpid, src_ip, dst_ip), {
            "controller": owners[dpid],
            "dpid": dpid,
            "match": match,
            "action": "drop",
            "priority": DROP_PRIORITY,
        })

    def add_host_pair(src_host, dst_host):
        if src_host["name"] == dst_host["name"]:
            return                                       # a host never blocks itself
        add(src_host["switch"], src_host["ip"], dst_host["ip"])   # ingress switch
        add(dst_host["switch"], src_host["ip"], dst_host["ip"])   # destination switch

    def add_wildcards(host):
        add(host["switch"], host["ip"], None)            # everything FROM the host
        add(host["switch"], None, host["ip"])            # everything TO the host

    if action == "block":
        srcs = resolve_hosts(policy["src"], topology)
        dsts = resolve_hosts(policy["dst"], topology)
        for s in srcs:
            for d in dsts:
                add_host_pair(s, d)
                if policy.get("two_way"):
                    add_host_pair(d, s)

    elif action == "disable":
        for host in resolve_hosts(policy["target"], topology):
            add_wildcards(host)

    elif action == "isolate":
        target = policy["target"]
        members = resolve_hosts(target, topology)
        if target in {h["name"] for h in topology["hosts"]}:
            # Single host: "everyone else" == wildcard, so two wildcard rules suffice.
            add_wildcards(members[0])
        else:
            # Group: block member <-> every host outside the group (traffic INSIDE the
            # group keeps working, so wildcards cannot be used here).
            inside = {h["name"] for h in members}
            outsiders = [h for h in topology["hosts"] if h["name"] not in inside]
            for m in members:
                for o in outsiders:
                    add_host_pair(m, o)
                    add_host_pair(o, m)
    else:
        raise ValueError("Cannot decompose unknown action '%s'" % action)

    if not rules:
        raise ValueError("Intent produced no rules (nothing to block)")

    return [rules[k] for k in sorted(rules, key=lambda k: (k[0], k[1] or "", k[2] or ""))]


# --------------------------------------------------------------------------
# enable / allow / remove: which stored intents does this command cancel?
# --------------------------------------------------------------------------
def find_intents_to_revoke(policy, intents, topology):
    """Return the stored intents that an enable / allow / remove policy cancels."""
    action = policy["action"]

    if action == "remove":
        return [i for i in intents if i.get("id") == policy["intent_id"]]

    if action == "enable":
        # cancel disable/isolate intents whose hosts are all inside the enabled target
        enabled = {h["name"] for h in resolve_hosts(policy["target"], topology)}
        found = []
        for i in intents:
            if i.get("action") in ("disable", "isolate") and i.get("target"):
                hosts = {h["name"] for h in resolve_hosts(i["target"], topology)}
                if hosts <= enabled:
                    found.append(i)
        return found

    if action == "allow":
        # cancel block intents between the same two entities (either direction)
        pair = {policy["src"], policy["dst"]}
        return [i for i in intents
                if i.get("action") == "block" and {i.get("src"), i.get("dst")} == pair]

    return []
