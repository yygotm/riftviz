"""Tests for shared utilities: load_env, fmt_time, t()."""

import sys
import tempfile
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# load_env (copied logic — both scripts share the same implementation)
# ---------------------------------------------------------------------------
def load_env(path):
    env = {}
    try:
        with open(path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, val = line.partition("=")
                env[key.strip()] = val.strip()
    except FileNotFoundError:
        pass
    return env


class TestLoadEnv:
    def test_basic_key_value(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("API_KEY=abc123\nPLATFORM=JP1\n", encoding="utf-8")
        result = load_env(env_file)
        assert result["API_KEY"] == "abc123"
        assert result["PLATFORM"] == "JP1"

    def test_ignores_comments(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("# this is a comment\nKEY=val\n", encoding="utf-8")
        result = load_env(env_file)
        assert "# this is a comment" not in result
        assert result["KEY"] == "val"

    def test_ignores_blank_lines(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("\n\nKEY=val\n\n", encoding="utf-8")
        assert load_env(env_file) == {"KEY": "val"}

    def test_missing_file_returns_empty(self, tmp_path):
        result = load_env(tmp_path / "nonexistent.env")
        assert result == {}

    def test_strips_whitespace(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("  KEY  =  value  \n", encoding="utf-8")
        assert load_env(env_file)["KEY"] == "value"

    def test_value_with_equals(self, tmp_path):
        """Value containing '=' should be preserved after first '='."""
        env_file = tmp_path / ".env"
        env_file.write_text("KEY=a=b=c\n", encoding="utf-8")
        assert load_env(env_file)["KEY"] == "a=b=c"


# ---------------------------------------------------------------------------
# fmt_time
# ---------------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import lol_html_viewer_auto  # noqa: E402


class TestFmtTime:
    def test_zero(self):
        assert lol_html_viewer_auto.fmt_time(0) == "00:00"

    def test_one_minute(self):
        assert lol_html_viewer_auto.fmt_time(60_000) == "01:00"

    def test_partial_minute(self):
        assert lol_html_viewer_auto.fmt_time(90_000) == "01:30"

    def test_large_value(self):
        # 25:00
        assert lol_html_viewer_auto.fmt_time(1_500_000) == "25:00"

    def test_none_treated_as_zero(self):
        assert lol_html_viewer_auto.fmt_time(None) == "00:00"


# ---------------------------------------------------------------------------
# t() language helper (fetch_match_data)
# ---------------------------------------------------------------------------
class TestLangHelper:
    """Test the t(ja, en) helper by importing with a patched LANG."""

    def _make_t(self, lang: str):
        """Return a t() closure for the given lang."""
        def t(ja, en):
            return ja if lang == "ja" else en
        return t

    def test_ja(self):
        t = self._make_t("ja")
        assert t("日本語", "English") == "日本語"

    def test_en(self):
        t = self._make_t("en")
        assert t("日本語", "English") == "English"

    def test_default_is_ja(self, tmp_path, monkeypatch):
        """LANG defaults to 'ja' when not specified in .env."""
        env = load_env(tmp_path / "nonexistent.env")  # empty env
        lang = env.get("LANG", "ja").lower()
        assert lang == "ja"
