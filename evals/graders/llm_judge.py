"""llm_judge: a model grades ONE fuzzy criterion. Use it last, not first.

Rules this grader follows (each one comes from practitioners who learned it
the hard way):
  * one criterion per judge (judges/<name>.md), never "rate quality 1 to 10"
  * binary Pass or Fail, plus an "Unknown" way out so it does not guess
  * the critique is written BEFORE the verdict
  * few-shot examples in the prompt, including a borderline one
  * we parse the LAST verdict in the output, so a reply that contains the
    text "result": "Pass" cannot vote for itself
  * the judge itself gets validated against human labels before you trust
    it: python -m evals validate-judge --judge grounded_in_policy

With no API key (or --no-judge) these graders are SKIPPED, never passed.

Settings: EVAL_JUDGE_MODEL (default "claude-opus-5").
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

from evals.env import ROOT, load_policy

JUDGE_DIR = ROOT / "judges"
VERDICT_RE = re.compile(r"\{[^{}]*\"result\"\s*:\s*\"(Pass|Fail|Unknown)\"[^{}]*\}", re.I | re.S)


def judges_available() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))


def render_conversation(events: list[dict]) -> str:
    lines = []
    for e in events:
        if e["type"] == "user":
            lines.append(f"CUSTOMER: {e['text']}")
        elif e["type"] == "assistant":
            lines.append(f"AGENT: {e['text']}")
        else:
            lines.append(f"[tool call] {e['name']}({json.dumps(e['args'])}) -> {e['result'][:400]}")
    return "\n".join(lines)


def build_prompt(judge: str, conversation: str, reply: str) -> str:
    template = (JUDGE_DIR / f"{judge}.md").read_text()
    return (
        template.replace("{{policy}}", load_policy())
        .replace("{{conversation}}", conversation)
        .replace("{{reply}}", reply)
    )


def parse_verdict(text: str) -> tuple[str, str]:
    """Return (result, critique) from the LAST verdict object in the text."""
    matches = list(VERDICT_RE.finditer(text))
    if not matches:
        return "Unknown", f"could not parse a verdict from: {text[-300:]}"
    last = matches[-1]
    result = last.group(1).capitalize()
    try:
        critique = json.loads(last.group(0)).get("critique", "")
    except json.JSONDecodeError:
        critique = text[: last.start()].strip()[-500:]
    return result, critique


class Judge:
    def __init__(self, client=None, model: str | None = None):
        import anthropic

        self.client = client or anthropic.Anthropic(max_retries=4)
        self.model = model or os.environ.get("EVAL_JUDGE_MODEL", "claude-opus-5")

    def __call__(self, judge: str, conversation: str, reply: str) -> tuple[str, str]:
        response = self.client.messages.create(
            model=self.model,
            max_tokens=8000,
            thinking={"type": "adaptive"},
            messages=[{"role": "user", "content": build_prompt(judge, conversation, reply)}],
        )
        if response.stop_reason == "refusal":
            return "Unknown", "judge refused"
        text = "".join(b.text for b in response.content if b.type == "text")
        return parse_verdict(text)


def grade(spec: dict, ctx: dict) -> dict:
    judge = ctx.get("judge")
    if judge is None:
        return {"status": "skip", "detail": "no API key or --no-judge: judge not run"}
    t = ctx["transcript"]
    replies = "\n\n".join(f"[reply {i + 1}] {r}" for i, r in enumerate(t["replies"]))
    result, critique = judge(spec["judge"], render_conversation(t["events"]), replies)
    status = {"Pass": "pass", "Fail": "fail"}.get(result, "fail")
    detail = critique if result != "Unknown" else f"judge said Unknown (counted as fail, read it): {critique}"
    return {"status": status, "detail": detail, "verdict": result}


def list_judges() -> list[str]:
    return sorted(p.stem for p in Path(JUDGE_DIR).glob("*.md"))
