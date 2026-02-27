"""Tag extraction and indexing.

Scans all markdown files in the shed for inline #tags and builds an
in-memory index. No separate tag registry -- the filesystem is the
source of truth.
"""

import json
import re
from pathlib import Path

from adzekit.config import Settings, get_settings

_TAG_RE = re.compile(r"(?<!\w)#([a-zA-Z][a-zA-Z0-9-]*)")


def extract_tags(text: str) -> set[str]:
    """Extract all #tags from a string.

    Returns lowercased tag names without the leading ``#``.
    """
    return {m.group(1).lower() for m in _TAG_RE.finditer(text)}


def tag_index(settings: Settings | None = None) -> dict[str, list[Path]]:
    """Build a mapping from tag -> list of files that contain it.

    Scans every ``.md`` file in the shed (excluding ``stock/`` and ``drafts/``).
    """
    settings = settings or get_settings()
    index: dict[str, list[Path]] = {}
    stock = settings.stock_dir
    drafts = settings.drafts_dir

    for md in sorted(settings.shed.rglob("*.md")):
        # Skip stock/ and drafts/ -- not part of the backbone
        try:
            md.relative_to(stock)
            continue
        except ValueError:
            pass
        try:
            md.relative_to(drafts)
            continue
        except ValueError:
            pass

        text = md.read_text(encoding="utf-8")
        for tag in extract_tags(text):
            index.setdefault(tag, []).append(md)

    return index


def files_for_tag(
    tag: str, settings: Settings | None = None
) -> list[Path]:
    """Return all files that contain a given tag."""
    tag = tag.lstrip("#").lower()
    idx = tag_index(settings)
    return idx.get(tag, [])


def tags_for_file(path: Path) -> set[str]:
    """Return all tags found in a single file."""
    text = path.read_text(encoding="utf-8")
    return extract_tags(text)


def all_tags(settings: Settings | None = None) -> list[str]:
    """Return a sorted list of every tag in the shed."""
    return sorted(tag_index(settings).keys())


def generate_cursor_snippets(settings: Settings | None = None) -> Path:
    """Generate a .vscode/adzekit.code-snippets file for tag autocomplete.

    Each tag in the shed becomes a snippet triggered by typing ``#``.
    Returns the path to the generated file.
    """
    settings = settings or get_settings()
    tags = all_tags(settings)

    snippets: dict = {}
    for tag in tags:
        snippets[f"tag: {tag}"] = {
            "prefix": f"#{tag}",
            "body": f"#{tag}",
            "scope": "markdown",
            "description": f"AdzeKit tag: #{tag}",
        }

    vscode_dir = settings.shed / ".vscode"
    vscode_dir.mkdir(exist_ok=True)
    snippets_path = vscode_dir / "adzekit.code-snippets"
    snippets_path.write_text(
        json.dumps(snippets, indent=2) + "\n", encoding="utf-8"
    )
    return snippets_path
