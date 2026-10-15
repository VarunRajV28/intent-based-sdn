# orchestrator/mock_controller.py
# Owner: Varun
# Purpose: Tiny Flask server that implements the full REST API (section 4.3)
#          in memory, so Varun and Karthik can develop and test without Ryu.
#
# Usage (start 3 instances in separate terminals):
#   CONTROLLER_ID=c1 REST_PORT=8081 python orchestrator/mock_controller.py
#   CONTROLLER_ID=c2 REST_PORT=8082 python orchestrator/mock_controller.py
#   CONTROLLER_ID=c3 REST_PORT=8083 python orchestrator/mock_controller.py
#
# Endpoints to implement (section 4.3):
#   GET  /status
#   GET  /flows?dpid=N
#   POST /rules           body: sub-policy + intent_id
#   DELETE /rules/<int:intent_id>
#   POST /takeover        body: {dpids: [...], rules: [...]}
#
# TODO (Varun): implement each endpoint.
