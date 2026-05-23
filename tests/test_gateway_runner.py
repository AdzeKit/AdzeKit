"""Tests for the gateway Runner abstraction."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from adzekit.gateway.runner import (
    AgentSDKRunner,
    ClaudeSubprocessRunner,
    RunnerError,
    RunnerResult,
    make_runner,
)


# --- ClaudeSubprocessRunner --------------------------------------------------


def _mock_create_subprocess_exec(*, stdout: bytes, stderr: bytes = b"", rc: int = 0):
    """Build a coroutine that mimics asyncio.create_subprocess_exec."""
    proc = MagicMock()
    proc.communicate = AsyncMock(return_value=(stdout, stderr))
    proc.returncode = rc
    proc.kill = MagicMock()

    async def fake_create(*args, **kwargs):
        return proc

    return fake_create, proc


def test_subprocess_runner_passes_session_id(monkeypatch):
    runner = ClaudeSubprocessRunner()
    captured_args: list[list[str]] = []

    async def fake_create(*args, **kwargs):
        captured_args.append(list(args))
        proc = MagicMock()
        proc.communicate = AsyncMock(return_value=(
            json.dumps({"result": "hello", "session_id": "abc-123"}).encode(),
            b"",
        ))
        proc.returncode = 0
        return proc

    monkeypatch.setattr(
        "adzekit.gateway.runner.asyncio.create_subprocess_exec",
        fake_create,
    )
    result = asyncio.run(
        runner.chat("old-session", "hi", cwd=Path("/tmp")),
    )
    assert result.text == "hello"
    assert result.session_id == "abc-123"
    # The subprocess was called with --resume old-session.
    assert "--resume" in captured_args[0]
    assert "old-session" in captured_args[0]
    assert "-p" in captured_args[0]
    assert "hi" in captured_args[0]
    assert "--output-format" in captured_args[0]
    assert "json" in captured_args[0]


def test_subprocess_runner_no_session_omits_resume_flag(monkeypatch):
    """Empty session_id → don't pass --resume; let Claude assign a fresh id."""
    runner = ClaudeSubprocessRunner()
    captured: list[list[str]] = []

    async def fake_create(*args, **kwargs):
        captured.append(list(args))
        proc = MagicMock()
        proc.communicate = AsyncMock(return_value=(
            json.dumps({"result": "first reply", "session_id": "new-session"}).encode(),
            b"",
        ))
        proc.returncode = 0
        return proc

    monkeypatch.setattr(
        "adzekit.gateway.runner.asyncio.create_subprocess_exec", fake_create,
    )
    result = asyncio.run(runner.chat("", "hi"))
    assert result.session_id == "new-session"
    assert "--resume" not in captured[0]


def test_subprocess_runner_raises_on_non_zero_exit(monkeypatch):
    runner = ClaudeSubprocessRunner()

    async def fake_create(*args, **kwargs):
        proc = MagicMock()
        proc.communicate = AsyncMock(return_value=(b"", b"boom"))
        proc.returncode = 2
        return proc

    monkeypatch.setattr(
        "adzekit.gateway.runner.asyncio.create_subprocess_exec", fake_create,
    )
    with pytest.raises(RunnerError, match="boom"):
        asyncio.run(runner.chat("", "hi"))


def test_subprocess_runner_raises_on_malformed_json(monkeypatch):
    runner = ClaudeSubprocessRunner()

    async def fake_create(*args, **kwargs):
        proc = MagicMock()
        proc.communicate = AsyncMock(return_value=(b"not json", b""))
        proc.returncode = 0
        return proc

    monkeypatch.setattr(
        "adzekit.gateway.runner.asyncio.create_subprocess_exec", fake_create,
    )
    with pytest.raises(RunnerError, match="did not produce JSON"):
        asyncio.run(runner.chat("", "hi"))


def test_subprocess_runner_handles_missing_binary(monkeypatch):
    runner = ClaudeSubprocessRunner(binary="nonexistent-binary-xyz")

    async def fake_create(*args, **kwargs):
        raise FileNotFoundError("no such file")

    monkeypatch.setattr(
        "adzekit.gateway.runner.asyncio.create_subprocess_exec", fake_create,
    )
    with pytest.raises(RunnerError, match="not found on PATH"):
        asyncio.run(runner.chat("", "hi"))


def test_subprocess_runner_accepts_schema_drift(monkeypatch):
    """The JSON shape may use `text`/`sessionId` instead of `result`/`session_id`."""
    runner = ClaudeSubprocessRunner()

    async def fake_create(*args, **kwargs):
        proc = MagicMock()
        proc.communicate = AsyncMock(return_value=(
            json.dumps({"text": "alt", "sessionId": "alt-sid"}).encode(),
            b"",
        ))
        proc.returncode = 0
        return proc

    monkeypatch.setattr(
        "adzekit.gateway.runner.asyncio.create_subprocess_exec", fake_create,
    )
    result = asyncio.run(runner.chat("", "hi"))
    assert result.text == "alt"
    assert result.session_id == "alt-sid"


# --- Factory ---------------------------------------------------------------


def test_make_runner_default_is_subprocess(monkeypatch):
    monkeypatch.delenv("ADZEKIT_RUNNER", raising=False)
    runner = make_runner()
    assert isinstance(runner, ClaudeSubprocessRunner)


def test_make_runner_explicit_subprocess():
    assert isinstance(make_runner("subprocess"), ClaudeSubprocessRunner)


def test_make_runner_unknown_raises():
    with pytest.raises(RunnerError, match="Unknown runner"):
        make_runner("garbage")


def test_make_runner_sdk_without_dep_raises(monkeypatch):
    """If claude-agent-sdk isn't installed, instantiation raises clearly."""
    import sys
    monkeypatch.setitem(sys.modules, "claude_agent_sdk", None)
    with pytest.raises(RunnerError, match="claude-agent-sdk"):
        AgentSDKRunner()


# --- RunnerResult dataclass ------------------------------------------------


def test_runner_result_defaults():
    r = RunnerResult(text="hi", session_id="x", duration_s=0.5)
    assert r.tool_calls_made == 0
    assert r.raw_payload is None
