"""transcript: cheap text checks on what the agent SAID.

Use sparingly. Regex on prose is brittle: there are many correct ways to say
"that's outside our 30-day window". These checks are for facts the customer
must be told (tau-bench calls this "communicate_info"), written loosely.

    must_include: ["30.?day"]          regex, case-insensitive
    must_not_include: ["lifetime warranty"]
    scope: any | final                 check all replies (default) or the last one
    max_tool_calls: 12                 an efficiency budget
"""

from __future__ import annotations

import re


def grade(spec: dict, ctx: dict) -> dict:
    t = ctx["transcript"]
    text = t["final_reply"] if spec.get("scope") == "final" else "\n".join(t["replies"])
    problems = []
    for pattern in spec.get("must_include", []):
        if not re.search(pattern, text, re.I):
            problems.append(f"reply never matched /{pattern}/")
    for pattern in spec.get("must_not_include", []):
        if re.search(pattern, text, re.I):
            problems.append(f"reply matched forbidden /{pattern}/")
    budget = spec.get("max_tool_calls")
    if budget is not None and t["metrics"]["n_tool_calls"] > budget:
        problems.append(f"{t['metrics']['n_tool_calls']} tool calls (budget {budget})")
    return {"status": "fail" if problems else "pass", "detail": "; ".join(problems) or "text checks passed"}
