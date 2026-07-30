from typing import Any, Protocol

from pydantic import BaseModel


class Phase4Agent[InputT: BaseModel, OutputT: BaseModel](Protocol):
    name: str
    version: str
    allowed_tools: frozenset[str]
    model_route: str
    prompt_version: str
    output_type: type[OutputT]

    async def execute(self, input_data: InputT) -> OutputT: ...


class AgentDescriptor(BaseModel):
    name: str
    version: str
    allowed_tools: list[str]
    model_route: str
    prompt_version: str
    output_schema: dict[str, Any]
