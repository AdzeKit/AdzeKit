"""macOS launchd automation for AdzeKit.

Generates, installs, and removes launchd plist files in
~/Library/LaunchAgents/ to schedule daily-start, daily-close,
and prune-drafts commands.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
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
    "prune-drafts": {
        "command": "prune-drafts",
        "hour": 9,
        "minute": 0,
        "weekdays": [0],  # Sunday (launchd: 0=Sunday)
    },
}


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
    args.extend(["--shed", str(shed_path), schedule["command"]])

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
