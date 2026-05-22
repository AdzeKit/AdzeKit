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
        "command": "review",
        "hour": 16,
        "minute": 0,
        "weekdays": [5],  # Friday (launchd: 1=Mon, 5=Fri)
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


def install(settings: Settings | None = None) -> list[Path]:
    """Generate, write, and load launchd plist files.

    Returns list of installed plist paths.
    """
    settings = settings or get_settings()
    LAUNCH_AGENTS_DIR.mkdir(parents=True, exist_ok=True)

    installed: list[Path] = []
    for name, schedule in SCHEDULES.items():
        xml = _generate_plist(name, schedule, settings.shed)
        plist_path = LAUNCH_AGENTS_DIR / f"{PLIST_PREFIX}.{name}.plist"
        plist_path.write_text(xml, encoding="utf-8")

        subprocess.run(
            ["launchctl", "load", str(plist_path)],
            capture_output=True,
        )
        installed.append(plist_path)

    return installed


def uninstall(settings: Settings | None = None) -> list[Path]:
    """Unload and remove launchd plist files.

    Returns list of removed plist paths.
    """
    settings = settings or get_settings()
    removed: list[Path] = []

    for name in SCHEDULES:
        plist_path = LAUNCH_AGENTS_DIR / f"{PLIST_PREFIX}.{name}.plist"
        if not plist_path.exists():
            continue

        subprocess.run(
            ["launchctl", "unload", str(plist_path)],
            capture_output=True,
        )
        plist_path.unlink()
        removed.append(plist_path)

    return removed
