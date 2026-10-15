# orchestrator/tests/test_parser.py
# Owner: Varun
# Purpose: Unit tests for orchestrator/parser.py
#
# TODO (Varun): write one test per intent pattern in section 4.5, plus tests
# for garbage input (must raise ValueError with a clear message).
#
# Example skeleton:
#
# import pytest
# from orchestrator.parser import parse
#
# def test_block_group_from_group():
#     policy = parse("block guest from server")
#     assert policy["action"] == "block"
#     assert policy["src"] == "guest"
#     assert policy["dst"] == "server"
#     assert policy["two_way"] is False
#
# def test_block_and():
#     policy = parse("block h2 and h5")
#     assert policy["action"] == "block"
#     assert policy["two_way"] is True
#
# def test_isolate():
#     policy = parse("isolate h4")
#     assert policy["action"] == "isolate"
#     assert policy["target"] == "h4"
#
# def test_disable():
#     policy = parse("disable h3")
#     assert policy["action"] == "disable"
#     assert policy["target"] == "h3"
#
# def test_deactivate_alias():
#     policy = parse("deactivate h3")
#     assert policy["action"] == "disable"
#
# def test_enable():
#     policy = parse("enable h3")
#     assert policy["action"] == "enable"
#
# def test_remove():
#     policy = parse("remove intent 5")
#     assert policy["action"] == "remove"
#     assert policy["intent_id"] == 5
#
# def test_garbage_raises():
#     with pytest.raises(ValueError):
#         parse("do something weird")
