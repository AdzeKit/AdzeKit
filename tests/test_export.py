"""Tests for markdown-to-docx export."""

import shutil

import pytest

from adzekit.modules.export import to_docx

pytestmark = pytest.mark.skipif(
    shutil.which("pandoc") is None,
    reason="pandoc not installed",
)


def test_to_docx_basic(tmp_path):
    md = tmp_path / "doc.md"
    md.write_text("# Hello\n\nSome content.\n", encoding="utf-8")

    result = to_docx(md)
    assert result.exists()
    assert result.suffix == ".docx"
    assert result.stem == "doc"
    assert result.stat().st_size > 0


def test_to_docx_custom_output(tmp_path):
    md = tmp_path / "input.md"
    md.write_text("# Test\n", encoding="utf-8")
    out = tmp_path / "subdir" / "output.docx"
    out.parent.mkdir()

    result = to_docx(md, out)
    assert result == out
    assert result.exists()


def test_to_docx_missing_source(tmp_path):
    missing = tmp_path / "nonexistent.md"
    with pytest.raises(FileNotFoundError):
        to_docx(missing)


def test_to_docx_with_tables(tmp_path):
    """Pandoc handles markdown tables in the conversion."""
    md = tmp_path / "tables.md"
    md.write_text(
        "# Report\n\n| Col A | Col B |\n|-------|-------|\n| 1 | 2 |\n",
        encoding="utf-8",
    )
    result = to_docx(md)
    assert result.exists()
    assert result.stat().st_size > 0
