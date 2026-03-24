"""OpenAI LLM provider with function calling support.

Translates between the internal tool format and OpenAI's function calling API.
"""

import json
import logging
import uuid

import httpx

from app.llm.base import AgentLLMProvider, LLMResponse, ToolCall

logger = logging.getLogger(__name__)


class OpenAIProvider(AgentLLMProvider):
    """OpenAI Chat Completions API provider with function calling."""

    def __init__(
        self,
        api_key: str,
        model_id: str = "gpt-4o",
        base_url: str = "https://api.openai.com/v1",
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
        oai_messages = []
        if system_prompt:
            oai_messages.append({"role": "system", "content": system_prompt})

        for msg in messages:
            oai_messages.append(self._convert_message(msg))

        payload: dict = {
            "model": self._model_id,
            "messages": oai_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if tools:
            payload["tools"] = self._convert_tools(tools)

        resp = await self._client.post(
            f"{self._base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()

        choice = data.get("choices", [{}])[0]
        message = choice.get("message", {})
        usage = data.get("usage", {})

        text = message.get("content", "") or ""
        tool_calls = []

        for tc in message.get("tool_calls", []):
            func = tc.get("function", {})
            try:
                arguments = json.loads(func.get("arguments", "{}"))
            except json.JSONDecodeError:
                arguments = {}
            tool_calls.append(
                ToolCall(
                    id=tc.get("id", str(uuid.uuid4())),
                    name=func.get("name", ""),
                    arguments=arguments,
                )
            )

        return LLMResponse(
            text=text,
            tool_calls=tool_calls,
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            stop_reason=choice.get("finish_reason", ""),
            raw=data,
        )

    def _convert_tools(self, tools: list[dict]) -> list[dict]:
        """Convert internal tool format to OpenAI function calling format."""
        oai_tools = []
        for tool in tools:
            oai_tools.append(
                {
                    "type": "function",
                    "function": {
                        "name": tool["name"],
                        "description": tool.get("description", ""),
                        "parameters": tool.get("parameters", {"type": "object", "properties": {}}),
                    },
                }
            )
        return oai_tools

    def _convert_message(self, msg: dict) -> dict:
        """Convert internal message format to OpenAI format."""
        role = msg.get("role", "user")
        content = msg.get("content", "")

        if role == "tool_result":
            return {
                "role": "tool",
                "tool_call_id": msg.get("tool_call_id", ""),
                "content": content if isinstance(content, str) else json.dumps(content),
            }

        if isinstance(content, list):
            # Flatten Anthropic-style content blocks
            text_parts = []
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    text_parts.append(block.get("text", ""))
                elif isinstance(block, dict) and block.get("type") == "tool_result":
                    return {
                        "role": "tool",
                        "tool_call_id": block.get("tool_use_id", ""),
                        "content": block.get("content", ""),
                    }
            return {"role": role, "content": "\n".join(text_parts)}

        return {"role": role, "content": content}

    def format_tool_result(self, tool_call_id: str, result: str) -> dict:
        """Format a tool result for OpenAI conversation format."""
        return {
            "role": "tool_result",
            "tool_call_id": tool_call_id,
            "content": result,
        }

    def format_assistant_response(self, response: LLMResponse) -> dict:
        """Format assistant response for OpenAI conversation."""
        msg: dict = {"role": "assistant", "content": response.text or None}
        if response.tool_calls:
            msg["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.name,
                        "arguments": json.dumps(tc.arguments),
                    },
                }
                for tc in response.tool_calls
            ]
        return msg

    def model_name(self) -> str:
        return self._model_id

    def provider_name(self) -> str:
        return "openai"

    async def close(self) -> None:
        await self._client.aclose()
        logger.info("OpenAI provider closed")
