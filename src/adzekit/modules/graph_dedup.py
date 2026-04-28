"""Deterministic duplicate detection over the knowledge graph.

No LLM. Uses difflib's SequenceMatcher (Ratcliff-Obershelp) plus a
substring-inclusion bonus, grouped within entity type via union-find.

Catches the common cases that show up when entities are extracted from
free-form tags and notes:

  - Single-character typos:        adam-guary  ↔ adam-gurary
  - Short-vs-full first name:      rob-signoretti ↔ robert-signoretti
  - Stem/longer suffix:            aer-compliance ↔ aer-compliancemanagement
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path

from adzekit.config import Settings
from adzekit.models import EntityType, KnowledgeGraph


@dataclass
class DuplicateMember:
    name: str
    entity_type: str
    degree: int
    sources: list[str]


@dataclass
class DuplicateGroup:
    entity_type: str
    members: list[DuplicateMember]
    similarity: float
    suggested_canonical: str


def _similarity(a: str, b: str) -> float:
    """0..1 score combining sequence ratio + substring-inclusion bonus."""
    if a == b:
        return 1.0
    seq = SequenceMatcher(None, a, b).ratio()
    if a in b or b in a:
        shorter, longer = (a, b) if len(a) <= len(b) else (b, a)
        if len(shorter) >= 4 and len(longer) - len(shorter) >= 2:
            return max(seq, 0.86)
    return seq


def find_duplicates(
    graph: KnowledgeGraph,
    threshold: float = 0.85,
    min_length: int = 4,
) -> list[DuplicateGroup]:
    """Cluster likely-duplicate entities, restricted within entity type.

    Args:
        threshold: minimum similarity for two names to be linked. Names ≤ 8
            characters use a stricter threshold (max(threshold, 0.9)) to
            avoid false positives like 'mike-foo' ↔ 'mike-bar'.
        min_length: ignore entity names shorter than this.

    Returns groups sorted by descending min-similarity (most certain dupes first).
    """
    degree: dict[str, int] = {}
    for rel in graph.relationships:
        degree[rel.source] = degree.get(rel.source, 0) + 1
        degree[rel.target] = degree.get(rel.target, 0) + 1

    by_type: dict[EntityType, list[str]] = {}
    for entity in graph.entities.values():
        if len(entity.name) >= min_length:
            by_type.setdefault(entity.entity_type, []).append(entity.name)

    groups: list[DuplicateGroup] = []

    for etype, names in by_type.items():
        names.sort()

        parent = {n: n for n in names}

        def find(x: str) -> str:
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(a: str, b: str) -> None:
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[ra] = rb

        # Pair scores keyed by sorted-tuple so we can recover them later.
        scores: dict[tuple[str, str], float] = {}
        for i, a in enumerate(names):
            for b in names[i + 1:]:
                # Stricter threshold for short names.
                local_thr = max(threshold, 0.9) if max(len(a), len(b)) <= 8 else threshold
                s = _similarity(a, b)
                if s >= local_thr:
                    union(a, b)
                    scores[(a, b)] = s

        clusters: dict[str, list[str]] = {}
        for n in names:
            clusters.setdefault(find(n), []).append(n)

        for cluster in clusters.values():
            if len(cluster) < 2:
                continue

            pair_sims: list[float] = []
            for i, a in enumerate(cluster):
                for b in cluster[i + 1:]:
                    pair_sims.append(scores.get(tuple(sorted([a, b])), _similarity(a, b)))
            min_sim = min(pair_sims) if pair_sims else 1.0

            # Canonical = most-connected name; tiebreak: longer, then lex.
            canonical = max(
                cluster,
                key=lambda n: (degree.get(n, 0), len(n), n),
            )

            members = [
                DuplicateMember(
                    name=n,
                    entity_type=etype.value,
                    degree=degree.get(n, 0),
                    sources=graph.entities[n].sources[:5],
                )
                for n in sorted(cluster)
            ]
            groups.append(
                DuplicateGroup(
                    entity_type=etype.value,
                    members=members,
                    similarity=min_sim,
                    suggested_canonical=canonical,
                )
            )

    groups.sort(key=lambda g: -g.similarity)
    return groups


# ---------------------------------------------------------------------------
# Apply (find-and-replace across backbone)
# ---------------------------------------------------------------------------


def _atomic_write(path: Path, content: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.rename(path)


def _backbone_files(settings: Settings) -> list[Path]:
    """All .md files where graph references should be rewritten.

    Scope is the human-authored backbone: daily/, loops/, projects/,
    knowledge/, reviews/, plus bench.md. Skips stock/, drafts/, graph/
    (agent-managed or workbench).
    """
    files: list[Path] = []
    for d in [
        settings.daily_dir,
        settings.loops_dir,
        settings.projects_dir,
        settings.knowledge_dir,
        settings.reviews_dir,
    ]:
        if d.exists():
            files.extend(p for p in d.rglob("*.md") if p.is_file())
    if settings.bench_path.exists():
        files.append(settings.bench_path)
    return files


def apply_merges(
    merges: list[tuple[str, str]],
    settings: Settings,
    dry_run: bool = False,
) -> dict:
    """Rewrite [[from]] and #from references to point at the canonical name.

    Conservative scope: only rewrites:
      - ``[[from]]`` (and ``[[from|alias]]``) → ``[[to]]`` / ``[[to|alias]]``
      - ``#from`` (with non-tag-char boundaries) → ``#to``

    Bare appearances of the slug in prose are NOT touched — too risky to
    silently rewrite human-written sentences.

    Args:
        merges: list of (from_name, to_name) pairs.
        dry_run: when True, returns what would change without writing.

    Returns a summary dict with total_replacements and per-file detail.
    """
    files_changed: list[dict] = []
    total = 0

    for path in _backbone_files(settings):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue

        new_text = text
        per_file_total = 0
        per_kind: dict[str, int] = {}

        for old, new in merges:
            if not old or not new or old == new:
                continue
            old_e = re.escape(old)

            # [[old]] (preserve any |alias)
            def _wl_sub(m: re.Match, _new: str = new) -> str:
                alias = m.group(1) or ""
                return f"[[{_new}{alias}]]"

            wl_pat = re.compile(rf"\[\[{old_e}(\|[^\]]+)?\]\]")
            new_text, n_wl = wl_pat.subn(_wl_sub, new_text)

            tag_pat = re.compile(
                rf"(?<![A-Za-z0-9_-])#{old_e}(?![A-Za-z0-9_-])"
            )
            new_text, n_tag = tag_pat.subn(f"#{new}", new_text)

            if n_wl + n_tag > 0:
                key = f"{old}→{new}"
                per_kind[f"{key}:wikilink"] = per_kind.get(f"{key}:wikilink", 0) + n_wl
                per_kind[f"{key}:tag"] = per_kind.get(f"{key}:tag", 0) + n_tag
                per_file_total += n_wl + n_tag

        if per_file_total > 0:
            rel = str(path.relative_to(settings.shed))
            files_changed.append({
                "path": rel,
                "replacements": per_file_total,
                "by_kind": per_kind,
            })
            total += per_file_total
            if not dry_run:
                _atomic_write(path, new_text)

    return {
        "dry_run": dry_run,
        "total_replacements": total,
        "files_changed": files_changed,
    }
