"""Tests for pick_latest_pair() in lol_html_viewer_auto."""

import json
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import lol_html_viewer_auto


def _write(path: Path, content: dict):
    path.write_text(json.dumps(content), encoding="utf-8")


class TestPickLatestPair:
    def test_returns_correct_pair(self, tmp_path):
        _write(tmp_path / "JP1_100.json", {"metadata": {"matchId": "JP1_100"}})
        _write(tmp_path / "JP1_100_timeline.json", {})
        match, tl = lol_html_viewer_auto.pick_latest_pair(tmp_path)
        assert match.name == "JP1_100.json"
        assert tl.name == "JP1_100_timeline.json"

    def test_picks_newest_when_multiple(self, tmp_path):
        _write(tmp_path / "JP1_100.json", {})
        _write(tmp_path / "JP1_100_timeline.json", {})
        time.sleep(0.05)
        _write(tmp_path / "JP1_200.json", {})
        _write(tmp_path / "JP1_200_timeline.json", {})
        match, tl = lol_html_viewer_auto.pick_latest_pair(tmp_path)
        assert match.name == "JP1_200.json"
        assert tl.name == "JP1_200_timeline.json"

    def test_raises_if_no_match(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="No match JSON"):
            lol_html_viewer_auto.pick_latest_pair(tmp_path)

    def test_raises_if_no_timeline(self, tmp_path):
        _write(tmp_path / "JP1_100.json", {})
        with pytest.raises(FileNotFoundError, match="No timeline JSON"):
            lol_html_viewer_auto.pick_latest_pair(tmp_path)

    def test_falls_back_to_latest_timeline(self, tmp_path, capsys):
        """If the matching timeline is missing, fall back to the latest available."""
        _write(tmp_path / "JP1_100.json", {})
        _write(tmp_path / "JP1_999_timeline.json", {})  # mismatched ID
        match, tl = lol_html_viewer_auto.pick_latest_pair(tmp_path)
        assert match.name == "JP1_100.json"
        assert tl.name == "JP1_999_timeline.json"
        captured = capsys.readouterr()
        assert "WARN" in captured.out
