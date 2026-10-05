"""The evaluation harness: runs tasks x trials, grades them, saves everything.

Each trial gets a fresh StoreEnv and a fresh agent, so nothing leaks between
trials. (Anthropic found Claude "gaining an unfair advantage" in internal evals
by reading git history left over from earlier trials. Isolation matters.)
"""

from __future__ import annotations

import json
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from evals.agents import make_agent
from evals.env import ROOT, StoreEnv
from evals.graders import grade_trial
from evals.metrics import pass_at_k, pass_hat_k, wilson_interval
from evals.tasks import suite


def run_trial(agent_name: str, task: dict, trial: int, judge=None, client=None) -> dict:
    env = StoreEnv(task.get("initial_state"))
    kwargs = {"client": client} if (agent_name == "claude" and client is not None) else {}
    agent = make_agent(agent_name, **kwargs)
    transcript = agent.run(task, env)
    grades = grade_trial(task, env, transcript, judge=judge)
    return {
        "task_id": task["id"],
        "trial": trial,
        "should": task["should"],
        "suite": suite(task),
        "passed": grades["passed"],
        "graders": grades["graders"],
        "metrics": transcript["metrics"],
        "error": transcript["error"],
        "transcript": transcript,
        "final_state_changes": _diff(env.initial, env.state),
    }


def _diff(before: dict, after: dict) -> dict:
    out = {}
    for table in after:
        if before.get(table) == after[table]:
            continue
        if isinstance(after[table], list):
            out[table] = after[table][len(before.get(table, [])):]
        else:
            out[table] = {k: v for k, v in after[table].items() if before.get(table, {}).get(k) != v}
    return out


def run_suite(agent_name: str, tasks: list[dict], trials: int = 1, judge=None, workers: int = 1, client=None) -> list[dict]:
    jobs = [(task, t) for task in tasks for t in range(trials)]
    if workers <= 1:
        return [run_trial(agent_name, task, t, judge, client) for task, t in jobs]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(lambda j: run_trial(agent_name, j[0], j[1], judge, client), jobs))


def summarize(records: list[dict], trials: int) -> dict:
    by_task = defaultdict(list)
    for r in records:
        by_task[r["task_id"]].append(r)

    per_task = {}
    for task_id, rs in by_task.items():
        n, c = len(rs), sum(r["passed"] for r in rs)
        per_task[task_id] = {
            "n": n, "c": c, "should": rs[0]["should"], "suite": rs[0]["suite"],
            "pass_rate": c / n,
            f"pass@{trials}": pass_at_k(n, c, trials),
            f"pass^{trials}": pass_hat_k(n, c, trials),
        }

    def group(key=None, value=None) -> dict:
        rows = [v for v in per_task.values() if key is None or v[key] == value]
        if not rows:
            return {}
        trials_total = sum(v["n"] for v in rows)
        passes = sum(v["c"] for v in rows)
        lo, hi = wilson_interval(passes, trials_total)
        return {
            "tasks": len(rows),
            "trials": trials_total,
            "pass@1": sum(v["pass_rate"] for v in rows) / len(rows),
            "pass@1_ci95": [lo, hi],
            f"pass@{trials}": sum(v[f"pass@{trials}"] for v in rows) / len(rows),
            f"pass^{trials}": sum(v[f"pass^{trials}"] for v in rows) / len(rows),
        }

    graders = defaultdict(lambda: {"pass": 0, "fail": 0, "skip": 0})
    for r in records:
        for g in r["graders"]:
            graders[g["grader"]][g["status"]] += 1

    tokens = {k: sum(r["metrics"].get(k, 0) for r in records) for k in ("input_tokens", "output_tokens")}
    regression_failures = sorted({r["task_id"] for r in records if r["suite"] == "regression" and not r["passed"]})
    return {
        "overall": group(),
        "by_should": {s: group("should", s) for s in sorted({v["should"] for v in per_task.values()})},
        "by_suite": {s: group("suite", s) for s in ("capability", "regression") if group("suite", s)},
        "per_task": per_task,
        "graders": dict(graders),
        "zero_pass_tasks": sorted(t for t, v in per_task.items() if v["c"] == 0),
        "regression_failures": regression_failures,
        "tokens": tokens,
        "avg_tool_calls": sum(r["metrics"]["n_tool_calls"] for r in records) / max(1, len(records)),
    }


def save_run(agent_name: str, records: list[dict], summary: dict, config: dict, out_root: Path | None = None) -> Path:
    out_root = out_root or ROOT / "runs"
    run_dir = out_root / f"{time.strftime('%Y%m%d-%H%M%S')}-{agent_name}"
    (run_dir / "transcripts").mkdir(parents=True, exist_ok=True)
    for r in records:
        path = run_dir / "transcripts" / f"{r['task_id']}__trial{r['trial']}.json"
        path.write_text(json.dumps(r, indent=2, default=str))
    slim = [{k: v for k, v in r.items() if k != "transcript"} for r in records]
    (run_dir / "results.json").write_text(json.dumps({"config": config, "summary": summary, "trials": slim}, indent=2, default=str))
    return run_dir
