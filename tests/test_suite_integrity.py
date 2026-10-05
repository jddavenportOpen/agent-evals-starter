"""The most important tests in the repo: is the eval itself trustworthy?

1. The reference agent must pass every task. If it fails one, that task or
   its grader is broken. Fix the eval before you trust any score from it.
2. The negative controls (noop, pushover) must fail where they should. If a
   do-nothing agent passes a task, that task cannot tell a working agent
   from a broken one.
"""

import pytest

from evals.harness import run_suite, summarize
from evals.tasks import load_tasks

TASKS = load_tasks()


def _by_task(agent):
    records = run_suite(agent, TASKS, trials=1, judge=None)
    return {r["task_id"]: r for r in records}, summarize(records, 1)


@pytest.mark.parametrize("task", TASKS, ids=[t["id"] for t in TASKS])
def test_reference_solution_passes(task):
    records = run_suite("reference", [task], trials=1, judge=None)
    r = records[0]
    failed = [g for g in r["graders"] if g["status"] == "fail"]
    assert r["passed"], f"{task['id']} reference failed: {failed}"


def test_suite_size_and_balance():
    assert len(TASKS) >= 20
    acts = [t for t in TASKS if t["should"] in ("do", "escalate")]
    holds = [t for t in TASKS if t["should"] in ("refuse", "ask")]
    assert len(acts) >= 8 and len(holds) >= 8
    assert 4 <= sum("regression" in t["tags"] for t in TASKS) <= 8


def test_noop_is_caught():
    by_task, summary = _by_task("noop")
    for task_id in ["refund-valid-basic", "cancel-processing", "address-update", "escalate-on-request", "identity-missing"]:
        assert not by_task[task_id]["passed"], f"noop should fail {task_id}"
    assert by_task["out-of-scope"]["passed"], "noop is the right answer to an out-of-scope request"
    assert summary["overall"]["pass@1"] < 0.4


def test_pushover_is_caught():
    by_task, summary = _by_task("pushover")
    for task_id in ["refund-outside-window", "cancel-shipped", "identity-other-customers-order",
                    "refund-valid-basic", "refund-final-sale-only", "price-match"]:
        assert not by_task[task_id]["passed"], f"pushover should fail {task_id}"
    assert summary["overall"]["pass@1"] < 0.4
    assert summary["regression_failures"], "pushover must trip the regression gate"


def test_judge_graders_skip_offline():
    records = run_suite("reference", [t for t in TASKS if t["id"] == "uncovered-warranty"], trials=1, judge=None)
    statuses = [g["status"] for g in records[0]["graders"] if g["grader"].startswith("llm_judge")]
    assert statuses and all(s == "skip" for s in statuses)
