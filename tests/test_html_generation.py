"""Integration tests: generate HTML from minimal fixture data."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import lol_html_viewer_auto
from tests.fixtures import MINIMAL_MATCH, MINIMAL_TIMELINE


def _write_fixtures(tmp_path: Path):
    (tmp_path / "JP1_000000001.json").write_text(
        json.dumps(MINIMAL_MATCH), encoding="utf-8"
    )
    (tmp_path / "JP1_000000001_timeline.json").write_text(
        json.dumps(MINIMAL_TIMELINE), encoding="utf-8"
    )


class TestHtmlGeneration:
    def test_generates_html_file(self, tmp_path, monkeypatch):
        _write_fixtures(tmp_path)
        out_dir = tmp_path / "out"
        out_dir.mkdir()

        monkeypatch.setattr(lol_html_viewer_auto, "OUTPUT_DIR", out_dir)
        monkeypatch.setattr(lol_html_viewer_auto, "USER_PUUID", "puuid_0")
        sys.argv = ["lol_html_viewer_auto.py", "--dir", str(tmp_path), "--no-csv"]
        lol_html_viewer_auto.main()

        html_files = list(out_dir.glob("out_*.html"))
        assert len(html_files) == 1

    def test_html_contains_match_id(self, tmp_path, monkeypatch):
        _write_fixtures(tmp_path)
        out_dir = tmp_path / "out"
        out_dir.mkdir()

        monkeypatch.setattr(lol_html_viewer_auto, "OUTPUT_DIR", out_dir)
        monkeypatch.setattr(lol_html_viewer_auto, "USER_PUUID", "puuid_0")
        sys.argv = ["lol_html_viewer_auto.py", "--dir", str(tmp_path), "--no-csv"]
        lol_html_viewer_auto.main()

        html = list(out_dir.glob("out_*.html"))[0].read_text(encoding="utf-8")
        assert "JP1_000000001" in html

    def test_html_contains_player_names(self, tmp_path, monkeypatch):
        _write_fixtures(tmp_path)
        out_dir = tmp_path / "out"
        out_dir.mkdir()

        monkeypatch.setattr(lol_html_viewer_auto, "OUTPUT_DIR", out_dir)
        monkeypatch.setattr(lol_html_viewer_auto, "USER_PUUID", "puuid_0")
        sys.argv = ["lol_html_viewer_auto.py", "--dir", str(tmp_path), "--no-csv"]
        lol_html_viewer_auto.main()

        html = list(out_dir.glob("out_*.html"))[0].read_text(encoding="utf-8")
        assert "Player0" in html
        assert "Player5" in html

    def test_en_lang_html_contains_ally_team(self, tmp_path, monkeypatch):
        _write_fixtures(tmp_path)
        out_dir = tmp_path / "out"
        out_dir.mkdir()

        monkeypatch.setattr(lol_html_viewer_auto, "OUTPUT_DIR", out_dir)
        monkeypatch.setattr(lol_html_viewer_auto, "USER_PUUID", "puuid_0")
        sys.argv = [
            "lol_html_viewer_auto.py", "--dir", str(tmp_path), "--no-csv", "--lang", "en"
        ]
        lol_html_viewer_auto.main()

        html = list(out_dir.glob("out_*.html"))[0].read_text(encoding="utf-8")
        assert "Ally Team" in html

    def test_user_row_highlighted(self, tmp_path, monkeypatch):
        """The user's table row must carry class='user'."""
        _write_fixtures(tmp_path)
        out_dir = tmp_path / "out"
        out_dir.mkdir()

        monkeypatch.setattr(lol_html_viewer_auto, "OUTPUT_DIR", out_dir)
        monkeypatch.setattr(lol_html_viewer_auto, "USER_PUUID", "puuid_0")
        sys.argv = ["lol_html_viewer_auto.py", "--dir", str(tmp_path), "--no-csv"]
        lol_html_viewer_auto.main()

        html = list(out_dir.glob("out_*.html"))[0].read_text(encoding="utf-8")
        assert "<tr class='user'>" in html
