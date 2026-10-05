"""Error analysis: dump a run into a spreadsheet you read by hand.

This is the step every serious practitioner says matters most and most teams
skip. Open review.csv, read each trial, and write a short note in
open_code_note about the FIRST thing that went wrong (open coding). When you
have 30 or so notes, group them into a handful of categories and fill in
failure_category (axial coding). Count the categories. The biggest bucket is
your next fix, and often your next task or grader.

docs/failure_taxonomy_template.md has a template for the grouping step.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path


def write_review(run_dir: Path) -> Path:
    out = run_dir / "review.csv"
    rows = []
    for path in sorted((run_dir / "transcripts").glob("*.json")):
        r = json.loads(path.read_text())
        t = r["transcript"]
        convo = []
        for e in t["events"]:
            if e["type"] == "user":
                convo.append(f"CUSTOMER: {e['text']}")
            elif e["type"] == "assistant":
                convo.append(f"AGENT: {e['text']}")
            else:
                flag = " (error)" if e["is_error"] else ""
                convo.append(f"  -> {e['name']}({json.dumps(e['args'])}){flag}")
        rows.append({
            "task_id": r["task_id"],
            "trial": r["trial"],
            "should": r["should"],
            "passed": r["passed"],
            "failed_graders": "; ".join(f"{g['grader']}: {g['detail']}" for g in r["graders"] if g["status"] == "fail"),
            "state_changes": json.dumps(r.get("final_state_changes", {})),
            "conversation": "\n".join(convo),
            "open_code_note": "",
            "failure_category": "",
        })
    with out.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else ["task_id"])
        writer.writeheader()
        writer.writerows(rows)
    return out
