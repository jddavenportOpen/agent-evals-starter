"""The agent interface and the scripted user.

Every agent implements respond(user_message, env) -> reply text. While it
responds it may call tools through env.call_tool(...), which logs them.

run() plays the task's scripted user: it sends user_turns one at a time and
records everything in env.events. That record is the transcript.

A scripted user is the simplest possible user simulator. It is predictable
and free, but it cannot react to what the agent says. If the agent asks an
unexpected question, the next scripted line may not fit. Swapping in an LLM
user simulator (like tau-bench does) is one of the exercises in the README.
"""

from __future__ import annotations

import time

from evals.env import StoreEnv


class Agent:
    name = "base"

    def start(self, task: dict, env: StoreEnv) -> None:
        """Called once per trial before the first user turn."""

    def respond(self, user_message: str, env: StoreEnv) -> str:
        raise NotImplementedError

    def usage(self) -> dict:
        """Token counts, if the agent calls a model."""
        return {}

    def run(self, task: dict, env: StoreEnv) -> dict:
        started = time.time()
        error = None
        self.start(task, env)
        for i, user_message in enumerate(task["user_turns"]):
            env.turn = i
            env.log_user(user_message)
            try:
                reply = self.respond(user_message, env)
            except Exception as exc:  # an infra error is recorded, not hidden
                error = f"{type(exc).__name__}: {exc}"
                env.log_assistant(f"[agent error] {error}")
                break
            env.log_assistant(reply)
        replies = [e["text"] for e in env.events if e["type"] == "assistant"]
        return {
            "task_id": task["id"],
            "agent": self.name,
            "events": env.events,
            "replies": replies,
            "final_reply": replies[-1] if replies else "",
            "error": error,
            "metrics": {
                "n_tool_calls": len(env.calls),
                "n_agent_turns": len(replies),
                "latency_s": round(time.time() - started, 2),
                **self.usage(),
            },
        }
