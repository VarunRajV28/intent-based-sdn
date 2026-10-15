# orchestrator/monitor.py
# Owner: Karthik
# Purpose: Heartbeat monitor and automatic failover (section 4.7 + 6.4).
#
# Usage:
#   python orchestrator/monitor.py
#   (Can also be launched by orchestrator.py with --start-monitor flag)
#
# Behaviour:
#   1. Poll GET /status on each of the 3 controllers every 1 second.
#   2. After 3 consecutive missed polls, declare that controller dead.
#   3. Pick the survivor with the fewest currently mastered switches.
#   4. Call store.intents_for_dpids(dead_dpids) to get the rules to reinstall.
#   5. POST /takeover to the chosen survivor with dead_dpids and the rules.
#   6. Call store.set_ownership(dpid, survivor_id) for each taken-over dpid.
#   7. Call store.log_event({...}) to record the failover.
#   8. Print a clear, timestamped line for every state change (used in demo).
#
# TODO (Karthik): implement the above using only store.py functions and the
# REST API; do NOT import internals from any controller or Ryu module.
