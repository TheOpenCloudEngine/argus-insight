"""Anthropic (Claude) LLM provider with native tool_use support.

Uses the Anthropic Messages API which has first-class tool_use support,
making it the recommended provider for the agent.
"""

import logging
import uuid

import httpx

from app.llm.base import AgentLLMProvider, LLMResponse, ToolCall

logger = logging.getLogger(__name__)


class AnthropicProvider(AgentLLMProvider):
    """Anthropic Messages API provider with tool_use."""

    def __init__(
        self,
        api_key: str,
        model_id: str = "claude-sonnet-4-20250514",
        base_url: str = "https://api.anthropic.com",
    ):
        self._api_key = api_key
        self._model_id = model_id
        self._base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(timeout=120.0)

    async def generate(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        system_prompt: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        payload: dict = {
            "model": self._model_id,
            "max_tokens": max_tokens,
            "messages": messages,
            "temperature": temperature,
        }
        if system_prompt:
            payload["system"] = system_prompt
        if tools:
            payload["tools"] = self._convert_tools(tools)

        resp = await self._client.post(
            f"{self._base_url}/v1/messages",
            headers={
                "x-api-key": self._api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()

        usage = data.get("usage", {})
        text = ""
        tool_calls = []

        for block in data.get("content", []):
            if block.get("type") == "text":
                text += block.get("text", "")
            elif block.get("type") == "tool_use":
                tool_calls.append(
                    ToolCall(
                        id=block.get("id", str(uuid.uuid4())),
                        name=block.get("name", ""),
                        arguments=block.get("input", {}),
                    )
                )

        return LLMResponse(
            text=text,
            tool_calls=tool_calls,
            prompt_tokens=usage.get("input_tokens", 0),
            completion_tokens=usage.get("output_tokens", 0),
            stop_reason=data.get("stop_reason", ""),
            raw=data,
        )

    def _convert_tools(self, tools: list[dict]) -> list[dict]:
        """Convert internal tool format to Anthropic tool_use format."""
        anthropic_tools = []
        for tool in tools:
            anthropic_tools.append(
                {
                    "name": tool["name"],
                    "description": tool.get("description", ""),
                    "input_schema": tool.get("parameters", {"type": "object", "properties": {}}),
                }
            )
        return anthropic_tools

    def format_tool_result(self, tool_call_id: str, result: str) -> dict:
        """Format a tool result for the Anthropic conversation format."""
        return {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": tool_call_id,
                    "content": result,
                }
            ],
        }

    def format_assistant_response(self, response: LLMResponse) -> dict:
        """Format the assistant response including tool_use blocks."""
        content = []
        if response.text:
            content.append({"type": "text", "text": response.text})
        for tc in response.tool_calls:
            content.append(
                {
                    "type": "tool_use",
                    "id": tc.id,
                    "name": tc.name,
                    "input": tc.arguments,
                }
            )
        return {"role": "assistant", "content": content}

    def model_name(self) -> str:
        return self._model_id

    def provider_name(self) -> str:
        return "anthropic"

    async def close(self) -> None:
        await self._client.aclose()
        logger.info("Anthropic provider closed")
