"""Orchestrator -- the agentic tool-calling loop.

Sends a user request to the LLM along with available tools.
When the LLM returns tool_use blocks, the orchestrator executes them
and feeds results back until the LLM produces a final text response.
"""

import json
from dataclasses import dataclass, field

from adzekit.agent.client import LLMSettings, chat, get_llm_settings
from adzekit.agent.tools import ToolRegistry, registry as global_registry


SYSTEM_PROMPT = """\
You are AdzeKit, a personal productivity agent. You help the user manage their
commitments, projects, and communications. You have access to tools for
reading and managing email (Gmail), and for reading the user's productivity
shed (loops, projects, daily notes).

IMPORTANT ACCESS RULES:
- You can READ everything in the shed (backbone files: loops, projects, daily
  notes, knowledge, reviews, inbox).
- You CANNOT WRITE to backbone files. The backbone is the human's domain.
- You CAN WRITE to drafts/ (proposals for human review) and stock/ (raw materials).
- When you want to suggest a new loop or inbox item, use the propose tools.
  These save to drafts/ for the human to review and apply.

Core principles you follow:
- Close every loop: every commitment gets a response within 24 hours.
- Cap work-in-progress: max 3 active projects, max 5 daily focus tasks.
- Protect deep work: minimize interruptions, batch communications.
- Human always decides: you draft and suggest, the user approves.

When triaging email:
- Categorize each email as: ACTION_REQUIRED, WAITING_FOR, FYI, or ARCHIVE.
- For ACTION_REQUIRED emails, draft a reply (saved as Gmail draft, not sent).
- For FYI emails, extract any relevant information and suggest archiving.
- For ARCHIVE emails, archive them if the user has approved auto-archive.
- If an email implies a commitment, propose a loop via shed_propose_loop.
- Save a triage summary to drafts/ via shed_save_summary.

Be concise. No filler. Act like a sharp executive assistant."""


@dataclass
class AgentTurn:
    """One turn of the agent loop."""

    role: str
    content: str
    tool_calls: list[dict] = field(default_factory=list)
    tool_results: list[dict] = field(default_factory=list)


@dataclass
class AgentResult:
    """The final result of an agent run."""

    response: str
    turns: list[AgentTurn]
    tool_calls_made: int


def run_agent(
    user_message: str,
    *,
    tool_registry: ToolRegistry | None = None,
    system_prompt: str = SYSTEM_PROMPT,
    settings: LLMSettings | None = None,
    max_iterations: int = 15,
    conversation_history: list[dict] | None = None,
) -> AgentResult:
    """Run the agentic loop until the LLM produces a final text answer.

    Args:
        user_message: The user's request.
        tool_registry: Tools available to the agent. Defaults to global registry.
        system_prompt: System prompt for the agent.
        settings: LLM settings.
        max_iterations: Safety limit on tool-calling rounds.
        conversation_history: Prior conversation messages to continue from.

    Returns:
        AgentResult with the final text response and execution trace.
    """
    settings = settings or get_llm_settings()
    reg = tool_registry or global_registry
    tools_schema = reg.to_anthropic_tools()

    messages = list(conversation_history or [])
    messages.append({"role": "user", "content": user_message})

    turns: list[AgentTurn] = []
    total_tool_calls = 0

    for _ in range(max_iterations):
        response = chat(
            messages=messages,
            system=system_prompt,
            tools=tools_schema if tools_schema else None,
            settings=settings,
        )

        # Parse the response content blocks
        text_parts = []
        tool_use_blocks = []

        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_use_blocks.append({
                    "id": block.id,
                    "name": block.name,
                    "input": block.input,
                })

        turn = AgentTurn(
            role="assistant",
            content="\n".join(text_parts),
            tool_calls=tool_use_blocks,
        )

        # If no tool calls, we have a final answer
        if not tool_use_blocks:
            turns.append(turn)
            return AgentResult(
                response=turn.content,
                turns=turns,
                tool_calls_made=total_tool_calls,
            )

        # Execute each tool call and collect results
        tool_results = []
        for tc in tool_use_blocks:
            result_str = reg.call(tc["name"], tc["input"])
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tc["id"],
                "content": result_str,
            })
            total_tool_calls += 1

        turn.tool_results = tool_results
        turns.append(turn)

        # Append assistant message (with tool_use blocks) and tool results
        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": tool_results})

    # If we hit max iterations, return whatever we have
    final_text = turns[-1].content if turns else "Agent reached maximum iterations."
    return AgentResult(
        response=final_text,
        turns=turns,
        tool_calls_made=total_tool_calls,
    )
