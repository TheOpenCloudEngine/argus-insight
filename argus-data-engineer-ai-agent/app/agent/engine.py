"""ReAct Agent Engine — the core reasoning loop.

Implements the Reason → Act → Observe cycle:
1. Send messages + tool definitions to the LLM
2. If LLM returns tool_calls, execute them (with approval if needed)
3. Feed results back and repeat
4. If LLM returns text only, that's the final answer
"""

import json
import logging

from app.agent.prompts.system import SYSTEM_PROMPT, TOOL_GUIDELINES
from app.agent.session import AgentStep, ConversationSession, StepType
from app.core.config import settings
from app.llm.base import AgentLLMProvider, LLMResponse
from app.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


class AgentEngine:
    """ReAct loop engine for the Data Engineer AI Agent."""

    def __init__(
        self,
        llm: AgentLLMProvider,
        tool_registry: ToolRegistry,
        max_steps: int | None = None,
    ) -> None:
        self._llm = llm
        self._tools = tool_registry
        self._max_steps = max_steps or settings.agent_max_steps
        self._system_prompt = SYSTEM_PROMPT + "\n\n" + TOOL_GUIDELINES

    async def run(
        self,
        user_message: str,
        session: ConversationSession,
    ) -> dict:
        """Run the agent loop for a single user message.

        Returns a dict with:
            - answer: Final text response (str or None)
            - steps: List of step dicts
            - status: "completed" | "awaiting_approval" | "max_steps_exceeded"
            - pending_action: Approval details if status is "awaiting_approval"
        """
        session.add_user_message(user_message)

        for step_num in range(self._max_steps):
            logger.info("Agent step %d/%d", step_num + 1, self._max_steps)

            # 1) Call LLM with messages + tools
            response = await self._llm.generate(
                messages=session.get_messages(),
                tools=self._tools.get_tool_definitions(),
                system_prompt=self._system_prompt,
                temperature=settings.llm_temperature,
                max_tokens=settings.llm_max_tokens,
            )
            session.add_tokens(response.prompt_tokens, response.completion_tokens)

            # 2) No tool calls → final answer
            if not response.has_tool_calls:
                session.add_step(
                    AgentStep(
                        type=StepType.ANSWER,
                        content=response.text,
                    )
                )
                # Add assistant message to conversation
                session.add_assistant_message(self._format_assistant_message(response))
                return {
                    "answer": response.text,
                    "steps": [s.to_dict() for s in session.steps],
                    "status": "completed",
                    "session_id": session.session_id,
                    "tokens": {
                        "prompt": session.total_prompt_tokens,
                        "completion": session.total_completion_tokens,
                    },
                }

            # 3) Has tool calls — add assistant message first
            session.add_assistant_message(self._format_assistant_message(response))

            # Record thinking if present
            if response.text:
                session.add_step(
                    AgentStep(
                        type=StepType.THINKING,
                        content=response.text,
                    )
                )

            # 4) Process each tool call
            tool_results_for_llm = []

            for tc in response.tool_calls:
                # Log the tool call step
                step_idx = session.add_step(
                    AgentStep(
                        type=StepType.TOOL_CALL,
                        tool_name=tc.name,
                        tool_params=tc.arguments,
                        tool_call_id=tc.id,
                    )
                )

                # Check if blocked
                if self._tools.is_blocked(tc.name):
                    error_msg = f"Tool '{tc.name}' is blocked. Generate code instead."
                    session.add_step(
                        AgentStep(
                            type=StepType.ERROR,
                            content=error_msg,
                            tool_name=tc.name,
                            tool_call_id=tc.id,
                        )
                    )
                    tool_results_for_llm.append(
                        self._format_tool_result(tc.id, json.dumps({"error": error_msg}))
                    )
                    continue

                # Check if approval needed
                if self._tools.requires_approval(tc.name):
                    tool = self._tools.get(tc.name)
                    desc = tool.description if tool else tc.name
                    session.set_pending_approval(
                        step_index=step_idx,
                        tool_name=tc.name,
                        tool_params=tc.arguments,
                        tool_call_id=tc.id,
                        description=(
                            f"{desc} — params: {json.dumps(tc.arguments, ensure_ascii=False)}"
                        ),
                    )
                    session.add_step(
                        AgentStep(
                            type=StepType.APPROVAL_REQUIRED,
                            tool_name=tc.name,
                            tool_params=tc.arguments,
                            tool_call_id=tc.id,
                            content=f"Approval required for: {tc.name}",
                        )
                    )
                    return {
                        "answer": None,
                        "steps": [s.to_dict() for s in session.steps],
                        "status": "awaiting_approval",
                        "session_id": session.session_id,
                        "pending_action": {
                            "step_index": step_idx,
                            "tool": tc.name,
                            "params": tc.arguments,
                            "description": desc,
                        },
                        "tokens": {
                            "prompt": session.total_prompt_tokens,
                            "completion": session.total_completion_tokens,
                        },
                    }

                # Execute the tool
                result = await self._tools.execute(tc.name, tc.arguments)
                result_str = result.to_str()

                session.add_step(
                    AgentStep(
                        type=StepType.TOOL_RESULT,
                        tool_name=tc.name,
                        tool_result=result_str,
                        tool_call_id=tc.id,
                    )
                )
                tool_results_for_llm.append(self._format_tool_result(tc.id, result_str))

            # 5) Add all tool results to conversation
            for tr in tool_results_for_llm:
                session.add_tool_result_message(tr)

        # Max steps exceeded
        logger.warning("Agent exceeded max steps (%d)", self._max_steps)
        return {
            "answer": "I've reached the maximum number of steps. Please refine your request.",
            "steps": [s.to_dict() for s in session.steps],
            "status": "max_steps_exceeded",
            "session_id": session.session_id,
            "tokens": {
                "prompt": session.total_prompt_tokens,
                "completion": session.total_completion_tokens,
            },
        }

    async def resume_after_approval(
        self,
        session: ConversationSession,
        approved: bool,
    ) -> dict:
        """Resume the agent loop after a user approval/denial decision."""
        approval = session.clear_pending_approval()
        if not approval:
            return {
                "answer": "No pending approval found.",
                "steps": [s.to_dict() for s in session.steps],
                "status": "completed",
                "session_id": session.session_id,
            }

        if approved:
            # Execute the approved tool
            result = await self._tools.execute(approval.tool_name, approval.tool_params)
            result_str = result.to_str()

            session.add_step(
                AgentStep(
                    type=StepType.TOOL_RESULT,
                    tool_name=approval.tool_name,
                    tool_result=result_str,
                    tool_call_id=approval.tool_call_id,
                )
            )
            session.add_tool_result_message(
                self._format_tool_result(approval.tool_call_id, result_str)
            )
        else:
            # User denied — feed denial back to LLM
            denial_msg = json.dumps(
                {
                    "error": f"User denied execution of '{approval.tool_name}'. "
                    "Try a different approach or just generate the code."
                }
            )
            session.add_step(
                AgentStep(
                    type=StepType.TOOL_RESULT,
                    tool_name=approval.tool_name,
                    tool_result=denial_msg,
                    tool_call_id=approval.tool_call_id,
                )
            )
            session.add_tool_result_message(
                self._format_tool_result(approval.tool_call_id, denial_msg)
            )

        # Continue the agent loop
        return await self._continue_loop(session)

    async def _continue_loop(self, session: ConversationSession) -> dict:
        """Continue the ReAct loop from where it left off."""
        remaining_steps = self._max_steps - len(
            [s for s in session.steps if s.type == StepType.TOOL_CALL]
        )
        if remaining_steps <= 0:
            remaining_steps = 3  # Give at least a few steps to wrap up

        for _ in range(remaining_steps):
            response = await self._llm.generate(
                messages=session.get_messages(),
                tools=self._tools.get_tool_definitions(),
                system_prompt=self._system_prompt,
                temperature=settings.llm_temperature,
                max_tokens=settings.llm_max_tokens,
            )
            session.add_tokens(response.prompt_tokens, response.completion_tokens)

            if not response.has_tool_calls:
                session.add_step(
                    AgentStep(
                        type=StepType.ANSWER,
                        content=response.text,
                    )
                )
                session.add_assistant_message(self._format_assistant_message(response))
                return {
                    "answer": response.text,
                    "steps": [s.to_dict() for s in session.steps],
                    "status": "completed",
                    "session_id": session.session_id,
                    "tokens": {
                        "prompt": session.total_prompt_tokens,
                        "completion": session.total_completion_tokens,
                    },
                }

            session.add_assistant_message(self._format_assistant_message(response))

            if response.text:
                session.add_step(
                    AgentStep(
                        type=StepType.THINKING,
                        content=response.text,
                    )
                )

            for tc in response.tool_calls:
                step_idx = session.add_step(
                    AgentStep(
                        type=StepType.TOOL_CALL,
                        tool_name=tc.name,
                        tool_params=tc.arguments,
                        tool_call_id=tc.id,
                    )
                )

                if self._tools.is_blocked(tc.name):
                    error_msg = f"Tool '{tc.name}' is blocked."
                    session.add_tool_result_message(
                        self._format_tool_result(tc.id, json.dumps({"error": error_msg}))
                    )
                    continue

                if self._tools.requires_approval(tc.name):
                    tool = self._tools.get(tc.name)
                    desc = tool.description if tool else tc.name
                    session.set_pending_approval(
                        step_index=step_idx,
                        tool_name=tc.name,
                        tool_params=tc.arguments,
                        tool_call_id=tc.id,
                        description=desc,
                    )
                    return {
                        "answer": None,
                        "steps": [s.to_dict() for s in session.steps],
                        "status": "awaiting_approval",
                        "session_id": session.session_id,
                        "pending_action": {
                            "step_index": step_idx,
                            "tool": tc.name,
                            "params": tc.arguments,
                            "description": desc,
                        },
                    }

                result = await self._tools.execute(tc.name, tc.arguments)
                result_str = result.to_str()
                session.add_step(
                    AgentStep(
                        type=StepType.TOOL_RESULT,
                        tool_name=tc.name,
                        tool_result=result_str,
                        tool_call_id=tc.id,
                    )
                )
                session.add_tool_result_message(self._format_tool_result(tc.id, result_str))

        return {
            "answer": "Reached step limit after approval.",
            "steps": [s.to_dict() for s in session.steps],
            "status": "max_steps_exceeded",
            "session_id": session.session_id,
        }

    def _format_assistant_message(self, response: LLMResponse) -> dict:
        """Format LLM response as a conversation message.

        Uses the provider's format_assistant_response if available,
        otherwise builds a generic format.
        """
        if hasattr(self._llm, "format_assistant_response"):
            return self._llm.format_assistant_response(response)

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

    def _format_tool_result(self, tool_call_id: str, result: str) -> dict:
        """Format a tool result as a conversation message."""
        if hasattr(self._llm, "format_tool_result"):
            return self._llm.format_tool_result(tool_call_id, result)

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
