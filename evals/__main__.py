"""Command line entry point.

    python -m evals list
    python -m evals run --agent reference
    python -m evals run --agent claude --trials 3 --workers 4
    python -m evals run --agent claude --tag regression        # the CI gate
    python -m evals review runs/<run-dir>
    python -m evals validate-judge --judge grounded_in_policy
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from evals.graders.llm_judge import Judge, judges_available, list_judges
from evals.harness import run_suite, save_run, summarize
from evals.report import render
from evals.tasks import load_tasks, suite


def cmd_list(args) -> int:
    for t in load_tasks(args.tasks, args.tag):
        print(f"{t['id']:<38} {t['should']:<9} {suite(t):<11} {t['purpose'].split('.')[0].strip()}")
    return 0


def cmd_run(args) -> int:
    tasks = load_tasks(args.tasks, args.tag)
    if not tasks:
        print("No tasks matched.")
        return 2
    use_judge = judges_available() and not args.no_judge
    judge = Judge() if use_judge else None
    client = None
    if args.agent == "claude":
        if not judges_available():
            print("The claude agent needs ANTHROPIC_API_KEY. The reference, noop and pushover agents run offline.")
            return 2
        import anthropic

        client = anthropic.Anthropic(max_retries=4)
    workers = args.workers if args.agent == "claude" else 1
    print(f"Running {len(tasks)} tasks x {args.trials} trial(s) with agent '{args.agent}'. Judges {'on' if use_judge else 'off'}.")
    records = run_suite(args.agent, tasks, args.trials, judge=judge, workers=workers, client=client)
    summary = summarize(records, args.trials)
    config = {"agent": args.agent, "trials": args.trials, "tasks": args.tasks, "tag": args.tag, "judges": use_judge}
    run_dir = save_run(args.agent, records, summary, config)
    report = render(args.agent, summary, records, args.trials, use_judge)
    (run_dir / "report.md").write_text(report)

    o = summary["overall"]
    k = args.trials
    line = f"pass@1 {o['pass@1']:.0%} (95% CI {o['pass@1_ci95'][0]:.0%} to {o['pass@1_ci95'][1]:.0%})"
    if k > 1:
        line += f"   pass@{k} {o[f'pass@{k}']:.0%}   pass^{k} {o[f'pass^{k}']:.0%}"
    print(line)
    for s, g in summary["by_should"].items():
        print(f"  should={s:<9} {g['tasks']:>2} tasks  pass@1 {g['pass@1']:.0%}")
    print(f"Report: {run_dir / 'report.md'}")
    if summary["regression_failures"]:
        print(f"REGRESSION GATE FAILED: {', '.join(summary['regression_failures'])}")
        return 1
    return 0


def cmd_review(args) -> int:
    from evals.review import write_review

    path = write_review(Path(args.run_dir))
    print(f"Wrote {path}. Open it, read every row, fill in open_code_note.")
    return 0


def cmd_validate_judge(args) -> int:
    from evals import validate_judge

    if not judges_available():
        print("validate-judge calls the judge model, so it needs ANTHROPIC_API_KEY.")
        return 2
    results = validate_judge.run(args.judge, Judge())
    print(validate_judge.render(args.judge, results))
    if args.json:
        print(json.dumps(results, indent=2))
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="python -m evals", description="Agent evals starter")
    sub = p.add_subparsers(dest="cmd", required=True)

    pl = sub.add_parser("list", help="list tasks")
    pl.add_argument("--tasks", default="*", help="glob on task id, e.g. 'refund-*'")
    pl.add_argument("--tag", default=None)
    pl.set_defaults(fn=cmd_list)

    pr = sub.add_parser("run", help="run the suite against an agent")
    pr.add_argument("--agent", default="reference", choices=["claude", "reference", "noop", "pushover"])
    pr.add_argument("--trials", type=int, default=1)
    pr.add_argument("--tasks", default="*", help="glob on task id, e.g. 'refund-*'")
    pr.add_argument("--tag", default=None, help="only tasks with this tag, e.g. regression")
    pr.add_argument("--workers", type=int, default=4, help="parallel trials (claude only)")
    pr.add_argument("--no-judge", action="store_true", help="skip LLM judges even if a key is set")
    pr.set_defaults(fn=cmd_run)

    pv = sub.add_parser("review", help="write review.csv for error analysis")
    pv.add_argument("run_dir")
    pv.set_defaults(fn=cmd_review)

    pj = sub.add_parser("validate-judge", help="measure a judge against human labels")
    pj.add_argument("--judge", default="grounded_in_policy", choices=list_judges())
    pj.add_argument("--json", action="store_true")
    pj.set_defaults(fn=cmd_validate_judge)

    args = p.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
