# orchestrator/tests/test_twin.py
# Owner: Karthik
# Purpose: Unit tests for orchestrator/twin.py
#
# TODO (Karthik): test with hand-made topology and sub-policy dicts
# (do not wait for the real controllers).
#
# Required cases:
#   - "block guest from server"   -> safe: True
#   - "disable h3"                -> safe: True  (h4 still reaches servers)
#   - "block staff from server"   -> safe: False (both h3 and h4 blocked,
#                                    invariant broken, reason names invariant)
#   - Isolating a server host     -> check if other server host keeps paths
