# orchestrator/decomposer.py
# Owner: Varun
# Purpose: Expand a policy dict (from parser.py) into a list of sub-policies,
#          one per (controller, dpid, match) triple, per section 4.2.
#
# TODO (Varun):
#   Implement decompose(policy: dict, topology: dict) -> list[dict]
#   Rules:
#     - For each src/dst host pair, add a drop rule on the source ingress switch
#       AND a copy on the destination host's switch (second line of defense).
#     - Remove duplicate rules on the same (dpid, match).
#     - 'match' always has eth_type=2048; include ipv4_src and/or ipv4_dst.
#     - For host-level rules (disable/isolate), one rule with only ipv4_src and
#       one with only ipv4_dst on that host's switch.
#     - ARP (eth_type 0x0806) is NEVER blocked.
#     - Set controller from topology's default_owner for each dpid.
