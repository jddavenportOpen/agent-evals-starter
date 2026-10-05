"""Agents you can evaluate. Add your own by subclassing evals.agents.base.Agent."""

from evals.agents.baselines import NoopAgent, PushoverAgent, ReferenceAgent

AGENTS = {
    "reference": ReferenceAgent,
    "noop": NoopAgent,
    "pushover": PushoverAgent,
}


def make_agent(name: str, **kwargs):
    if name == "claude":
        from evals.agents.claude_agent import ClaudeAgent

        return ClaudeAgent(**kwargs)
    if name not in AGENTS:
        raise SystemExit(f"Unknown agent '{name}'. Choose from: claude, {', '.join(AGENTS)}")
    return AGENTS[name]()
