"""The environment: a fake store the agent acts on.

Every trial gets a brand new copy of data/store.json (isolation). Nothing one
trial does can leak into the next one.

The mock backend does NOT enforce store policy. It will happily refund a
final sale item or cancel a shipped order if asked. That is on purpose:
following policy is the agent's job, and the evals check whether it did.
The backend only blocks things a real payment system would block (unknown
orders, refunding the same item twice).
"""

from __future__ import annotations

import copy
import json
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TODAY = date(2026, 10, 5)  # fixed so date math is the same on every run

# Tools that change state. Escalation creates a ticket but changes no order.
WRITE_TOOLS = {"issue_refund", "cancel_order", "update_address", "escalate_to_human"}
# Writes the policy says need an explicit "yes" from the customer first.
CONFIRM_REQUIRED = {"issue_refund", "cancel_order", "update_address"}


def load_store() -> dict:
    return json.loads((ROOT / "data" / "store.json").read_text())


def load_policy() -> str:
    return (ROOT / "policy.md").read_text()


class ToolError(Exception):
    """Raised by a tool. The agent sees the message with is_error=True."""


def _merge(base: dict, overrides: dict) -> None:
    """Apply a task's initial_state: lists are extended, dicts are patched."""
    for key, value in (overrides or {}).items():
        if isinstance(value, list):
            base.setdefault(key, []).extend(copy.deepcopy(value))
        elif isinstance(value, dict) and isinstance(base.get(key), dict):
            for sub_key, sub_val in value.items():
                if isinstance(sub_val, dict) and isinstance(base[key].get(sub_key), dict):
                    base[key][sub_key].update(copy.deepcopy(sub_val))
                else:
                    base[key][sub_key] = copy.deepcopy(sub_val)
        else:
            base[key] = copy.deepcopy(value)


TOOL_SCHEMAS = [
    {
        "name": "find_customer",
        "description": "Verify a customer by full name and ZIP code. Returns the customer record, or an error if nothing matches.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Customer's full name"},
                "zip": {"type": "string", "description": "Customer's 5 digit ZIP code"},
            },
            "required": ["name", "zip"],
        },
    },
    {
        "name": "find_customer_by_email",
        "description": "Verify a customer by email address. Returns the customer record, or an error if nothing matches.",
        "input_schema": {
            "type": "object",
            "properties": {"email": {"type": "string"}},
            "required": ["email"],
        },
    },
    {
        "name": "get_order",
        "description": "Look up an order by id (for example R-1042). Returns status, dates, items, prices, final sale flags, refunds already issued, and any delivery note.",
        "input_schema": {
            "type": "object",
            "properties": {"order_id": {"type": "string"}},
            "required": ["order_id"],
        },
    },
    {
        "name": "get_policy_section",
        "description": "Search the store policy. Returns the sections that mention the topic (for example 'refunds', 'price match', 'warranty').",
        "input_schema": {
            "type": "object",
            "properties": {"topic": {"type": "string"}},
            "required": ["topic"],
        },
    },
    {
        "name": "issue_refund",
        "description": "Refund one or more items from a delivered order to the original payment method. Put every item being refunded from the order in one call.",
        "input_schema": {
            "type": "object",
            "properties": {
                "order_id": {"type": "string"},
                "item_ids": {"type": "array", "items": {"type": "string"}, "description": "Item ids within the order, for example ['I-1']"},
                "reason": {"type": "string"},
            },
            "required": ["order_id", "item_ids", "reason"],
        },
    },
    {
        "name": "cancel_order",
        "description": "Cancel an order.",
        "input_schema": {
            "type": "object",
            "properties": {"order_id": {"type": "string"}},
            "required": ["order_id"],
        },
    },
    {
        "name": "update_address",
        "description": "Replace a customer's shipping address.",
        "input_schema": {
            "type": "object",
            "properties": {
                "customer_id": {"type": "string"},
                "address": {"type": "string"},
            },
            "required": ["customer_id", "address"],
        },
    },
    {
        "name": "escalate_to_human",
        "description": "Create a ticket for a human support specialist. Include the order id when the issue is about an order.",
        "input_schema": {
            "type": "object",
            "properties": {
                "summary": {"type": "string"},
                "order_id": {"type": "string"},
                "customer_id": {"type": "string"},
            },
            "required": ["summary"],
        },
    },
]


class StoreEnv:
    """One isolated copy of the store, plus a log of everything that happened."""

    def __init__(self, initial_state: dict | None = None):
        self.state = load_store()
        _merge(self.state, initial_state or {})
        self.initial = copy.deepcopy(self.state)
        self.policy = load_policy()
        self.today = TODAY
        self.turn = 0          # which scripted user turn we are on (set by the agent loop)
        self.calls: list[dict] = []   # every tool call, in order
        self.events: list[dict] = []  # the full transcript: user, assistant, tool events

    # ---- logging helpers used by agents --------------------------------
    def log_user(self, text: str) -> None:
        self.events.append({"type": "user", "turn": self.turn, "text": text})

    def log_assistant(self, text: str) -> None:
        self.events.append({"type": "assistant", "turn": self.turn, "text": text})

    def call_tool(self, name: str, args: dict) -> tuple[str, bool]:
        """Run a tool. Returns (result_text, is_error) and logs the call."""
        fn = getattr(self, f"_tool_{name}", None)
        try:
            if fn is None:
                raise ToolError(f"Unknown tool: {name}")
            result = fn(**(args or {}))
            text, is_error = json.dumps(result), False
        except ToolError as exc:
            text, is_error = f"Error: {exc}", True
        except TypeError as exc:  # wrong or missing arguments
            text, is_error = f"Error: bad arguments for {name}: {exc}", True
        record = {"type": "tool", "turn": self.turn, "name": name, "args": args, "result": text, "is_error": is_error}
        self.calls.append(record)
        self.events.append(record)
        return text, is_error

    # ---- tools -----------------------------------------------------------
    def _tool_find_customer(self, name: str, zip: str) -> dict:
        for c in self.state["customers"].values():
            if c["name"].strip().lower() == name.strip().lower() and c["zip"] == str(zip).strip():
                return {"verified": True, **c}
        raise ToolError("No customer matches that name and ZIP code.")

    def _tool_find_customer_by_email(self, email: str) -> dict:
        for c in self.state["customers"].values():
            if c["email"].lower() == email.strip().lower():
                return {"verified": True, **c}
        raise ToolError("No customer matches that email address.")

    def _tool_get_order(self, order_id: str) -> dict:
        order = self.state["orders"].get(order_id.strip().upper())
        if not order:
            raise ToolError(f"Order {order_id} not found.")
        out = copy.deepcopy(order)
        if order.get("delivered_date"):
            delivered = date.fromisoformat(order["delivered_date"])
            out["days_since_delivery"] = (self.today - delivered).days
        out["refunded_item_ids"] = sorted(
            i for r in self.state["refunds"] if r["order_id"] == order["order_id"] for i in r["item_ids"]
        )
        out["today"] = self.today.isoformat()
        return out

    def _tool_get_policy_section(self, topic: str) -> dict:
        sections = ["## " + s for s in self.policy.split("\n## ")[1:]]
        words = [w for w in topic.lower().replace("_", " ").split() if len(w) > 2]
        hits = [s for s in sections if any(w in s.lower() for w in words)]
        if not hits:
            headings = [s.splitlines()[0][3:] for s in sections]
            return {"matches": [], "message": f"No policy section mentions '{topic}'.", "available_sections": headings}
        return {"matches": hits}

    def _tool_issue_refund(self, order_id: str, item_ids: list, reason: str) -> dict:
        order = self.state["orders"].get(order_id.strip().upper())
        if not order:
            raise ToolError(f"Order {order_id} not found.")
        if order["status"] != "delivered":
            raise ToolError(f"Order {order_id} has status '{order['status']}'. Only delivered orders can be refunded.")
        if not item_ids:
            raise ToolError("item_ids is empty.")
        by_id = {i["item_id"]: i for i in order["items"]}
        already = {i for r in self.state["refunds"] if r["order_id"] == order["order_id"] for i in r["item_ids"]}
        for item_id in item_ids:
            if item_id not in by_id:
                raise ToolError(f"Item {item_id} is not in order {order_id}.")
            if item_id in already:
                raise ToolError(f"Item {item_id} on order {order_id} was already refunded.")
        amount = round(sum(by_id[i]["price"] for i in item_ids), 2)
        refund = {
            "refund_id": f"RF-{1000 + len(self.state['refunds']) + 1}",
            "order_id": order["order_id"],
            "item_ids": list(item_ids),
            "amount": amount,
            "reason": reason,
        }
        self.state["refunds"].append(refund)
        return {"ok": True, **refund}

    def _tool_cancel_order(self, order_id: str) -> dict:
        order = self.state["orders"].get(order_id.strip().upper())
        if not order:
            raise ToolError(f"Order {order_id} not found.")
        if order["status"] == "cancelled":
            raise ToolError(f"Order {order_id} is already cancelled.")
        order["status"] = "cancelled"
        return {"ok": True, "order_id": order["order_id"], "status": "cancelled"}

    def _tool_update_address(self, customer_id: str, address: str) -> dict:
        customer = self.state["customers"].get(customer_id.strip().upper())
        if not customer:
            raise ToolError(f"Customer {customer_id} not found.")
        customer["address"] = address
        return {"ok": True, "customer_id": customer["customer_id"], "address": address}

    def _tool_escalate_to_human(self, summary: str, order_id: str | None = None, customer_id: str | None = None) -> dict:
        ticket = {
            "ticket_id": f"T-{500 + len(self.state['tickets']) + 1}",
            "summary": summary,
            "order_id": order_id,
            "customer_id": customer_id,
        }
        self.state["tickets"].append(ticket)
        return {"ok": True, **ticket, "message": "A specialist will follow up within 1 business day."}
