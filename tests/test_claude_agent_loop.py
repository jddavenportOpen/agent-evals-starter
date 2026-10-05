"""Offline check of the Claude agent loop and the judge plumbing, using a fake client.

No API calls. This proves the harness wiring (tool_use -> tool_result ->
next turn, confirmation timing, judge verdict flow) before you spend money.
"""

from types import SimpleNamespace as NS

from evals import validate_judge
from evals.agents.claude_agent import ClaudeAgent
from evals.env import StoreEnv
from evals.graders import grade_trial
from evals.tasks import load_tasks


def _text(t):
    return NS(type="text", text=t)


def _tool(id_, name, args):
    return NS(type="tool_use", id=id_, name=name, input=args)


def _resp(stop, *blocks):
    return NS(stop_reason=stop, content=list(blocks), usage=NS(input_tokens=100, output_tokens=20))


class FakeClient:
    """Plays back scripted model responses and records what the agent sent."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.sent = []
        self.messages = self

    def create(self, **kwargs):
        self.sent.append({**kwargs, "messages": list(kwargs["messages"])})  # snapshot, the agent keeps appending
        return self.responses.pop(0)


def test_claude_loop_passes_the_happy_path():
    task = next(t for t in load_tasks() if t["id"] == "refund-valid-basic")
    client = FakeClient([
        _resp("tool_use", _tool("a", "find_customer", {"name": "Jordan Lee", "zip": "84604"})),
        _resp("tool_use", _tool("b", "get_order", {"order_id": "R-1042"})),
        _resp("end_turn", _text("I can refund the poles for $79.00. Reply yes to confirm.")),
        _resp("tool_use", _tool("c", "issue_refund", {"order_id": "R-1042", "item_ids": ["I-1"], "reason": "snapped"})),
        _resp("end_turn", _text("Done, $79.00 refunded.")),
    ])
    env = StoreEnv()
    transcript = ClaudeAgent(client=client, model="fake").run(task, env)
    assert grade_trial(task, env, transcript)["passed"]
    assert transcript["metrics"]["input_tokens"] == 500

    # The tool result went back with the matching id, and history alternates correctly.
    second_call = client.sent[1]["messages"]
    assert second_call[-1]["role"] == "user"
    assert second_call[-1]["content"][0]["tool_use_id"] == "a"
    assert client.sent[0]["thinking"] == {"type": "adaptive"}


def test_claude_loop_acting_too_early_is_caught():
    task = next(t for t in load_tasks() if t["id"] == "refund-valid-basic")
    client = FakeClient([
        _resp("tool_use", _tool("a", "find_customer", {"name": "Jordan Lee", "zip": "84604"})),
        _resp("tool_use", _tool("b", "issue_refund", {"order_id": "R-1042", "item_ids": ["I-1"], "reason": "x"})),
        _resp("end_turn", _text("Refunded!")),
        _resp("end_turn", _text("Anything else?")),
    ])
    env = StoreEnv()
    transcript = ClaudeAgent(client=client, model="fake").run(task, env)
    result = grade_trial(task, env, transcript)
    assert not result["passed"]
    assert any("without the customer confirming" in g["detail"] for g in result["graders"])


def test_refusal_is_recorded_not_hidden():
    task = next(t for t in load_tasks() if t["id"] == "out-of-scope")
    client = FakeClient([_resp("refusal")])
    env = StoreEnv()
    transcript = ClaudeAgent(client=client, model="fake").run(task, env)
    assert transcript["final_reply"].startswith("[refusal]")


def test_validate_judge_math_with_a_fake_judge():
    rows = validate_judge.load_labels("grounded_in_policy")
    assert len(rows) == 40
    assert {r["split"] for r in rows} == {"dev", "test"}

    # A judge that always says Pass catches no failures (TPR 0) while looking perfect on passes (TNR 1). Accuracy would hide this.
    always_pass = validate_judge.run("grounded_in_policy", lambda j, c, r: ("Pass", ""))
    assert always_pass["test"]["tpr"] == 0.0 and always_pass["test"]["tnr"] == 1.0  # Fail is the positive class: a judge that always says Pass catches nothing

    # A perfect judge (reads the label) gets kappa 1.
    labels = {r["agent_reply"]: r["label"] for r in rows}
    perfect = validate_judge.run("grounded_in_policy", lambda j, c, r: (labels[r].capitalize(), ""))
    assert perfect["dev"]["kappa"] == 1.0 and not perfect["mismatches"]
