# orchestrator/orchestrator.py
# Owner: Varun
# Purpose: Interactive CLI loop — the main entry point for the demo.
#
# Usage:
#   python orchestrator/orchestrator.py [--start-monitor]
#
# Commands (section 4.5 + demo section 8):
#   <intent text>   parse → decompose → twin.check → store → deploy via HTTP
#   list            print all active intents from the store
#   remove N        delete intent N (sends DELETE /rules/N to each controller)
#   status          GET /status from each controller and print a summary
#   quit / exit     leave the CLI
#
# TODO (Varun):
#   1. Load shared/topology.json at startup.
#   2. Read intent text from stdin in a loop.
#   3. Call parser.parse(), decomposer.decompose(), twin.check() (stub until
#      Karthik pushes his code), store.add_intent(), then POST each sub-policy
#      to the owning controller's REST port.
#   4. Print every intermediate step clearly (used in the live demo).
#   5. Use a stub twin.check that always returns {"safe": True, "reason": "stub"}
#      until orchestrator/twin.py is available.
