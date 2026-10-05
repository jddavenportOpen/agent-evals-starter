"""Load and sanity check tasks from tasks/*.yaml."""

from __future__ import annotations

import fnmatch

import yaml

from evals.env import ROOT

SHOULD_TYPES = {"do", "refuse", "escalate", "ask"}
REQUIRED_FIELDS = ["id", "purpose", "tags", "should", "user_turns", "reference_solution", "graders"]


def load_tasks(pattern: str = "*", tag: str | None = None) -> list[dict]:
    tasks = []
    for path in sorted((ROOT / "tasks").glob("*.yaml")):
        task = yaml.safe_load(path.read_text())
        missing = [f for f in REQUIRED_FIELDS if f not in task]
        if missing:
            raise ValueError(f"{path.name}: missing fields {missing}")
        if task["should"] not in SHOULD_TYPES:
            raise ValueError(f"{path.name}: should must be one of {sorted(SHOULD_TYPES)}")
        if len(task["reference_solution"]) != len(task["user_turns"]):
            raise ValueError(f"{path.name}: reference_solution needs one step per user turn")
        task["_file"] = path.name
        tasks.append(task)
    ids = [t["id"] for t in tasks]
    dupes = {i for i in ids if ids.count(i) > 1}
    if dupes:
        raise ValueError(f"duplicate task ids: {dupes}")
    tasks = [t for t in tasks if fnmatch.fnmatch(t["id"], pattern)]
    if tag:
        tasks = [t for t in tasks if tag in t["tags"]]
    return tasks


def suite(task: dict) -> str:
    return "regression" if "regression" in task["tags"] else "capability"
