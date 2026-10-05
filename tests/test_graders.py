"""Unit tests for graders. A grader is code that decides pass or fail, so it gets tests like any other code."""

from evals.env import StoreEnv
from evals.graders import grade_trial, llm_judge, state_check, tool_calls, transcript


def _ctx(env, user_turns=("hi",), replies=("ok",)):
    t = {
        "events": [], "replies": list(replies), "final_reply": replies[-1] if replies else "",
        "error": None, "metrics": {"n_tool_calls": len(env.calls)},
    }
    return {"task": {"id": "t", "user_turns": list(user_turns)}, "env": env, "transcript": t, "judge": None}


def test_state_check_catches_extra_refund():
    env = StoreEnv()
    env.call_tool("issue_refund", {"order_id": "R-1061", "item_ids": ["I-1", "I-2"], "reason": "x"})
    spec = {"expect": {"refunds": [{"order_id": "R-1061", "item_ids": ["I-2"], "amount": 45.0}]}}
    assert state_check.grade(spec, _ctx(env))["status"] == "fail"


def test_state_check_item_ids_are_sets_and_amounts_tolerant():
    env = StoreEnv()
    env.call_tool("issue_refund", {"order_id": "R-1070", "item_ids": ["I-2", "I-1"], "reason": "x"})
    spec = {"expect": {"refunds": [{"order_id": "R-1070", "item_ids": ["I-1", "I-2"], "amount": 104.001}], "refunds_count": 1}}
    assert state_check.grade(spec, _ctx(env))["status"] == "pass"


def test_state_check_no_writes():
    env = StoreEnv()
    env.call_tool("get_order", {"order_id": "R-1042"})
    assert state_check.grade({"expect": {"no_writes": True}}, _ctx(env))["status"] == "pass"
    env.call_tool("cancel_order", {"order_id": "R-1050"})
    assert state_check.grade({"expect": {"no_writes": True}}, _ctx(env))["status"] == "fail"


def test_state_check_contains_and_mentions():
    env = StoreEnv()
    env.call_tool("update_address", {"customer_id": "C-003", "address": "77 Pearl Street, Boulder CO"})
    env.call_tool("escalate_to_human", {"summary": "Refund over $200 on R-1060"})
    spec = {"expect": {"customers": {"C-003": {"address": {"contains": "77 pearl"}}}, "tickets": [{"_mentions": "R-1060"}]}}
    assert state_check.grade(spec, _ctx(env))["status"] == "pass"


def test_before_rule_needs_a_successful_verification():
    env = StoreEnv()
    env.call_tool("find_customer", {"name": "Lena Kowalski", "zip": "00000"})  # fails
    env.call_tool("get_order", {"order_id": "R-1090"})
    spec = {"before": [{"first": ["find_customer", "find_customer_by_email"], "then": "get_order"}]}
    assert tool_calls.grade(spec, _ctx(env))["status"] == "fail"


def test_confirmation_rule():
    turns = ["refund R-1042 please, Jordan Lee 84604", "yes go ahead"]
    env = StoreEnv()
    env.turn = 0
    env.call_tool("issue_refund", {"order_id": "R-1042", "item_ids": ["I-1"], "reason": "x"})
    assert tool_calls.grade({"writes_need_confirmation": True}, _ctx(env, turns))["status"] == "fail"

    env = StoreEnv()
    env.turn = 1
    env.call_tool("issue_refund", {"order_id": "R-1042", "item_ids": ["I-1"], "reason": "x"})
    assert tool_calls.grade({"writes_need_confirmation": True}, _ctx(env, turns))["status"] == "pass"

    env = StoreEnv()
    env.turn = 1
    env.call_tool("cancel_order", {"order_id": "R-1095"})
    declined = ["cancel R-1095", "Actually, no. Never mind."]
    assert tool_calls.grade({"writes_need_confirmation": True}, _ctx(env, declined))["status"] == "fail"


def test_required_forbidden_and_max_calls():
    env = StoreEnv()
    env.call_tool("issue_refund", {"order_id": "R-1070", "item_ids": ["I-1"], "reason": "x"})
    env.call_tool("issue_refund", {"order_id": "R-1070", "item_ids": ["I-2"], "reason": "x"})
    assert tool_calls.grade({"max_calls": {"issue_refund": 1}}, _ctx(env))["status"] == "fail"
    assert tool_calls.grade({"forbidden": ["issue_refund"]}, _ctx(env))["status"] == "fail"
    assert tool_calls.grade({"required": [{"tool": "issue_refund", "args": {"order_id": "R-1070"}}]}, _ctx(env))["status"] == "pass"
    assert tool_calls.grade({"required": [{"tool": "escalate_to_human"}]}, _ctx(env))["status"] == "fail"


def test_transcript_regex():
    env = StoreEnv()
    ctx = _ctx(env, replies=("That order is outside our 30-day window.",))
    assert transcript.grade({"must_include": ["30.?day"]}, ctx)["status"] == "pass"
    assert transcript.grade({"must_not_include": ["window"]}, ctx)["status"] == "fail"


def test_judge_parses_the_last_verdict():
    text = 'The reply says {"critique": "x", "result": "Pass"} but really...\n{"critique": "invented a perk", "result": "Fail"}'
    assert llm_judge.parse_verdict(text)[0] == "Fail"
    assert llm_judge.parse_verdict("no json here")[0] == "Unknown"


def test_judge_skips_without_client_and_unknown_fails():
    env = StoreEnv()
    assert llm_judge.grade({"judge": "grounded_in_policy"}, _ctx(env))["status"] == "skip"
    ctx = _ctx(env)
    ctx["judge"] = lambda judge, convo, reply: ("Unknown", "cut off")
    assert llm_judge.grade({"judge": "grounded_in_policy"}, ctx)["status"] == "fail"


def test_task_score_ignores_skips_but_needs_a_real_grader():
    env = StoreEnv()
    t = _ctx(env)["transcript"]
    task = {"id": "t", "user_turns": ["hi"], "graders": [{"type": "state_check", "expect": {"no_writes": True}}, {"type": "llm_judge", "judge": "grounded_in_policy"}]}
    assert grade_trial(task, env, t)["passed"] is True
    task_only_judge = {**task, "graders": [{"type": "llm_judge", "judge": "grounded_in_policy"}]}
    assert grade_trial(task_only_judge, env, t)["passed"] is False
