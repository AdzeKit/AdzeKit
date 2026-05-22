"""Tests for launchd automation."""

import os
import xml.etree.ElementTree as ET

from adzekit.cli import main
from adzekit.modules.automate import SCHEDULES, _generate_plist


class TestPlistGeneration:
    def test_daily_start_plist(self, workspace):
        xml = _generate_plist(
            "daily-start", SCHEDULES["daily-start"], workspace.shed,
        )
        assert "com.adzekit.daily-start" in xml
        assert str(workspace.shed) in xml
        assert "daily-start" in xml
        assert "<key>Hour</key>" in xml
        assert "<integer>7</integer>" in xml
        assert "<integer>30</integer>" in xml
        assert "<key>Weekday</key>" in xml

    def test_daily_close_plist(self, workspace):
        xml = _generate_plist(
            "daily-close", SCHEDULES["daily-close"], workspace.shed,
        )
        assert "com.adzekit.daily-close" in xml
        assert "<integer>17</integer>" in xml

    def test_drafts_gc_sunday(self, workspace):
        xml = _generate_plist(
            "drafts-gc", SCHEDULES["drafts-gc"], workspace.shed,
        )
        assert "com.adzekit.drafts-gc" in xml
        assert "<integer>9</integer>" in xml
        assert "<integer>0</integer>" in xml
        # Multi-word command must serialize as separate <string> elements.
        assert "<string>drafts</string>" in xml
        assert "<string>gc</string>" in xml

    def test_all_schedules_valid_xml(self, workspace):
        for name, schedule in SCHEDULES.items():
            xml = _generate_plist(name, schedule, workspace.shed)
            ET.fromstring(xml)

    def test_weekday_entries_count(self, workspace):
        xml = _generate_plist(
            "daily-start", SCHEDULES["daily-start"], workspace.shed,
        )
        assert xml.count("<key>Weekday</key>") == 5  # Mon-Fri

    def test_cli_automate_install_uninstall(self, tmp_path, monkeypatch, capsys):
        main(["init", str(tmp_path / "shed")])

        fake_bin = tmp_path / "bin"
        fake_bin.mkdir()
        fake_launchctl = fake_bin / "launchctl"
        fake_launchctl.write_text("#!/bin/sh\nexit 0\n")
        fake_launchctl.chmod(0o755)
        fake_adzekit = fake_bin / "adzekit"
        fake_adzekit.write_text("#!/bin/sh\nexit 0\n")
        fake_adzekit.chmod(0o755)
        monkeypatch.setenv(
            "PATH", f"{fake_bin}:{os.environ.get('PATH', '')}",
        )

        temp_agents = tmp_path / "LaunchAgents"
        monkeypatch.setattr(
            "adzekit.modules.automate.LAUNCH_AGENTS_DIR", temp_agents,
        )

        main(["--shed", str(tmp_path / "shed"), "automate", "install"])
        output = capsys.readouterr().out
        assert "installed" in output
        assert len(list(temp_agents.glob("*.plist"))) == len(SCHEDULES)

        main(["--shed", str(tmp_path / "shed"), "automate", "uninstall"])
        output = capsys.readouterr().out
        assert "removed" in output
        assert len(list(temp_agents.glob("*.plist"))) == 0
