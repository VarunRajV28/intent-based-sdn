# controllers/base_app.py
# Owner: Anuj
# Purpose: Hand-written Ryu application for table-miss, learned MAC forwarding,
#          and OpenFlow role handling (MASTER / SLAVE).
#          See sections 4.6 and 6.2 of the execution plan.
#
# Run via run_controllers.sh (together with rule_api.py):
#   CONTROLLER_ID=c1 REST_PORT=8081 \
#     ryu-manager --ofp-tcp-listen-port 6653 \
#       controllers/base_app.py controllers/rule_api.py
#
# RUBRIC REQUIREMENT: every flow rule is written by hand as an explicit
# OFPFlowMod message. Do NOT import or use simple_switch_13, ofctl_rest,
# or any ready-made forwarding app. Comment every field.
#
# Rules this app installs (section 4.6):
#   Priority 0  (table-miss): match=*, instructions=[output CONTROLLER]
#   Priority 1  (learned):    match={in_port, eth_dst}, instructions=[output port],
#                             idle_timeout=60
#
# OpenFlow roles (section 4.1):
#   On switch connect, send RoleRequest MASTER if this controller is the
#   default_owner of that dpid (from shared/topology.json), else SLAVE.
#   Use an increasing generation_id so the role is accepted.
#
# TODO (Anuj):
#   1. Load shared/topology.json to know each controller's default dpids.
#   2. On EventOFPSwitchFeatures: send table-miss flow-mod, then RoleRequest.
#   3. On EventOFPPacketIn (only for mastered switches):
#        - Parse Ethernet frame.
#        - Learn src_mac -> in_port per dpid.
#        - If dst_mac known: send priority-1 flow-mod + packet-out.
#        - Else: flood with packet-out.
#   4. Comment every match field, priority, instruction, timeout, cookie.
