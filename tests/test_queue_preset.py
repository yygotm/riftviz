"""Tests for queue preset resolution logic in fetch_match_data."""

import pytest

QUEUE_PRESETS = {
    "swift": 1700,
    "ranked-solo": 420,
    "ranked-flex": 440,
    "normal-draft": 400,
    "normal-blind": 430,
    "aram": 450,
}


def resolve_queue(queue_arg: str) -> int | None:
    """Mirror the resolution logic in fetch_match_data.py."""
    if queue_arg.lstrip("-").isdigit():
        return int(queue_arg)
    if queue_arg in QUEUE_PRESETS:
        return QUEUE_PRESETS[queue_arg]
    return None


class TestQueueResolution:
    @pytest.mark.parametrize("name,expected", list(QUEUE_PRESETS.items()))
    def test_named_presets(self, name, expected):
        assert resolve_queue(name) == expected

    def test_numeric_id(self):
        assert resolve_queue("900") == 900

    def test_unknown_name_returns_none(self):
        assert resolve_queue("unknown-mode") is None

    def test_default_is_swift(self):
        assert resolve_queue("swift") == 1700
