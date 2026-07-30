from collections.abc import Iterable
from typing import Any

from astrapath.agents.contracts import AgentProtocol
from astrapath.errors import AppError


class AgentRegistry:
    def __init__(self, agents: Iterable[AgentProtocol[Any, Any]]) -> None:
        agent_list = list(agents)
        self._agents = {agent.name: agent for agent in agent_list}
        if len(self._agents) != len(agent_list):
            raise ValueError("Agent names must be unique")

    def get(self, name: str) -> AgentProtocol[Any, Any]:
        agent = self._agents.get(name)
        if not agent:
            raise AppError(404, "agent_not_registered", f"Agent '{name}' is not registered")
        return agent

    def list(self) -> list[dict[str, Any]]:
        return [
            {
                "name": agent.name,
                "version": agent.version,
                "allowed_tools": sorted(agent.allowed_tools),
            }
            for agent in sorted(self._agents.values(), key=lambda item: item.name)
        ]
