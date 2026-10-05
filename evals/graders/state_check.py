"""state_check: grade the OUTCOME, the final state of the store.

This is the most important grader in the repo. A reply that says "your
refund is done" means nothing. A refund row in the database means
something. (Anthropic's example: a flight agent can say "your flight has been
booked"; the outcome is whether the reservation exists.)

Supported keys under `expect:`

    no_writes: true                 nothing in the store changed
    unchanged: [orders, customers]  these tables are exactly as they started
    refunds_count: 1                number of rows in a list table
    tickets_count: 0
    refunds:                        each listed row must match some real row
      - {order_id: R-1042, item_ids: [I-1], amount: 79.0}
    tickets:
      - {_mentions: R-1060}         any field of the ticket contains this text
    orders:                         field checks on keyed records
      R-1050: {status: cancelled}
    customers:
      C-003: {address: {contains: "77 Pearl"}}

Matching rules: item_ids compare as sets, numbers within 0.01, strings
case-insensitive. {contains: x} is a case-insensitive substring check.
"""

from __future__ import annotations


def _norm(v):
    return " ".join(v.lower().split()) if isinstance(v, str) else v


def _value_matches(expected, actual) -> bool:
    if isinstance(expected, dict) and "contains" in expected:
        return isinstance(actual, str) and _norm(expected["contains"]) in _norm(actual)
    if isinstance(expected, list) and isinstance(actual, list):
        return sorted(map(str, expected)) == sorted(map(str, actual))
    if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
        return abs(expected - actual) < 0.01
    return _norm(expected) == _norm(actual)


def _row_matches(expected: dict, row: dict) -> bool:
    for key, exp in expected.items():
        if key == "_mentions":
            if not any(isinstance(v, str) and _norm(exp) in _norm(v) for v in row.values()):
                return False
        elif not _value_matches(exp, row.get(key)):
            return False
    return True


def grade(spec: dict, ctx: dict) -> dict:
    expect = spec.get("expect", {})
    initial, final = ctx["env"].initial, ctx["env"].state
    problems = []

    if expect.get("no_writes") and final != initial:
        changed = [t for t in final if final[t] != initial.get(t)]
        problems.append(f"expected no changes, but these changed: {changed}")

    for table in expect.get("unchanged", []):
        if final.get(table) != initial.get(table):
            problems.append(f"{table} changed but should not have")

    for key, value in expect.items():
        if key.endswith("_count"):
            table = key[: -len("_count")]
            n = len(final.get(table, []))
            if n != value:
                problems.append(f"{table}: expected {value} rows, found {n}")

    for table in ("refunds", "tickets"):
        for wanted in expect.get(table, []):
            if not any(_row_matches(wanted, row) for row in final.get(table, [])):
                problems.append(f"no row in {table} matches {wanted}")

    for table in ("orders", "customers"):
        for record_id, fields in (expect.get(table) or {}).items():
            record = final.get(table, {}).get(record_id)
            if record is None:
                problems.append(f"{table}.{record_id} missing")
                continue
            for field, exp in fields.items():
                if not _value_matches(exp, record.get(field)):
                    problems.append(f"{table}.{record_id}.{field} is {record.get(field)!r}, expected {exp!r}")

    return {"status": "fail" if problems else "pass", "detail": "; ".join(problems) or "state as expected"}
