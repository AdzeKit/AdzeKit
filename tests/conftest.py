"""Shared fixtures for AdzeKit tests."""

import pytest

from adzekit.config import Settings


@pytest.fixture
def workspace(tmp_path):
    """A temporary AdzeKit workspace rooted in tmp_path."""
    settings = Settings(workspace=tmp_path)
    settings.ensure_workspace()
    return settings
