# orchestrator/tests/test_decomposer.py
# Owner: Varun
# Purpose: Unit tests for orchestrator/decomposer.py
#
# TODO (Varun): verify that:
#   - "block guest from server" produces rules on s1, s2 (c1) AND s5, s6 (c3)
#   - "disable h3" produces exactly 2 rules on dpid 3 (c2): one ipv4_src,
#     one ipv4_dst wildcard rule
#   - Duplicate rules on the same (dpid, match) are removed
#   - eth_type is always 2048 and ARP rules are never generated
