"""Runner abstraction for the gateway daemon.

Per the locked decision (hybrid Pro/SDK), the daemon talks to Claude through
a `Runner` interface with two implementations:

  - ClaudeSubprocessRunner (default): shells out to
        claude --resume <session-id> -p "<message>" --output-format json
    Uses the user's Claude Code Pro subscription. Slower (~2-5s subprocess
    startup per turn). No extra dependencies.

  - AgentSDKRunner (opt-in): holds a `ClaudeSDKClient` in-process per
    session_id and calls `client.query(message)`. Uses ANTHROPIC_API_KEY
    pay-per-token. Sub-second latency. Requires `claude-agent-sdk` to be
    installed (raises a clear ImportError on instantiation otherwise).

The implementation is selected at daemon startup via env var
`ADZEKIT_RUNNER=subprocess` (default) or `=sdk`. Switching modes never
requires touching gateway code.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass
class RunnerResult:
    """What a Runner.chat() call returns."""

    text: str
    session_id: str
    duration_s: float
    tool_calls_made: int = 0
    raw_payload: dict | None = None


class RunnerError(RuntimeError):
    """Raised when the underlying Claude invocation fails."""


class Runner(Protocol):
    """The contract: `chat()` takes a session id (possibly empty for first
    turn) plus a message, returns text + the session id to resume next."""

    async def chat(
        self,
        session_id: str,
        message: str,
        *,
        cwd: Path | None = None,
    ) -> RunnerResult:
        ...


# --- ClaudeSubprocessRunner (default, uses Pro subscription) ---------------


class ClaudeSubprocessRunner:
    """Shells out to `claude --resume <session-id> -p <message> --output-format json`.

    Sessions persist in `~/.claude/projects/<cwd-hash>/*.jsonl` and are
    portable across invocations. The session id is captured from the
    JSON output and threaded back through the gateway.

    No persistent process. Every call spawns a fresh `claude` subprocess.
    """

    def __init__(self, *, binary: str = "claude", timeout_s: float = 120.0):
        self.binary = binary
        self.timeout_s = timeout_s

    async def chat(
        self,
        session_id: str,
        message: str,
        *,
        cwd: Path | None = None,
    ) -> RunnerResult:
        args = [self.binary]
        if session_id:
            args.extend(["--resume", session_id])
        args.extend(["-p", message, "--output-format", "json"])

        start = time.monotonic()
        try:
            proc = await asyncio.create_subprocess_exec(
                *args,
                cwd=str(cwd) if cwd else None,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError as exc:
            raise RunnerError(
                f"`{self.binary}` not found on PATH. Install Claude Code or "
                "set the `binary` kwarg to a full path."
            ) from exc

        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=self.timeout_s,
            )
        except asyncio.TimeoutError as exc:
            proc.kill()
            await proc.communicate()
            raise RunnerError(
                f"`{self.binary}` did not respond within {self.timeout_s}s"
            ) from exc

        duration_s = time.monotonic() - start

        if proc.returncode != 0:
            stderr_text = stderr.decode("utf-8", errors="replace").strip()
            raise RunnerError(
                f"`{self.binary}` exited {proc.returncode}: {stderr_text or '(no stderr)'}"
            )

        try:
            payload = json.loads(stdout.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise RunnerError(
                f"`{self.binary}` did not produce JSON output: {exc}. "
                "Did the --output-format flag take effect?"
            ) from exc

        # Claude Code's headless JSON envelope varies slightly across versions;
        # we accept either `result` or `text` and either `session_id` or
        # `sessionId`. Defensive against minor schema drift.
        text = payload.get("result") or payload.get("text") or payload.get("response") or ""
        new_session_id = (
            payload.get("session_id")
            or payload.get("sessionId")
            or session_id  # fall back to the input
        )
        tool_calls = payload.get("tool_calls_made") or payload.get("toolCallsMade") or 0

        return RunnerResult(
            text=text,
            session_id=new_session_id,
            duration_s=duration_s,
            tool_calls_made=int(tool_calls),
            raw_payload=payload,
        )


# --- AgentSDKRunner (opt-in, uses claude-agent-sdk + API key) --------------


class AgentSDKRunner:
    """In-process runner using `claude-agent-sdk`.

    Requires the optional `claude-agent-sdk` package and a valid
    `ANTHROPIC_API_KEY`. Cost is pay-per-token (separate from Pro). Use
    when you want sub-second latency and don't mind unpredictable bills.

    The implementation is intentionally minimal — it constructs a query
    per turn rather than holding a long-lived client, which keeps the
    session handoff identical to the subprocess runner. Future versions
    may pool clients for further latency wins.
    """

    def __init__(self) -> None:
        try:
            import claude_agent_sdk  # noqa: F401
        except ImportError as exc:
            raise RunnerError(
                "AgentSDKRunner requires `claude-agent-sdk`. Install with "
                "`pip install adzekit[sdk]` (or `pip install claude-agent-sdk`)."
            ) from exc

    async def chat(
        self,
        session_id: str,
        message: str,
        *,
        cwd: Path | None = None,
    ) -> RunnerResult:
        from claude_agent_sdk import ClaudeAgentOptions, query

        start = time.monotonic()
        result_text = ""
        new_session_id = session_id
        try:
            options = ClaudeAgentOptions(cwd=str(cwd) if cwd else None)
            kwargs: dict = {"prompt": message, "options": options}
            if session_id:
                kwargs["resume"] = session_id
            async for msg in query(**kwargs):
                # The SDK emits a sequence of messages; the final one carries
                # the result + session id. We collect text from any message
                # that has it and remember the most recent session id.
                if hasattr(msg, "result") and msg.result:
                    result_text = msg.result
                if hasattr(msg, "session_id") and msg.session_id:
                    new_session_id = msg.session_id
                # Fall back: some SDK messages expose `text` instead.
                if not result_text and hasattr(msg, "text") and msg.text:
                    result_text = msg.text
        except Exception as exc:
            raise RunnerError(f"Agent SDK query failed: {exc}") from exc

        return RunnerResult(
            text=result_text,
            session_id=new_session_id,
            duration_s=time.monotonic() - start,
        )


# --- Factory ---------------------------------------------------------------


def make_runner(name: str | None = None) -> Runner:
    """Construct the configured Runner.

    Selection order:
      1. explicit `name` argument
      2. ADZEKIT_RUNNER env var ("subprocess" | "sdk")
      3. default: "subprocess"
    """
    chosen = name or os.environ.get("ADZEKIT_RUNNER", "subprocess")
    if chosen == "subprocess":
        return ClaudeSubprocessRunner()
    if chosen == "sdk":
        return AgentSDKRunner()
    raise RunnerError(
        f"Unknown runner `{chosen}`. Valid values: subprocess, sdk."
    )
