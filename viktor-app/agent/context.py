from dataclasses import dataclass


@dataclass
class AgentContext:
    """Per-conversation values handed to every tool through the Agents SDK."""

    storage_prefix: str
