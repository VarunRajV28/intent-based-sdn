# orchestrator/twin.py
# Owner: Karthik
# Purpose: Digital-twin safety checker (section 4.7).
#
# Public interface (called by Varun's orchestrator.py):
#
#   check(topology: dict, intent: dict, subpolicies: list[dict]) -> dict
#
#   Returns:
#     {
#       "safe": bool,
#       "reason": str,           # human-readable sentence
#       "blocked_pairs": [       # list of [src_host_name, dst_host_name]
#           ["h1", "h5"], ...
#       ]
#     }
#
# Safety rules (section 4.7 + 4.1 invariants):
#   1. The intended pairs ARE blocked after applying sub-policies.
#   2. Each invariant in topology["invariants"] still has >= 1 reachable pair.
#   3. No host OUTSIDE the intent's target loses ALL connectivity.
#
# TODO (Karthik):
#   Build a networkx DiGraph from topology. For each sub-policy mark the
#   (src_ip → dst_ip) edge as blocked. Run reachability checks.
