# orchestrator/parser.py
# Owner: Varun
# Purpose: Turn plain-English intent text into the "policy dict" of section 4.7.
#
# Supported patterns (section 4.5), all case-insensitive, filler words ignored:
#
#   block GROUP from GROUP     one-way block   (src -> dst)
#   block X and Y              two-way block   (X <-> Y), X/Y = group or host
#   isolate X                  block X <-> everything else
#   disable HOST               (alias: deactivate) drop all IP traffic to/from HOST
#   enable HOST                undo disable/isolate on HOST
#   allow X and Y              undo a block between X and Y
#   remove intent N            delete intent number N
#
# The policy dict ALWAYS has exactly these six keys (unused ones are None):
#   action     "block" | "isolate" | "disable" | "enable" | "allow" | "remove"
#   src, dst   group or host name (block / allow) else None
#   two_way    True / False
#   target     group or host name (isolate / disable / enable) else None
#   intent_id  int (remove) else None
#
# parse() raises ValueError with a human-readable message on bad input.

from __future__ import annotations

import re

GROUPS = ("guest", "staff", "server")
HOSTS = tuple("h%d" % i for i in range(1, 7))  # h1 .. h6

# Words the user may sprinkle in; they carry no meaning for us and are dropped.
# NOTE: "from", "and", "to", "intent" are NOT fillers - the grammar needs them.
_FILLER = {
    "please", "kindly", "the", "a", "an", "all", "any", "of", "now",
    "traffic", "packets", "access", "between", "network",
    "group", "groups", "host", "hosts", "machine", "machines",
    "user", "users",
}

# Plural / alternative spellings of the group names.
_NORMALISE = {"guests": "guest", "servers": "server"}

# First word -> canonical action.
_VERBS = {
    "block": "block", "deny": "block",
    "isolate": "isolate", "quarantine": "isolate",
    "disable": "disable", "deactivate": "disable",
    "enable": "enable", "activate": "enable",
    "allow": "allow", "unblock": "allow", "permit": "allow",
    "remove": "remove", "delete": "remove", "undo": "remove", "revoke": "remove",
}

USAGE = (
    "Supported intents:\n"
    "  block GROUP from GROUP     e.g. block guest from server\n"
    "  block X and Y              e.g. block h2 and h5   (two-way)\n"
    "  isolate X                  e.g. isolate h4\n"
    "  disable HOST               e.g. disable h3   (also: deactivate)\n"
    "  enable HOST                e.g. enable h3\n"
    "  allow X and Y              e.g. allow h2 and h5\n"
    "  remove intent N            e.g. remove intent 2\n"
    "Groups: %s    Hosts: %s-%s" % (", ".join(GROUPS), HOSTS[0], HOSTS[-1])
)


def _policy(action, src=None, dst=None, two_way=False, target=None, intent_id=None):
    """Build the policy dict with all six keys present."""
    return {
        "action": action,
        "src": src,
        "dst": dst,
        "two_way": two_way,
        "target": target,
        "intent_id": intent_id,
    }


def _entity(token, original):
    """Validate that a token is a known group or host name."""
    if token in GROUPS or token in HOSTS:
        return token
    if re.fullmatch(r"h\d+", token):
        raise ValueError("Unknown host '%s' (valid hosts: %s-%s)"
                         % (token, HOSTS[0], HOSTS[-1]))
    raise ValueError("Unknown group or host '%s' in \"%s\" (groups: %s; hosts: %s-%s)"
                     % (token, original, ", ".join(GROUPS), HOSTS[0], HOSTS[-1]))


def _tokenise(text):
    """Lower-case, strip punctuation, drop filler words, normalise plurals."""
    cleaned = re.sub(r"[^a-z0-9\s]", " ", text.lower())
    tokens = []
    for word in cleaned.split():
        word = _NORMALISE.get(word, word)
        if word not in _FILLER:
            tokens.append(word)
    return tokens


def parse(text):
    """Parse intent text into a policy dict. Raises ValueError on bad input."""
    if text is None or not str(text).strip():
        raise ValueError("Empty intent. " + USAGE)
    original = str(text).strip()

    # "isolate h4 from everything else" -> "isolate h4" (done before filler removal)
    lowered = re.sub(r"\s+from\s+(everything|everyone|everybody|the rest|rest)(\s+else)?\s*$",
                     "", original.lower())
    tokens = _tokenise(lowered)
    if not tokens:
        raise ValueError("Could not understand \"%s\". %s" % (original, USAGE))

    verb = _VERBS.get(tokens[0])
    if verb is None:
        raise ValueError("Unrecognised intent \"%s\" (unknown command '%s'). %s"
                         % (original, tokens[0], USAGE))
    rest = tokens[1:]

    # ---- block / allow : need two entities -------------------------------
    if verb in ("block", "allow"):
        # "X and Y"  -> two-way
        if len(rest) == 3 and rest[1] == "and":
            x, y = _entity(rest[0], original), _entity(rest[2], original)
            if x == y and x in HOSTS:
                raise ValueError("'%s %s and %s' names the same host twice" % (verb, x, y))
            return _policy(verb, src=x, dst=y, two_way=True)
        # "X from Y"  -> one-way, traffic from X to Y (spec 4.5: "block guest from server")
        if len(rest) == 3 and rest[1] == "from":
            x, y = _entity(rest[0], original), _entity(rest[2], original)
            if x == y and x in HOSTS:
                raise ValueError("'%s %s from %s' names the same host twice" % (verb, x, y))
            return _policy(verb, src=x, dst=y, two_way=False)
        # "from X to Y" (after fillers: "block traffic from X to Y")
        if len(rest) == 4 and rest[0] == "from" and rest[2] == "to":
            x, y = _entity(rest[1], original), _entity(rest[3], original)
            if x == y and x in HOSTS:
                raise ValueError("'%s' names the same host twice" % original)
            return _policy(verb, src=x, dst=y, two_way=False)
        raise ValueError("Could not understand \"%s\". Use '%s X and Y'%s.\n%s"
                         % (original, verb,
                            " or 'block X from Y'" if verb == "block" else "", USAGE))

    # ---- isolate / disable / enable : exactly one entity -----------------
    if verb in ("isolate", "disable", "enable"):
        if len(rest) != 1:
            raise ValueError("'%s' needs exactly one group or host, e.g. '%s h3'. Got \"%s\"."
                             % (verb, verb, original))
        target = _entity(rest[0], original)
        return _policy(verb, target=target, two_way=(verb != "enable"))

    # ---- remove : "remove [intent|rule|policy] N" ------------------------
    if rest and rest[0] in ("intent", "rule", "policy"):
        rest = rest[1:]
    if len(rest) == 1 and rest[0].isdigit() and int(rest[0]) >= 1:
        return _policy("remove", intent_id=int(rest[0]))
    raise ValueError("'remove' needs an intent number, e.g. 'remove intent 2'. Got \"%s\"."
                     % original)
