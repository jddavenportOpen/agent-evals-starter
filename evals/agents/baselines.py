"""Three agents that need no API key.

reference: replays each task's hand-written correct answer. It must score
    100%. If it does not, the TASK or the GRADER is broken, not the agent.
    (Anthropic's guide calls this writing a reference solution that passes
    all graders.)

noop: says "Sorry, I can't help with that." and does nothing. A negative
    control. Any task the noop agent passes is a task where doing nothing
    looks correct to your graders. If that is most of your suite, your
    suite is lopsided. (A trivial agent that returned empty responses scored
    38% on tau-bench's airline tasks.)

pushover: does whatever the customer asks, right away, with no identity
    check and no confirmation, and says yes to every question. A second
    negative control. It should fail almost everything that involves policy.
"""

from __future__ import annotations

import json
import re

from evals.agents.base import Agent
from evals.env import StoreEnv


class ReferenceAgent(Agent):
    name = "reference"

    def start(self, task, env):
        self.steps = task.get("reference_solution") or []

    def respond(self, user_message, env):
        step = self.steps[env.turn] if env.turn < len(self.steps) else {"calls": [], "reply": ""}
        for call in step.get("calls", []):
            env.call_tool(call["tool"], call.get("args", {}))
        return step.get("reply", "")


class NoopAgent(Agent):
    name = "noop"

    def respond(self, user_message, env):
        return "Sorry, I can't help with that."


ORDER_RE = re.compile(r"\bR-\d{4}\b", re.I)
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")


class PushoverAgent(Agent):
    """Rule-based people pleaser. Deterministic, so its score never changes."""

    name = "pushover"

    def start(self, task, env):
        self.done = False

    def respond(self, user_message, env: StoreEnv):
        if self.done:
            return "Great, anything else I can do for you?"
        text = user_message.lower()
        orders = [o.upper() for o in ORDER_RE.findall(user_message)]
        order_id = orders[0] if orders else None

        if any(w in text for w in ["human", "real person", "manager"]):
            env.call_tool("escalate_to_human", {"summary": user_message, "order_id": order_id})
            self.done = True
            return "Done, a human will reach out."
        if "address" in text and " to " in text:
            email = EMAIL_RE.search(user_message)
            if email:
                result, err = env.call_tool("find_customer_by_email", {"email": email.group(0)})
                if not err:
                    new_address = user_message.split(" to ", 1)[1].split(". My email")[0].strip()
                    env.call_tool("update_address", {"customer_id": json.loads(result)["customer_id"], "address": new_address})
            self.done = True
            return "Done! Your address is updated."
        if "cancel" in text and order_id:
            env.call_tool("cancel_order", {"order_id": order_id})
            self.done = True
            return f"Done! Order {order_id} is cancelled."
        if any(w in text for w in ["refund", "return"]) and order_id:
            result, err = env.call_tool("get_order", {"order_id": order_id})
            if not err:
                order = json.loads(result)
                item_ids = [i["item_id"] for i in order["items"] if i["item_id"] not in order["refunded_item_ids"]]
                if item_ids:
                    env.call_tool("issue_refund", {"order_id": order_id, "item_ids": item_ids, "reason": "Customer request"})
            self.done = True
            return "Done! You've been refunded in full."
        if order_id:
            result, err = env.call_tool("get_order", {"order_id": order_id})
            status = json.loads(result).get("status", "unknown") if not err else "unknown"
            return f"Order {order_id} is {status}."
        return "Yes, absolutely, we can do that for you!"
