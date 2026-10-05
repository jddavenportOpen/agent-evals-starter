"""Turn a run's summary into report.md. Read the failures section first."""

from __future__ import annotations


def _pct(x: float) -> str:
    return f"{100 * x:.0f}%"


def render(agent: str, summary: dict, records: list[dict], trials: int, judges_on: bool) -> str:
    k = trials
    o = summary["overall"]
    lo, hi = o["pass@1_ci95"]
    lines = [
        f"# Eval report: {agent}",
        "",
        f"{o['tasks']} tasks x {trials} trial(s) = {o['trials']} trials. LLM judges: {'on' if judges_on else 'OFF (skipped, not passed)'}.",
        "",
        *([f"**{sum(1 for r in records if r.get('judge_skipped') and r['passed'])} passing trials had an LLM judge skipped.** Offline scores are an upper bound: those trials were only checked by code.", ""] if not judges_on else []),
        "## Headline",
        "",
        f"- **pass@1: {_pct(o['pass@1'])}** (95% CI {_pct(lo)} to {_pct(hi)})",
    ]
    if trials > 1:
        lines += [
            f"- pass@{k}: {_pct(o[f'pass@{k}'])} (at least one of {k} tries succeeds)",
            f"- **pass^{k}: {_pct(o[f'pass^{k}'])}** (all {k} tries succeed: what a customer who gets one shot experiences)",
        ]
    lines += [
        "",
        "Note: trials of the same task are not independent, so the interval above is optimistic. With 24 tasks at 70%, a 95% interval is about plus or minus 18 points. To compare two versions, compare them task by task on the same tasks (paired), not by eyeballing two headline numbers.",
        "",
        "## By expected behavior",
        "",
        "| should | tasks | pass@1 |" + (f" pass^{k} |" if trials > 1 else ""),
        "|---|---|---|" + ("---|" if trials > 1 else ""),
    ]
    for name, g in summary["by_should"].items():
        lines.append(f"| {name} | {g['tasks']} | {_pct(g['pass@1'])} |" + (f" {_pct(g[f'pass^{k}'])} |" if trials > 1 else ""))
    lines += ["", "## Capability vs regression", "", "| suite | tasks | pass@1 |", "|---|---|---|"]
    for name, g in summary["by_suite"].items():
        lines.append(f"| {name} | {g['tasks']} | {_pct(g['pass@1'])} |")
    if summary["regression_failures"]:
        lines += ["", f"**REGRESSION GATE FAILED:** {', '.join(summary['regression_failures'])}"]
    else:
        lines += ["", "Regression gate: all regression tasks passed every trial."]

    lines += ["", "## Per grader", "", "| grader | pass | fail | skipped |", "|---|---|---|---|"]
    for name, c in sorted(summary["graders"].items()):
        lines.append(f"| {name} | {c['pass']} | {c['fail']} | {c['skip']} |")

    if summary["zero_pass_tasks"] and trials > 1:
        lines += [
            "",
            "## 0% across every trial",
            "",
            "These failed every time. With a capable model that is most often a broken task or grader, not an incapable agent. Read the transcript before you change the prompt:",
            "",
        ] + [f"- {t}" for t in summary["zero_pass_tasks"]]

    lines += ["", "## Per task", "", "| task | should | suite | passed |", "|---|---|---|---|"]
    for t, v in sorted(summary["per_task"].items()):
        lines.append(f"| {t} | {v['should']} | {v['suite']} | {v['c']}/{v['n']} |")

    fails = [r for r in records if not r["passed"]]
    lines += ["", f"## Failures ({len(fails)})", ""]
    for r in sorted(fails, key=lambda r: (r["task_id"], r["trial"])):
        why = "; ".join(f"{g['grader']}: {g['detail']}" for g in r["graders"] if g["status"] == "fail")
        if r.get("error"):
            why = f"agent error: {r['error']}. {why}"
        lines.append(f"- **{r['task_id']}** trial {r['trial']}: {why[:400]}")

    tok = summary["tokens"]
    if tok["input_tokens"]:
        lines += ["", "## Tracked (reported, not graded)", "", f"- tokens: {tok['input_tokens']:,} in, {tok['output_tokens']:,} out"]
    lines += [f"- average tool calls per trial: {summary['avg_tool_calls']:.1f}", ""]
    return "\n".join(lines)
