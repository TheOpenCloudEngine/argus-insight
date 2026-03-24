"""Ollama LLM provider with tool calling support.

Ollama supports OpenAI-compatible tool calling for models like
qwen2.5, llama3.1, and mistral-nemo.
"""

import json
import logging
import uuid

import httpx

from app.llm.base import AgentLLMProvider, LLMResponse, ToolCall

logger = logging.getLogger(__name__)


class OllamaProvider(AgentLLMProvider):
    """Ollama API provider with tool calling (OpenAI-compatible)."""

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model_id: str = "qwen2.5:7b",
    ):
        self._model_id = model_id
        self._base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(timeout=300.0)

    async def generate(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        system_prompt: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        ollama_messages = []
        if system_prompt:
            ollama_messages.append({"role": "system", "content": system_prompt})

        for msg in messages:
            ollama_messages.append(self._convert_message(msg))

        payload: dict = {
            "model": self._model_id,
            "messages": ollama_messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }
        if tools:
            payload["tools"] = self._convert_tools(tools)

        resp = await self._client.post(
            f"{self._base_url}/api/chat",
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()

        message = data.get("message", {})
        text = message.get("content", "") or ""
        tool_calls = []

        for tc in message.get("tool_calls", []):
            func = tc.get("function", {})
            tool_calls.append(
                ToolCall(
                    id=str(uuid.uuid4()),
                    name=func.get("name", ""),
                    arguments=func.get("arguments", {}),
                )
            )

        prompt_tokens = data.get("prompt_eval_count", 0) or 0
        completion_tokens = data.get("eval_count", 0) or 0

        return LLMResponse(
            text=text,
            tool_calls=tool_calls,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            stop_reason="tool_use" if tool_calls else "end_turn",
            raw=data,
        )

    def _convert_tools(self, tools: list[dict]) -> list[dict]:
        """Convert internal tool format to Ollama tool format."""
        ollama_tools = []
        for tool in tools:
            ollama_tools.append(
                {
                    "type": "function",
                    "function": {
                        "name": tool["name"],
                        "description": tool.get("description", ""),
                        "parameters": tool.get("parameters", {"type": "object", "properties": {}}),
                    },
                }
            )
        return ollama_tools

    def _convert_message(self, msg: dict) -> dict:
        """Convert internal message format to Ollama format."""
        role = msg.get("role", "user")
        content = msg.get("content", "")

        if role == "tool_result":
            return {
                "role": "tool",
                "content": content if isinstance(content, str) else json.dumps(content),
            }

        if isinstance(content, list):
            text_parts = []
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    text_parts.append(block.get("text", ""))
                elif isinstance(block, dict) and block.get("type") == "tool_result":
                    return {"role": "tool", "content": block.get("content", "")}
            return {"role": role, "content": "\n".join(text_parts)}

        return {"role": role, "content": content}

    def format_tool_result(self, tool_call_id: str, result: str) -> dict:
        return {
            "role": "tool_result",
            "tool_call_id": tool_call_id,
            "content": result,
        }

    def format_assistant_response(self, response: LLMResponse) -> dict:
        return {"role": "assistant", "content": response.text or ""}

    def model_name(self) -> str:
        return self._model_id

    def provider_name(self) -> str:
        return "ollama"

    async def close(self) -> None:
        await self._client.aclose()
        logger.info("Ollama provider closed")
