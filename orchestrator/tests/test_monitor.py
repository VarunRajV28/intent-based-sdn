# orchestrator/tests/test_monitor.py
# Owner: Karthik
# Purpose: Unit tests for orchestrator/monitor.py
#
# TODO (Karthik): use Varun's mock_controller (or a test-double) to simulate
# controller death and verify that:
#   - A controller is declared dead after exactly 3 missed polls (~3 s)
#   - The survivor with the fewest switches is chosen
#   - POST /takeover is called with the correct dpids and rules
#   - store ownership is updated after takeover
