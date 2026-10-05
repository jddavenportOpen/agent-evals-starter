"""Validate an LLM judge against human labels before you trust it.

A judge is a model, and models are wrong in patterned ways. So you treat the
judge like any model you would ship: hold out labeled data and measure it.

judges/labels/<judge>.csv has hand-labeled examples split into dev (iterate
on the judge prompt while looking at these) and test (look at these ONCE, at
the end). We report:

  TPR  of the replies a human marked Pass, how many did the judge pass?
  TNR  of the replies a human marked Fail, how many did the judge fail?
  Cohen's kappa  agreement beyond chance

Positive class here = Pass. Write that down; write-ups disagree on it.
Accuracy alone hides a judge that passes everything: on a set with 90%
passes, "always Pass" scores 90% accuracy and 0% TNR.
"""

from __future__ import annotations

import csv

from evals.env import ROOT
from evals.metrics import cohen_kappa


def load_labels(judge: str) -> list[dict]:
    path = ROOT / "judges" / "labels" / f"{judge}.csv"
    with path.open() as f:
        return list(csv.DictReader(f))


def score(rows: list[dict], verdicts: list[str]) -> dict:
    """Positive class = Fail: the judge's job is to catch failures.

    TPR = of the human Fails, the share the judge called Fail (failures caught).
    TNR = of the human Passes, the share the judge called Pass (no false alarms).
    Unknown is an abstention: counted separately, never as Pass, and left out
    of TPR/TNR (so report coverage next to them).
    """
    tp = fn = fp = tn = 0
    unknown_on_fail = unknown_on_pass = 0
    for row, v in zip(rows, verdicts):
        human_fail = row["label"].strip().lower() == "fail"
        if v == "Unknown":
            if human_fail:
                unknown_on_fail += 1
            else:
                unknown_on_pass += 1
            continue
        judge_fail = v != "Pass"
        if human_fail and judge_fail:
            tp += 1
        elif human_fail:
            fn += 1
        elif judge_fail:
            fp += 1
        else:
            tn += 1
    decided = tp + fn + fp + tn
    return {
        "n": len(rows), "tp": tp, "fn": fn, "fp": fp, "tn": tn,
        "unknown": unknown_on_fail + unknown_on_pass,
        "unknown_on_fail": unknown_on_fail, "unknown_on_pass": unknown_on_pass,
        "coverage": decided / len(rows) if rows else 0.0,
        "tpr": tp / (tp + fn) if tp + fn else 0.0,
        "tnr": tn / (tn + fp) if tn + fp else 0.0,
        "kappa": cohen_kappa(tp, fn, fp, tn),
    }


def run(judge_name: str, judge) -> dict:
    rows = load_labels(judge_name)
    results = {}
    mismatches = []
    for split in ("dev", "test"):
        subset = [r for r in rows if r["split"] == split]
        verdicts = []
        for r in subset:
            conversation = f"CUSTOMER: {r['customer_message']}\nAGENT: {r['agent_reply']}"
            v, critique = judge(judge_name, conversation, r["agent_reply"])
            verdicts.append(v)
            if (v == "Pass") != (r["label"].strip().lower() == "pass"):
                mismatches.append({"id": r["id"], "split": split, "human": r["label"], "judge": v, "critique": critique})
        results[split] = score(subset, verdicts)
    results["mismatches"] = mismatches
    return results


def render(judge_name: str, results: dict) -> str:
    lines = [f"Judge: {judge_name}   (positive class = Fail: TPR = failures caught, TNR = passes left alone)", ""]
    for split in ("dev", "test"):
        s = results[split]
        lines += [
            f"[{split}] n={s['n']}  TPR={s['tpr']:.0%}  TNR={s['tnr']:.0%}  kappa={s['kappa']:.2f}  coverage={s['coverage']:.0%}  unknown={s['unknown']}",
            "             judge Fail  judge Pass",
            f"  human Fail  {s['tp']:>10}  {s['fn']:>10}",
            f"  human Pass  {s['fp']:>10}  {s['tn']:>10}",
            f"  With ~{min(s['tp']+s['fn'], s['fp']+s['tn'])} examples per class this is a rough estimate. Aim for 30 to 50 per class in test.",
            "",
        ]
    if results["mismatches"]:
        lines.append("Disagreements (read these; sometimes the human label is the one that is wrong):")
        for m in results["mismatches"]:
            lines.append(f"  {m['split']} #{m['id']}: human={m['human']} judge={m['judge']} :: {m['critique'][:240]}")
    return "\n".join(lines)
