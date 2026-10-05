"""Graders: the logic that scores a trial. Code first, a model judge last.

Each grader is a function grade(spec, ctx) -> {"status": pass|fail|skip, "detail": str}.
ctx holds the task, the env (initial and final state, tool calls), the
transcript, and the judge client (or None when judges are off).
"""

from evals.graders import llm_judge, state_check, tool_calls, transcript

GRADERS = {
    "state_check": state_check.grade,
    "tool_calls": tool_calls.grade,
    "transcript": transcript.grade,
    "llm_judge": llm_judge.grade,
}


def grader_label(spec: dict) -> str:
    """A stable name for reporting, like 'llm_judge:grounded_in_policy'."""
    return f"llm_judge:{spec['judge']}" if spec["type"] == "llm_judge" else spec["type"]


def grade_trial(task: dict, env, transcript_: dict, judge=None) -> dict:
    ctx = {"task": task, "env": env, "transcript": transcript_, "judge": judge}
    results = []
    for spec in task["graders"]:
        if spec["type"] not in GRADERS:
            raise ValueError(f"task {task['id']}: unknown grader type {spec['type']}")
        out = GRADERS[spec["type"]](spec, ctx)
        results.append({"grader": grader_label(spec), **out})
    scored = [r for r in results if r["status"] != "skip"]
    # Binary task score: every grader that ran must pass. An agent error is a fail.
    passed = bool(scored) and all(r["status"] == "pass" for r in scored) and not transcript_.get("error")
    judge_skipped = any(r["status"] == "skip" for r in results)
    return {"passed": passed, "graders": results, "judge_skipped": judge_skipped}
