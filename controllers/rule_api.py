# controllers/rule_api.py
# Owner: Narain
# Purpose: Ryu WSGI app that exposes the REST API defined in section 4.3.
#          Loaded alongside base_app.py by the same ryu-manager process.
#          REST port comes from the REST_PORT environment variable.
#
# RUBRIC REQUIREMENT: all flow rules sent by this app are hand-written
# OFPFlowMod messages. Do NOT use ofctl_rest or any ready-made rule app.
# Comment every match field, priority, cookie, and instruction.
#
# Endpoints (section 4.3):
#   GET  /status                 -> {controller_id, mastered_dpids, rule_count}
#   GET  /flows?dpid=N           -> list of flow entries (OFPFlowStatsRequest)
#   POST /rules                  -> install drop rule (section 4.2 sub-policy)
#   DELETE /rules/<intent_id>    -> delete by cookie
#   POST /takeover               -> RoleRequest MASTER + install rules
#
# Drop rule spec (section 4.6, priority 100):
#   match: eth_type=0x0800, ipv4_src=... and/or ipv4_dst=... (wildcard if absent)
#   instructions: []   (empty = drop)
#   cookie: intent_id
#   cookie_mask: 0xFFFFFFFFFFFFFFFF
#
# Takeover spec (section 6.3):
#   For each dpid: send OFPRoleRequest MASTER with a new generation_id.
#   Then install all supplied rules.
#   Must work for 2 switches simultaneously.
#
# TODO (Narain):
#   1. Create a WSGI router (ryu.app.wsgi).
#   2. Track datapaths via EventOFPStateChange.
#   3. Track which dpids this controller is MASTER of.
#   4. Implement each endpoint as described above.
