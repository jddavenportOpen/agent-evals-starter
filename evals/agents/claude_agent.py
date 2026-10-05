"""The real agent under test: Claude with the store tools.

This file is the "agent harness" (scaffold): the system prompt, the tool
list, and the loop that runs tool calls and feeds results back. An eval
always measures model + harness together, so changing this prompt can move
your scores as much as changing the model. Editing SYSTEM_PROMPT and
re-running the suite is the main experiment this repo is built for.

Settings (environment variables):
    ANTHROPIC_API_KEY   required
    EVAL_MODEL          default "claude-opus-5"

A note on refusal fallbacks: the Claude API can silently retry a refused
request on a different model. That is useful in production, but in an eval
it would mix two models into one score, so it is deliberately left off here.
A refusal is recorded in the transcript instead.
"""

from __future__ import annotations

import os

from evals.agents.base import Agent
from evals.env import TOOL_SCHEMAS, StoreEnv

SYSTEM_PROMPT = """You are the customer support agent for Ridgeline Outfitters, an outdoor gear store.
Today's date is {today}.

Follow the store policy below exactly. Use the tools to look up customers, orders, and policy, and to take actions.
Be concise and friendly. When you need the customer to confirm an action, describe it and ask them to reply yes.

<policy>
{policy}
</policy>"""

MAX_STEPS_PER_TURN = 15  # safety valve on tool calls within one customer turn


class ClaudeAgent(Agent):
    name = "claude"

    def __init__(self, client=None, model: str | None = None):
        import anthropic  # imported here so offline agents never need the package configured

        self.client = client or anthropic.Anthropic(max_retries=4)
        self.model = model or os.environ.get("EVAL_MODEL", "claude-opus-5")
        self.tokens = {"input_tokens": 0, "output_tokens": 0}

    def start(self, task, env: StoreEnv):
        self.messages = []
        self.system = SYSTEM_PROMPT.format(today=env.today.isoformat(), policy=env.policy)

    def usage(self):
        return {"model": self.model, **self.tokens}

    def respond(self, user_message: str, env: StoreEnv) -> str:
        self.messages.append({"role": "user", "content": user_message})
        for _ in range(MAX_STEPS_PER_TURN):
            response = self.client.messages.create(
                model=self.model,
                max_tokens=16000,
                system=self.system,
                tools=TOOL_SCHEMAS,
                thinking={"type": "adaptive"},
                messages=self.messages,
            )
            self.tokens["input_tokens"] += response.usage.input_tokens
            self.tokens["output_tokens"] += response.usage.output_tokens

            if response.stop_reason == "refusal":
                return "[refusal] The model declined to respond."

            # Keep the full content (including thinking blocks) in the history.
            self.messages.append({"role": "assistant", "content": response.content})

            if response.stop_reason == "tool_use":
                results = []
                for block in response.content:
                    if block.type == "tool_use":
                        text, is_error = env.call_tool(block.name, block.input)
                        results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": text,
                            "is_error": is_error,
                        })
                self.messages.append({"role": "user", "content": results})
                continue

            if response.stop_reason == "pause_turn":
                continue  # re-send so the model can finish its turn

            text = "".join(b.text for b in response.content if b.type == "text").strip()
            if response.stop_reason == "max_tokens":
                text += " [truncated: hit max_tokens]"
            return text
        return "[stopped: too many tool calls in one turn]"

