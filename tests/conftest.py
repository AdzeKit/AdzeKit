"""Shared fixtures for AdzeKit tests."""

import pytest

from adzekit.config import Settings


@pytest.fixture
def workspace(tmp_path):
    """A temporary AdzeKit shed rooted in tmp_path.

    Creates the directory tree and .adzekit marker but does NOT seed
    example content (loops, projects, etc.) so tests start with a
    clean slate.  Use ``init_shed()`` explicitly if you need the full
    seed behaviour.
    """
    settings = Settings(shed=tmp_path)
    settings.write_marker()
    settings.ensure_shed()
    return settings
