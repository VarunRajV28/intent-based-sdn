# orchestrator/tests/test_parser.py
# Owner: Varun
# Unit tests for orchestrator/parser.py - every pattern in section 4.5 plus garbage.
#
# Run from the repo root:  python -m pytest orchestrator/tests -v

import pytest

from orchestrator.parser import parse

POLICY_KEYS = {"action", "src", "dst", "two_way", "target", "intent_id"}


def test_block_group_from_group():
    assert parse("block guest from server") == {
        "action": "block", "src": "guest", "dst": "server",
        "two_way": False, "target": None, "intent_id": None,
    }


def test_block_staff_from_server():
    p = parse("block staff from server")
    assert (p["action"], p["src"], p["dst"], p["two_way"]) == ("block", "staff", "server", False)


def test_block_host_and_host_is_two_way():
    p = parse("block h2 and h5")
    assert (p["action"], p["src"], p["dst"], p["two_way"]) == ("block", "h2", "h5", True)


def test_block_group_and_group_is_two_way():
    p = parse("block guest and server")
    assert (p["src"], p["dst"], p["two_way"]) == ("guest", "server", True)


def test_isolate_host_and_group():
    p = parse("isolate h4")
    assert p["action"] == "isolate" and p["target"] == "h4" and p["two_way"] is True
    assert parse("isolate guest")["target"] == "guest"


def test_isolate_from_everything_else_phrase():
    assert parse("isolate h4 from everything else")["target"] == "h4"


def test_disable_and_deactivate_alias():
    for word in ("disable", "deactivate"):
        p = parse("%s h3" % word)
        assert p["action"] == "disable" and p["target"] == "h3" and p["two_way"] is True


def test_enable():
    p = parse("enable h3")
    assert p["action"] == "enable" and p["target"] == "h3"


def test_allow_x_and_y():
    p = parse("allow h2 and h5")
    assert (p["action"], p["src"], p["dst"], p["two_way"]) == ("allow", "h2", "h5", True)


def test_remove_intent_n():
    p = parse("remove intent 5")
    assert p["action"] == "remove" and p["intent_id"] == 5
    assert parse("remove 12")["intent_id"] == 12
    assert parse("remove intent #3")["intent_id"] == 3


def test_case_insensitive_and_whitespace():
    assert parse("  BLOCK   Guest   FROM   SERVER  ") == parse("block guest from server")


def test_filler_words_and_plurals_ignored():
    assert parse("Please block all guests from the servers") == parse("block guest from server")
    assert parse("block traffic from guest to server") == parse("block guest from server")
    assert parse("disable host h3") == parse("disable h3")
    assert parse("block traffic between h2 and h5") == parse("block h2 and h5")


def test_trailing_punctuation():
    assert parse("disable h3!") == parse("disable h3")
    assert parse("block guest from server.") == parse("block guest from server")


def test_every_result_has_all_six_keys():
    for text in ("block guest from server", "block h1 and h2", "isolate h4",
                 "disable h3", "enable h3", "allow h1 and h2", "remove intent 1"):
        assert set(parse(text)) == POLICY_KEYS


@pytest.mark.parametrize("text", [
    "",                           # empty
    "   ",                        # whitespace only
    "do something weird",         # unknown command
    "hello",                      # unknown command
    "block",                      # nothing to block
    "block guest",                # needs two entities
    "block guest from",           # incomplete
    "block guest from nobody",    # unknown group
    "block h1 and h9",            # unknown host
    "disable h9",                 # unknown host
    "disable",                    # missing target
    "disable h1 h2",              # too many targets
    "isolate",                    # missing target
    "enable martians",            # unknown target
    "remove",                     # missing number
    "remove intent",              # missing number
    "remove intent abc",          # not a number
    "remove intent 0",            # ids start at 1
    "block h1 and h1",            # same host twice
    "12345 !!!",                  # nonsense
])
def test_garbage_raises_value_error(text):
    with pytest.raises(ValueError):
        parse(text)


def test_none_raises_value_error():
    with pytest.raises(ValueError):
        parse(None)


def test_error_message_is_helpful():
    with pytest.raises(ValueError) as exc:
        parse("do something weird")
    msg = str(exc.value)
    assert "do" in msg and "block GROUP from GROUP" in msg   # names the bad word + shows usage

    with pytest.raises(ValueError) as exc:
        parse("disable h9")
    assert "h9" in str(exc.value)
