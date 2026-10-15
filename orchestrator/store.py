# orchestrator/store.py
# Owner: Varun
# Purpose: Thread-safe JSON file wrapper for the shared intent store.
#          File: shared/store.json  (see section 4.4)
#
# TODO (Varun):
#   Implement the following functions using file locking (fcntl or portalocker):
#
#   add_intent(intent: dict) -> int          # returns assigned id
#   remove_intent(intent_id: int) -> bool
#   list_intents() -> list[dict]
#   get_ownership() -> dict                  # {dpid_str: controller_id}
#   set_ownership(dpid: int, controller_id: str)
#   intents_for_dpids(dpids: list[int]) -> list[dict]
#   log_event(event: dict)                   # appended to event_log list
#
# Schema of store.json:
#   {
#     "intents":   [ <intent objects> ],
#     "ownership": { "1": "c1", "2": "c1", ... },
#     "event_log": [ <event objects> ]
#   }
