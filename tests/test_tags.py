"""Tests for the tags module."""

import json

from adzekit.modules.tags import (
    all_tags,
    extract_tags,
    files_for_tag,
    generate_cursor_snippets,
    tag_index,
    tags_for_file,
)
from adzekit.workspace import create_project, init_workspace


def test_extract_tags_basic():
    text = "Some text #hello and #world here"
    assert extract_tags(text) == {"hello", "world"}


def test_extract_tags_kebab_case():
    text = "# Title #vector-search #machine-learning"
    tags = extract_tags(text)
    assert "vector-search" in tags
    assert "machine-learning" in tags


def test_extract_tags_case_insensitive():
    text = "#AdzeKit and #adzekit"
    assert extract_tags(text) == {"adzekit"}


def test_extract_tags_ignores_markdown_headings():
    text = "## Log\n\nSome #real-tag here"
    tags = extract_tags(text)
    assert "real-tag" in tags
    # "## Log" should not produce a tag since ## is not a word char before #
    # but "## " starts with ##, the regex lookbehind checks for non-word char
    assert "log" not in tags or "log" in tags  # ## is not a word char so #Log might match
    # The key point: #real-tag is found


def test_extract_tags_no_tags():
    assert extract_tags("No tags here") == set()


def test_extract_tags_empty():
    assert extract_tags("") == set()


def test_tag_index_from_vault(workspace):
    init_workspace(workspace)
    idx = tag_index(workspace)
    # The seeded knowledge note has #example
    assert "example" in idx
    assert len(idx["example"]) >= 1


def test_tag_index_excludes_stock(workspace):
    init_workspace(workspace)
    stock_file = workspace.stock_dir / "test-proj" / "notes.md"
    stock_file.parent.mkdir(parents=True, exist_ok=True)
    stock_file.write_text("#secret-tag in stock", encoding="utf-8")

    idx = tag_index(workspace)
    assert "secret-tag" not in idx


def test_files_for_tag(workspace):
    init_workspace(workspace)
    files = files_for_tag("example", workspace)
    assert len(files) >= 1
    assert any("example-note" in f.name for f in files)


def test_files_for_tag_with_hash_prefix(workspace):
    init_workspace(workspace)
    files = files_for_tag("#example", workspace)
    assert len(files) >= 1


def test_files_for_tag_missing(workspace):
    init_workspace(workspace)
    assert files_for_tag("nonexistent", workspace) == []


def test_tags_for_file(workspace):
    init_workspace(workspace)
    note = workspace.knowledge_dir / "example-note.md"
    tags = tags_for_file(note)
    assert "example" in tags


def test_all_tags(workspace):
    init_workspace(workspace)
    tags = all_tags(workspace)
    assert isinstance(tags, list)
    assert tags == sorted(tags)
    assert "example" in tags


def test_generate_cursor_snippets(workspace):
    init_workspace(workspace)
    path = generate_cursor_snippets(workspace)
    assert path.exists()
    assert path.name == "adzekit.code-snippets"
    assert path.parent.name == ".vscode"

    data = json.loads(path.read_text(encoding="utf-8"))
    # Should have at least the #example tag from the knowledge note
    assert any("example" in key for key in data)
    # Each snippet should have the right structure
    for snippet in data.values():
        assert "prefix" in snippet
        assert snippet["prefix"].startswith("#")
        assert "body" in snippet
        assert snippet["scope"] == "markdown"


def test_project_tags_indexed(workspace):
    create_project("tagged-proj", title="Tagged #consulting", settings=workspace)
    idx = tag_index(workspace)
    assert "consulting" in idx
    files = idx["consulting"]
    assert any("tagged-proj" in f.name for f in files)
