"""Skill distillation: detect repeated edit patterns in accepted drafts.

When the human consistently rewrites the same section of a generated draft
the same way, the pattern wants to become a skill. The /distill workflow:

  1. Pair each preserved original (drafts/archive/originals/X.md) with its
     accepted counterpart (drafts/archive/X.md).
  2. Diff the two; record per-skill patterns.
  3. Emit a proposal markdown to drafts/skill-proposals/<slug>.md when a
     pattern repeats ≥ 3 times within the rolling window.
  4. Surface in INBOX.

The CLI command `adzekit distill` runs the deterministic scan and emits
proposals. It does NOT invoke an LLM — the proposal markdown is templated
from the diff evidence; richer phrasing is the job of an adapter skill
that reads the proposal afterward.
"""

from __future__ import annotations

import difflib
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path

from adzekit.config import Settings, get_settings
from adzekit.preprocessor import read_draft_frontmatter, strip_draft_frontmatter

# Filename pattern: <skill>-YYYY-MM-DD-HHMMSS-<host>[-N].md
# Post-B2 the time portion is HHMMSS (6 digits). Pre-B2 drafts archived
# before the upgrade may still have HHMM (4 digits); accept either so
# distillation works across the transition.
_FILENAME_RE = re.compile(
    r"^(?P<skill>[a-z0-9-]+?)"
    r"-(?P<date>\d{4}-\d{2}-\d{2})"
    r"-(?P<time>\d{4,6})"
    r"-(?P<host>[a-z0-9-]+?)"
    r"(?:-\d+)?"  # optional collision suffix
    r"\.md$"
)


@dataclass
class DiffPair:
    skill: str
    original_path: Path
    accepted_path: Path
    accepted_date: date
    diff_lines: list[str] = field(default_factory=list)


@dataclass
class PatternCluster:
    skill: str
    signature: str
    instances: list[DiffPair] = field(default_factory=list)


def _parse_filename_skill(name: str) -> tuple[str, date] | None:
    m = _FILENAME_RE.match(name)
    if not m:
        return None
    try:
        d = date.fromisoformat(m.group("date"))
    except ValueError:
        return None
    return m.group("skill"), d


def _list_pairs(settings: Settings) -> list[DiffPair]:
    """Pair each original with its accepted counterpart by filename."""
    originals_dir = settings.drafts_dir / "archive" / "originals"
    accepted_dir = settings.drafts_dir / "archive"
    if not originals_dir.exists() or not accepted_dir.exists():
        return []

    pairs: list[DiffPair] = []
    for original in sorted(originals_dir.glob("*.md")):
        accepted = accepted_dir / original.name
        if not accepted.exists():
            continue
        parsed = _parse_filename_skill(original.name)
        if parsed is None:
            continue
        skill, accepted_date = parsed
        original_body = strip_draft_frontmatter(original)
        accepted_body = strip_draft_frontmatter(accepted) if accepted.read_text(encoding="utf-8").startswith("<!--") else accepted.read_text(encoding="utf-8")
        if original_body == accepted_body:
            continue
        diff = list(difflib.unified_diff(
            original_body.splitlines(),
            accepted_body.splitlines(),
            lineterm="",
            n=1,
        ))
        pairs.append(DiffPair(
            skill=skill,
            original_path=original,
            accepted_path=accepted,
            accepted_date=accepted_date,
            diff_lines=diff,
        ))
    return pairs


def _diff_signature(pair: DiffPair) -> str:
    """Compute a structural signature for a diff so similar edits cluster.

    Strategy: take the set of `-` (removed) and `+` (added) lines, strip
    leading punctuation/whitespace, lowercase, sort, and hash by tuple. Two
    diffs with the same set of substantive line-level changes get the same
    signature, regardless of order.
    """
    minus: set[str] = set()
    plus: set[str] = set()
    for line in pair.diff_lines:
        if line.startswith("--- ") or line.startswith("+++ ") or line.startswith("@@"):
            continue
        if line.startswith("-"):
            minus.add(_normalize(line[1:]))
        elif line.startswith("+"):
            plus.add(_normalize(line[1:]))
    if not minus and not plus:
        return "no-op"
    return "|".join(sorted(minus)) + "==>" + "|".join(sorted(plus))


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def cluster_patterns(
    pairs: list[DiffPair],
    *,
    window_days: int = 60,
    today: date | None = None,
) -> list[PatternCluster]:
    """Group diff pairs by (skill, signature) within the rolling window."""
    today = today or date.today()
    cutoff = today - timedelta(days=window_days)
    grouped: dict[tuple[str, str], list[DiffPair]] = defaultdict(list)
    for pair in pairs:
        if pair.accepted_date < cutoff:
            continue
        sig = _diff_signature(pair)
        if sig == "no-op":
            continue
        grouped[(pair.skill, sig)].append(pair)
    clusters = [
        PatternCluster(skill=skill, signature=sig, instances=instances)
        for (skill, sig), instances in grouped.items()
    ]
    clusters.sort(key=lambda c: -len(c.instances))
    return clusters


def _slugify(text: str, max_len: int = 60) -> str:
    text = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    if not text:
        text = "pattern"
    return text[:max_len]


def _proposal_body(cluster: PatternCluster) -> str:
    """Render a proposal markdown body from a cluster."""
    n = len(cluster.instances)
    first_dates = sorted({p.accepted_date.isoformat() for p in cluster.instances})
    minus, plus = cluster.signature.split("==>", 1)
    minus_lines = [s for s in minus.split("|") if s]
    plus_lines = [s for s in plus.split("|") if s]

    lines = [
        f"# Proposed skill / patch: {cluster.skill} repeated edit pattern",
        "",
        f"Detected **{n}** occurrences in the last 60 days where the human consistently",
        f"edited the output of the `{cluster.skill}` skill the same way.",
        "",
        "## Evidence",
        "",
    ]
    for pair in cluster.instances:
        lines.append(
            f"- `{pair.accepted_path.name}` (accepted {pair.accepted_date.isoformat()})"
        )
    lines += [
        "",
        "## Pattern (deterministic signature)",
        "",
        "What gets removed (frequency: every instance):",
    ]
    if minus_lines:
        lines += [f"- `{m}`" for m in minus_lines[:10]]
    else:
        lines.append("- (no consistent removals)")
    lines += ["", "What gets added (frequency: every instance):"]
    if plus_lines:
        lines += [f"- `{p}`" for p in plus_lines[:10]]
    else:
        lines.append("- (no consistent additions)")
    lines += [
        "",
        "## Suggested action",
        "",
        f"Update the `{cluster.skill}` skill (in core or in the workspace override) to",
        "bake this pattern in. Two routes:",
        "",
        "1. **Edit the existing skill** — if the change is a small rule addition (e.g.",
        "   reclassify a sender, change a phrase, add a section), append it to the skill's",
        "   rules block. Lower-risk.",
        "2. **Author a new skill** — if the pattern is large enough to warrant its own",
        "   command, propose a new skill markdown and a slash command name.",
        "",
        "## How to promote",
        "",
        "```",
        "adzekit drafts list",
        "adzekit drafts accept <N>     # this proposal moves to skills/ or workspace",
        "```",
        "",
        f"_First seen: {first_dates[0]}. Most recent: {first_dates[-1]}._",
    ]
    return "\n".join(lines) + "\n"


def run_distill(
    *,
    settings: Settings | None = None,
    min_occurrences: int = 3,
    window_days: int = 60,
    today: date | None = None,
) -> list[Path]:
    """Scan accepted drafts for repeated edit patterns and emit proposals.

    Returns the list of proposal paths written.
    """
    settings = settings or get_settings()
    today = today or date.today()

    pairs = _list_pairs(settings)
    clusters = cluster_patterns(pairs, window_days=window_days, today=today)

    proposals_dir = settings.drafts_dir / "skill-proposals"
    proposals_dir.mkdir(parents=True, exist_ok=True)

    # Lazy import to avoid circular dep (preprocessor calls drafts module).
    from adzekit.preprocessor import write_draft_with_frontmatter

    written: list[Path] = []
    for cluster in clusters:
        if len(cluster.instances) < min_occurrences:
            continue
        slug = _slugify(f"{cluster.skill}-{cluster.signature.split('==>')[0][:40]}")
        body = _proposal_body(cluster)
        # Use write_draft_with_frontmatter so the proposal gets provenance +
        # an INBOX entry. Override the destination by writing into
        # skill-proposals/ via a parent target.
        ts = datetime.combine(today, datetime.min.time())
        path = write_draft_with_frontmatter(
            f"distill-{slug}",
            body=body,
            settings=settings,
            timestamp=ts,
            summary=f"{len(cluster.instances)} occurrences of {cluster.skill} pattern",
            confidence=min(1.0, 0.5 + 0.1 * len(cluster.instances)),
        )
        # Move from drafts/ root into drafts/skill-proposals/
        target = proposals_dir / path.name
        target.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
        path.unlink()
        # Fix up the INBOX line so it points at the new location.
        _retarget_inbox_line(settings, path.name, target)
        written.append(target)

    return written


def _retarget_inbox_line(settings: Settings, filename: str, new_path: Path) -> None:
    """Rewrite the INBOX entry for `filename` to point at the new path.

    Updates the sidecar entry at drafts/INBOX.d/{stem}.entry (post-B1) and
    regenerates the INBOX.md view. Falls back to legacy INBOX.md replacement
    when no sidecar is present.
    """
    old_marker = f"`drafts/{filename}`"
    try:
        rel = str(new_path.resolve().relative_to(settings.shed.resolve()))
    except ValueError:
        rel = str(new_path)
    new_marker = f"`{rel}`"

    sidecar = settings.drafts_dir / "INBOX.d" / f"{Path(filename).stem}.entry"
    if sidecar.exists():
        text = sidecar.read_text(encoding="utf-8")
        sidecar.write_text(text.replace(old_marker, new_marker), encoding="utf-8")
        from adzekit.preprocessor import _regenerate_inbox_view
        _regenerate_inbox_view(settings)
        return

    inbox = settings.drafts_dir / "INBOX.md"
    if not inbox.exists():
        return
    text = inbox.read_text(encoding="utf-8")
    inbox.write_text(text.replace(old_marker, new_marker), encoding="utf-8")
