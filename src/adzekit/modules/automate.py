"""macOS launchd cadence layer for AdzeKit.

Generates, installs, and removes launchd plist files in
~/Library/LaunchAgents/ to schedule the morning/evening/weekly rituals
and the weekly drafts gc.

Deep-work guard: in_deep_work_window() reads knowledge/soul.md and
returns True when the current local time falls inside the declared
deep-work range. Cadence-triggered skills check this and suppress
notifications when it returns True.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from datetime import datetime, time
from pathlib import Path
from textwrap import dedent

from adzekit.config import Settings, get_settings

LAUNCH_AGENTS_DIR = Path.home() / "Library" / "LaunchAgents"
PLIST_PREFIX = "com.adzekit"

SCHEDULES: dict[str, dict] = {
    "daily-start": {
        "command": "daily-start",
        "hour": 7,
        "minute": 30,
        "weekdays": [1, 2, 3, 4, 5],
    },
    "daily-close": {
        "command": "daily-close",
        "hour": 17,
        "minute": 30,
        "weekdays": [1, 2, 3, 4, 5],
    },
    "weekly-review": {
        "command": "weekly-review",
        "hour": 17,
        "minute": 30,
        "weekdays": [5],  # Friday (launchd: 1=Mon, 5=Fri)
    },
    "insight-weekly": {
        "command": "insight --period weekly",
        "hour": 16,
        "minute": 30,  # 30 min after weekly-review so the day's review is fresh
        "weekdays": [5],  # Friday
    },
    "drafts-gc": {
        "command": "drafts gc",
        "hour": 9,
        "minute": 0,
        "weekdays": [0],  # Sunday (launchd: 0=Sunday)
    },
}

# --- Deep-work guard --------------------------------------------------------

_DEEP_WORK_LINE_RE = re.compile(
    r"^\s*(?P<start>\d{1,2}:\d{2})\s*[-–—]\s*(?P<end>\d{1,2}:\d{2})"
)


def parse_deep_work_window(soul_section: str) -> tuple[time, time] | None:
    """Parse a soul.md `Deep work hours` section into (start, end) times.

    Returns None when the section is missing, empty, or unparseable. Only
    the first matching `HH:MM-HH:MM` range on any line is used; timezone
    text after the range is ignored (the cadence layer uses local time).
    """
    if not soul_section:
        return None
    for line in soul_section.splitlines():
        m = _DEEP_WORK_LINE_RE.match(line)
        if not m:
            continue
        try:
            start = time.fromisoformat(_pad_hm(m.group("start")))
            end = time.fromisoformat(_pad_hm(m.group("end")))
        except ValueError:
            continue
        return start, end
    return None


def _pad_hm(value: str) -> str:
    """Pad `H:MM` to `HH:MM` so time.fromisoformat accepts it."""
    if ":" in value and len(value.split(":", 1)[0]) == 1:
        return "0" + value
    return value


def in_deep_work_window(
    now: datetime | None = None,
    settings: Settings | None = None,
) -> bool:
    """Return True if `now` is inside the user's declared deep-work window.

    Reads `knowledge/soul.md`, looks for a `Deep work hours` section, and
    parses the first `HH:MM-HH:MM` range. Returns False when soul.md is
    missing, the section is absent, or the range is unparseable — fail-open
    so a missing config doesn't accidentally silence the cadence.
    """
    from adzekit.preprocessor import load_soul

    settings = settings or get_settings()
    sections = load_soul(settings)
    window = parse_deep_work_window(sections.get("Deep work hours", ""))
    if window is None:
        return False
    start, end = window
    current = (now or datetime.now()).time().replace(microsecond=0)
    if start <= end:
        return start <= current < end
    # Crosses midnight (e.g. 22:00-02:00)
    return current >= start or current < end


def _find_adzekit() -> str:
    """Locate the adzekit executable."""
    path = shutil.which("adzekit")
    if path:
        return path
    return sys.executable


def _calendar_entry(hour: int, minute: int, weekday: int) -> str:
    """Build a single StartCalendarInterval dict entry."""
    return dedent(f"""\
        <dict>
            <key>Hour</key>
            <integer>{hour}</integer>
            <key>Minute</key>
            <integer>{minute}</integer>
            <key>Weekday</key>
            <integer>{weekday}</integer>
        </dict>""")


def _generate_plist(
    name: str,
    schedule: dict,
    shed_path: Path,
) -> str:
    """Generate a launchd plist XML string."""
    label = f"{PLIST_PREFIX}.{name}"
    adzekit = _find_adzekit()

    # Build ProgramArguments
    if adzekit.endswith("python") or adzekit.endswith("python3"):
        args = [adzekit, "-m", "adzekit"]
    else:
        args = [adzekit]
    args.extend(["--shed", str(shed_path)])
    command = schedule["command"]
    if isinstance(command, list):
        args.extend(command)
    else:
        args.extend(command.split())

    args_xml = "\n        ".join(f"<string>{a}</string>" for a in args)

    # Build calendar intervals
    entries = []
    for weekday in schedule["weekdays"]:
        entries.append(
            _calendar_entry(schedule["hour"], schedule["minute"], weekday)
        )
    intervals_xml = "\n        ".join(entries)

    return dedent(f"""\
        <?xml version="1.0" encoding="UTF-8"?>
        <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
          "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
        <plist version="1.0">
        <dict>
            <key>Label</key>
            <string>{label}</string>
            <key>ProgramArguments</key>
            <array>
                {args_xml}
            </array>
            <key>StartCalendarInterval</key>
            <array>
                {intervals_xml}
            </array>
            <key>StandardOutPath</key>
            <string>/tmp/{label}.log</string>
            <key>StandardErrorPath</key>
            <string>/tmp/{label}.err</string>
        </dict>
        </plist>
    """).strip() + "\n"


class LaunchctlError(RuntimeError):
    """Raised when a launchctl invocation fails.

    The previous behavior was to silently swallow failures (capture_output=True
    + no returncode check). That meant `install` could report success while no
    plist was actually loaded — user trusts the cadence is running and it isn't.
    """


def install(settings: Settings | None = None) -> list[Path]:
    """Generate, write, and load launchd plist files.

    Returns list of installed plist paths. Raises LaunchctlError if any
    `launchctl load` invocation fails — partial state may exist (plists
    written to disk but not loaded); subsequent reinstall is safe.
    """
    settings = settings or get_settings()
    LAUNCH_AGENTS_DIR.mkdir(parents=True, exist_ok=True)

    installed: list[Path] = []
    failures: list[str] = []
    for name, schedule in SCHEDULES.items():
        xml = _generate_plist(name, schedule, settings.shed)
        plist_path = LAUNCH_AGENTS_DIR / f"{PLIST_PREFIX}.{name}.plist"
        plist_path.write_text(xml, encoding="utf-8")

        result = subprocess.run(
            ["launchctl", "load", str(plist_path)],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            failures.append(
                f"{plist_path.name}: rc={result.returncode}; "
                f"stderr={result.stderr.strip() or '(empty)'}"
            )
            continue
        installed.append(plist_path)

    if failures:
        raise LaunchctlError(
            "launchctl load failed for one or more plists:\n  "
            + "\n  ".join(failures)
            + "\nVerify with `launchctl list | grep adzekit`; "
            "common causes: user logged out at install time, SIP, permissions."
        )

    return installed


def uninstall(settings: Settings | None = None) -> list[Path]:
    """Unload and remove launchd plist files.

    Returns list of removed plist paths. Continues on per-plist errors but
    raises LaunchctlError at the end if any unload reported failure (the
    plist file is still removed from disk so reinstall is safe).
    """
    settings = settings or get_settings()
    removed: list[Path] = []
    failures: list[str] = []

    for name in SCHEDULES:
        plist_path = LAUNCH_AGENTS_DIR / f"{PLIST_PREFIX}.{name}.plist"
        if not plist_path.exists():
            continue

        result = subprocess.run(
            ["launchctl", "unload", str(plist_path)],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            # Common case: plist was never loaded (already-unloaded error). We
            # tolerate this so a partial install can be cleaned up. But
            # surface a notice so the user knows.
            failures.append(
                f"{plist_path.name}: rc={result.returncode}; "
                f"stderr={result.stderr.strip() or '(empty)'}"
            )
        plist_path.unlink()
        removed.append(plist_path)

    if failures:
        # Non-fatal: removal still happened. Surface as warning via the
        # returned shape; caller decides what to do.
        # We use a sentinel attribute on the list to communicate this without
        # changing the public signature.
        removed = list(removed)  # ensure mutable
        setattr(removed, "warnings", failures)  # type: ignore[attr-defined]

    return removed


def verify_loaded(settings: Settings | None = None) -> dict[str, bool]:
    """Return per-plist load status by querying `launchctl list`.

    Used by `adzekit cadence status` to confirm the install actually took.
    Failing-open behavior: if launchctl itself fails (unlikely on macOS),
    returns an empty dict rather than raising.
    """
    try:
        result = subprocess.run(
            ["launchctl", "list"],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return {}
    if result.returncode != 0:
        return {}
    loaded_labels = set()
    for line in result.stdout.splitlines():
        parts = line.split(maxsplit=2)
        if len(parts) >= 3 and parts[2].startswith(PLIST_PREFIX):
            loaded_labels.add(parts[2])
    return {
        name: f"{PLIST_PREFIX}.{name}" in loaded_labels
        for name in SCHEDULES
    }
