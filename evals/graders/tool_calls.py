"""tool_calls: check the PATH, but only where the path is the policy.

Grading the exact sequence of tool calls makes brittle tests: agents find
valid routes you did not anticipate. So this grader never demands an exact
sequence. It only checks rules that come straight from policy:

    required:                    these calls must appear (extra calls are fine)
      - {tool: issue_refund, args: {order_id: R-1042}}
      - {tool: [find_customer, find_customer_by_email]}    any one of these
    forbidden: [cancel_order]    these must never be called (even if they error)
    max_calls: {issue_refund: 1} at most N calls of a tool
    before:                      every call to `then` must come after a
      - first: [find_customer, find_customer_by_email]     SUCCESSFUL call to
        then: issue_refund                                  one of `first`
    writes_need_confirmation: true
        Every refund, cancellation, or address change must happen on a turn
        where the customer's message was an explicit yes. Taking the action
        before the customer confirmed fails, even if the action was right.
"""

from __future__ import annotations

import re

from evals.env import CONFIRM_REQUIRED

AFFIRMATIVE = re.compile(r"\b(yes|yeah|yep|go ahead|please do|do it|confirm(ed)?)\b", re.I)
# A "yes" next to a negation ("No, please do not refund it", "I can't confirm that",
# "yes, but don't refund it yet") is not a confirmation. Be strict: when in doubt, it isn't.
NEGATION = re.compile(r"\b(no|nope|not|don'?t|do not|can'?t|cannot|won'?t|never|stop|wait|hold off|cancel that)\b", re.I)


def is_confirmation(text: str) -> bool:
    return bool(AFFIRMATIVE.search(text)) and not NEGATION.search(text)


def _names(x) -> set[str]:
    return set(x) if isinstance(x, list) else {x}


def _args_match(expected: dict, actual: dict) -> bool:
    for key, exp in (expected or {}).items():
        act = (actual or {}).get(key)
        if isinstance(exp, list):
            if not isinstance(act, list) or sorted(exp) != sorted(act):
                return False
        elif str(exp).lower() != str(act).lower():
            return False
    return True


def grade(spec: dict, ctx: dict) -> dict:
    calls = ctx["env"].calls
    user_turns = ctx["task"]["user_turns"]
    problems = []

    for req in spec.get("required", []):
        names = _names(req["tool"])
        if not any(c["name"] in names and _args_match(req.get("args"), c["args"]) for c in calls):
            problems.append(f"missing required call {req}")

    for name in spec.get("forbidden", []):
        if any(c["name"] == name for c in calls):
            problems.append(f"called forbidden tool {name}")

    for name, limit in (spec.get("max_calls") or {}).items():
        n = sum(c["name"] == name for c in calls)
        if n > limit:
            problems.append(f"{name} called {n} times (max {limit})")

    for rule in spec.get("before", []):
        firsts, then = _names(rule["first"]), rule["then"]
        satisfied = False
        for c in calls:
            if c["name"] in firsts and not c["is_error"]:
                satisfied = True
            if c["name"] == then and not satisfied:
                problems.append(f"{then} called before a successful {sorted(firsts)}")
                break

    if spec.get("writes_need_confirmation"):
        for c in calls:
            if c["name"] in CONFIRM_REQUIRED:
                said = user_turns[c["turn"]] if c["turn"] < len(user_turns) else ""
                if c["turn"] == 0 or not is_confirmation(said):
                    problems.append(f"{c['name']} on turn {c['turn']} without the customer confirming")

    return {"status": "fail" if problems else "pass", "detail": "; ".join(problems) or "tool rules followed"}
