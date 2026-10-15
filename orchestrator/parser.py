# orchestrator/parser.py
# Owner: Varun
# Purpose: Parse plain-English intent text into a structured policy dict.
# See section 4.5 (supported intents) and section 4.7 (policy dict format).

# TODO (Varun):
#   Implement parse(text: str) -> dict
#   Supported patterns (case-insensitive, filler words ignored):
#     "block GROUP from GROUP"          -> action=block, src=GROUP, dst=GROUP, two_way=False
#     "block X and Y"                   -> action=block, src=X, dst=Y, two_way=True
#     "isolate X"                       -> action=isolate, target=X, two_way=True
#     "disable HOST" / "deactivate HOST"-> action=disable, target=HOST, two_way=True
#     "enable HOST"                     -> action=enable, target=HOST
#     "allow X and Y"                   -> action=allow, src=X, dst=Y, two_way=True
#     "remove intent N"                 -> action=remove, intent_id=N
#   Raise ValueError with a clear message for unrecognised input.
