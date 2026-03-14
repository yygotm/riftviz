"""Unit tests for MatchContext and module-level helpers."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import lol_html_viewer_auto as viewer
from lol_html_viewer_auto import MatchContext, fmt_time, html_escape, table_html
from tests.fixtures import MINIMAL_MATCH, MINIMAL_TIMELINE


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

CHAMP_MAP = {"1": "Annie", "99": "Lux", "222": "Jinx"}
USER_PUUID = "puuid_0"  # participant 1, team 100


def make_ctx(match=None, champ_map=None, puuid=USER_PUUID) -> MatchContext:
    return MatchContext(
        match or MINIMAL_MATCH,
        champ_map if champ_map is not None else CHAMP_MAP,
        puuid,
    )


# ---------------------------------------------------------------------------
# MatchContext.__init__ — team assignment
# ---------------------------------------------------------------------------


class TestMatchContextInit:
    def test_user_pid_resolved(self):
        ctx = make_ctx()
        assert ctx.user_pid == 1  # puuid_0 is participantId 1

    def test_user_team_100(self):
        ctx = make_ctx()
        assert ctx.user_team_id == 100
        assert ctx.friend_team_id == 100
        assert ctx.enemy_team_id == 200

    def test_user_team_200(self):
        # puuid_5 is participantId 6, team 200
        ctx = make_ctx(puuid="puuid_5")
        assert ctx.user_team_id == 200
        assert ctx.friend_team_id == 200
        assert ctx.enemy_team_id == 100

    def test_unknown_puuid_defaults_to_team100(self):
        ctx = make_ctx(puuid="no_such_puuid")
        assert ctx.user_pid is None
        assert ctx.user_team_id == 100

    def test_invalid_team_id_falls_back_to_100(self):
        """A participant with teamId 999 should fall back to 100."""
        import copy

        bad_match = copy.deepcopy(MINIMAL_MATCH)
        bad_match["info"]["participants"][0]["teamId"] = 999
        ctx = make_ctx(match=bad_match, puuid="puuid_0")
        assert ctx.user_team_id == 100


# ---------------------------------------------------------------------------
# champ_name
# ---------------------------------------------------------------------------


class TestChampName:
    def test_known_id(self):
        ctx = make_ctx()
        assert ctx.champ_name(1) == "Annie"
        assert ctx.champ_name(99) == "Lux"

    def test_unknown_id_returns_id_label(self):
        ctx = make_ctx()
        assert ctx.champ_name(9999) == "ID:9999"

    def test_empty_champ_map(self):
        ctx = make_ctx(champ_map={})
        assert ctx.champ_name(1) == "ID:1"


# ---------------------------------------------------------------------------
# get_p
# ---------------------------------------------------------------------------


class TestGetP:
    def test_valid_pid(self):
        ctx = make_ctx()
        p = ctx.get_p(1)
        assert p is not None
        assert p["participantId"] == 1

    def test_zero_returns_none(self):
        ctx = make_ctx()
        assert ctx.get_p(0) is None

    def test_none_returns_none(self):
        ctx = make_ctx()
        assert ctx.get_p(None) is None

    def test_nonexistent_pid_returns_none(self):
        ctx = make_ctx()
        assert ctx.get_p(999) is None


# ---------------------------------------------------------------------------
# champ_from_pid
# ---------------------------------------------------------------------------


class TestChampFromPid:
    def test_ja_uses_champ_map(self):
        ctx = make_ctx()
        # participantId 1 has championId 1 → "Annie"
        assert ctx.champ_from_pid(1, "ja") == "Annie"

    def test_en_uses_championName(self):
        ctx = make_ctx()
        assert ctx.champ_from_pid(1, "en") == "Annie"

    def test_invalid_pid_ja(self):
        ctx = make_ctx()
        assert ctx.champ_from_pid(999, "ja") == "不明"

    def test_invalid_pid_en(self):
        ctx = make_ctx()
        assert ctx.champ_from_pid(999, "en") == "Unknown"


# ---------------------------------------------------------------------------
# display_name
# ---------------------------------------------------------------------------


class TestDisplayName:
    def test_riot_id_format(self):
        p = {"riotIdGameName": "Alpha", "riotIdTagline": "NA1", "summonerName": "Alpha"}
        assert MatchContext.display_name(p) == "Alpha#NA1"

    def test_fallback_to_summoner_name(self):
        p = {"riotIdGameName": "", "riotIdTagline": "", "summonerName": "Beta"}
        assert MatchContext.display_name(p) == "Beta"

    def test_fallback_to_pid(self):
        p = {"riotIdGameName": "", "riotIdTagline": "", "summonerName": "", "participantId": 7}
        assert MatchContext.display_name(p) == "PID:7"


# ---------------------------------------------------------------------------
# team_label
# ---------------------------------------------------------------------------


class TestTeamLabel:
    def test_friend_team_ja(self):
        ctx = make_ctx()  # user on team 100
        assert ctx.team_label(100, "ja") == "味方"

    def test_friend_team_en(self):
        ctx = make_ctx()
        assert ctx.team_label(100, "en") == "Ally"

    def test_enemy_team_ja(self):
        ctx = make_ctx()
        assert ctx.team_label(200, "ja") == "敵"

    def test_enemy_team_en(self):
        ctx = make_ctx()
        assert ctx.team_label(200, "en") == "Enemy"

    def test_unknown_team_returns_empty(self):
        ctx = make_ctx()
        assert ctx.team_label(999, "ja") == ""


# ---------------------------------------------------------------------------
# event_text — CHAMPION_KILL
# ---------------------------------------------------------------------------


class TestEventTextChampionKill:
    BASE_EV = {"type": "CHAMPION_KILL", "killerId": 1, "victimId": 6}

    def test_ja(self):
        ctx = make_ctx()
        text = ctx.event_text(self.BASE_EV, "ja")
        assert "⚔️" in text
        assert "キル" in text
        assert "Annie" in text

    def test_en(self):
        ctx = make_ctx()
        text = ctx.event_text(self.BASE_EV, "en")
        assert "killed" in text
        assert "Annie" in text

    def test_unknown_killer_ja(self):
        ctx = make_ctx()
        ev = {"type": "CHAMPION_KILL", "killerId": 999, "victimId": 6}
        text = ctx.event_text(ev, "ja")
        assert "不明" in text

    def test_unknown_killer_en(self):
        ctx = make_ctx()
        ev = {"type": "CHAMPION_KILL", "killerId": 999, "victimId": 6}
        text = ctx.event_text(ev, "en")
        assert "Unknown" in text


# ---------------------------------------------------------------------------
# event_text — ELITE_MONSTER_KILL
# ---------------------------------------------------------------------------


class TestEventTextEliteMonster:
    def test_dragon_ja(self):
        ctx = make_ctx()
        ev = {"type": "ELITE_MONSTER_KILL", "killerId": 1,
              "monsterType": "DRAGON", "monsterSubType": "FIRE_DRAGON"}
        text = ctx.event_text(ev, "ja")
        assert "🐉" in text
        assert "ドラゴン" in text
        assert "FIRE_DRAGON" in text

    def test_baron_en(self):
        ctx = make_ctx()
        ev = {"type": "ELITE_MONSTER_KILL", "killerId": 1,
              "monsterType": "BARON_NASHOR", "monsterSubType": ""}
        text = ctx.event_text(ev, "en")
        assert "👑" in text
        assert "Baron Nashor" in text
        assert "slew" in text

    def test_rift_herald_ja(self):
        ctx = make_ctx()
        ev = {"type": "ELITE_MONSTER_KILL", "killerId": 1,
              "monsterType": "RIFTHERALD", "monsterSubType": ""}
        text = ctx.event_text(ev, "ja")
        assert "リフトヘラルド" in text

    def test_unknown_monster_fallback_ja(self):
        ctx = make_ctx()
        ev = {"type": "ELITE_MONSTER_KILL", "killerId": 1,
              "monsterType": "HORDE", "monsterSubType": ""}
        text = ctx.event_text(ev, "ja")
        assert "HORDE" in text

    def test_unknown_monster_fallback_en(self):
        ctx = make_ctx()
        ev = {"type": "ELITE_MONSTER_KILL", "killerId": 1,
              "monsterType": "HORDE", "monsterSubType": ""}
        text = ctx.event_text(ev, "en")
        assert "HORDE" in text


# ---------------------------------------------------------------------------
# event_text — BUILDING_KILL
# ---------------------------------------------------------------------------


class TestEventTextBuildingKill:
    def test_tower_mid_ja(self):
        ctx = make_ctx()
        ev = {"type": "BUILDING_KILL", "killerId": 1,
              "buildingType": "TOWER_BUILDING", "laneType": "MID_LANE"}
        text = ctx.event_text(ev, "ja")
        assert "🏰" in text
        assert "タワー" in text
        assert "ミッド" in text

    def test_inhibitor_top_en(self):
        ctx = make_ctx()
        ev = {"type": "BUILDING_KILL", "killerId": 1,
              "buildingType": "INHIBITOR_BUILDING", "laneType": "TOP_LANE"}
        text = ctx.event_text(ev, "en")
        assert "💎" in text
        assert "Inhibitor" in text
        assert "Top" in text

    def test_unknown_building_fallback(self):
        ctx = make_ctx()
        ev = {"type": "BUILDING_KILL", "killerId": 1,
              "buildingType": "NEXUS_BUILDING", "laneType": ""}
        text_ja = ctx.event_text(ev, "ja")
        text_en = ctx.event_text(ev, "en")
        assert "NEXUS_BUILDING" in text_ja
        assert "NEXUS_BUILDING" in text_en

    def test_no_lane_suffix(self):
        ctx = make_ctx()
        ev = {"type": "BUILDING_KILL", "killerId": 1,
              "buildingType": "TOWER_BUILDING", "laneType": ""}
        text = ctx.event_text(ev, "ja")
        assert "（" not in text  # no parentheses when lane is empty


# ---------------------------------------------------------------------------
# event_text — unknown type
# ---------------------------------------------------------------------------


class TestEventTextUnknown:
    def test_unknown_type_returns_empty(self):
        ctx = make_ctx()
        ev = {"type": "WARD_PLACED"}
        assert ctx.event_text(ev, "ja") == ""
        assert ctx.event_text(ev, "en") == ""


# ---------------------------------------------------------------------------
# build_player_row
# ---------------------------------------------------------------------------


class TestBuildPlayerRow:
    def test_basic_stats(self):
        ctx = make_ctx()
        p = ctx.participants[0]  # participantId 1, kills=0
        row = ctx.build_player_row(p)
        assert row["pid"] == 1
        assert row["k"] == 0
        assert row["d"] == 2
        assert row["a"] == 3
        assert row["cs"] == 110  # 100 + 10
        assert row["gold"] == 10000
        assert row["teamId"] == 100

    def test_kda_formula(self):
        ctx = make_ctx()
        p = ctx.participants[0]
        row = ctx.build_player_row(p)
        # (kills + assists) / max(1, deaths) = (0+3)/2 = 1.5
        assert row["kda"] == pytest.approx(1.5)

    def test_zero_deaths_kda(self):
        """Deaths=0 must not cause ZeroDivisionError; denominator=1."""
        import copy

        ctx = make_ctx()
        p = copy.deepcopy(ctx.participants[0])
        p["kills"] = 5
        p["deaths"] = 0
        p["assists"] = 0
        row = ctx.build_player_row(p)
        assert row["kda"] == pytest.approx(5.0)

    def test_is_user_flag(self):
        ctx = make_ctx()
        rows = [ctx.build_player_row(p) for p in ctx.participants]
        user_rows = [r for r in rows if r["is_user"]]
        assert len(user_rows) == 1
        assert user_rows[0]["pid"] == 1

    def test_champ_name_resolved(self):
        ctx = make_ctx()
        p = ctx.participants[0]
        row = ctx.build_player_row(p)
        assert row["champ"] == "Annie"


# ---------------------------------------------------------------------------
# build_all_rows
# ---------------------------------------------------------------------------


class TestBuildAllRows:
    def test_returns_four_lists(self):
        ctx = make_ctx()
        team100, team200, friend_rows, enemy_rows = ctx.build_all_rows()
        assert len(team100) == 5
        assert len(team200) == 5
        assert len(friend_rows) == 5
        assert len(enemy_rows) == 5

    def test_friend_is_team100_when_user_on_100(self):
        ctx = make_ctx(puuid="puuid_0")  # team 100
        _, _, friend_rows, enemy_rows = ctx.build_all_rows()
        assert all(r["teamId"] == 100 for r in friend_rows)
        assert all(r["teamId"] == 200 for r in enemy_rows)

    def test_friend_is_team200_when_user_on_200(self):
        ctx = make_ctx(puuid="puuid_5")  # team 200
        _, _, friend_rows, enemy_rows = ctx.build_all_rows()
        assert all(r["teamId"] == 200 for r in friend_rows)
        assert all(r["teamId"] == 100 for r in enemy_rows)


# ---------------------------------------------------------------------------
# build_events
# ---------------------------------------------------------------------------


class TestBuildEvents:
    def test_returns_events_sorted_by_time(self):
        ctx = make_ctx()
        events = ctx.build_events(MINIMAL_TIMELINE, "ja")
        assert len(events) >= 1
        timestamps = [e["t"] for e in events]
        assert timestamps == sorted(timestamps)

    def test_event_has_required_keys(self):
        ctx = make_ctx()
        events = ctx.build_events(MINIMAL_TIMELINE, "ja")
        ev = events[0]
        for key in ("t", "time", "type", "teamId", "team", "team_en", "text", "text_en", "is_user", "raw"):
            assert key in ev, f"Missing key: {key}"

    def test_champion_kill_text_ja(self):
        ctx = make_ctx()
        events = ctx.build_events(MINIMAL_TIMELINE, "ja")
        kill_ev = next(e for e in events if e["type"] == "CHAMPION_KILL")
        assert "キル" in kill_ev["text"]

    def test_champion_kill_text_en(self):
        ctx = make_ctx()
        events = ctx.build_events(MINIMAL_TIMELINE, "en")
        kill_ev = next(e for e in events if e["type"] == "CHAMPION_KILL")
        assert "killed" in kill_ev["text_en"]

    def test_user_involved_flag(self):
        ctx = make_ctx()  # user pid=1, killer in MINIMAL_TIMELINE
        events = ctx.build_events(MINIMAL_TIMELINE, "ja")
        kill_ev = next(e for e in events if e["type"] == "CHAMPION_KILL")
        assert kill_ev["is_user"] is True

    def test_disallowed_event_types_filtered_out(self):
        import copy

        tl = copy.deepcopy(MINIMAL_TIMELINE)
        tl["info"]["frames"][0]["events"].append(
            {"timestamp": 130000, "type": "WARD_PLACED", "creatorId": 1}
        )
        ctx = make_ctx()
        events = ctx.build_events(tl, "ja")
        types = {e["type"] for e in events}
        assert "WARD_PLACED" not in types

    def test_team_assignment_friend(self):
        ctx = make_ctx()  # user on team 100; killer pid=1 is team 100
        events = ctx.build_events(MINIMAL_TIMELINE, "ja")
        kill_ev = next(e for e in events if e["type"] == "CHAMPION_KILL")
        assert kill_ev["teamId"] == 100
        assert kill_ev["team"] == "味方"

    def test_time_formatted(self):
        ctx = make_ctx()
        events = ctx.build_events(MINIMAL_TIMELINE, "ja")
        # MINIMAL_TIMELINE timestamp is 120000 ms → 02:00
        kill_ev = events[0]
        assert kill_ev["time"] == "02:00"


# ---------------------------------------------------------------------------
# _event_team_id
# ---------------------------------------------------------------------------


class TestEventTeamId:
    def test_via_killer_id(self):
        ctx = make_ctx()
        ev = {"type": "CHAMPION_KILL", "killerId": 1}  # pid 1 is team 100
        assert ctx._event_team_id(ev) == 100

    def test_via_victim_id(self):
        ctx = make_ctx()
        ev = {"type": "CHAMPION_KILL", "victimId": 6}  # pid 6 is team 200
        assert ctx._event_team_id(ev) == 200

    def test_no_valid_pid_returns_none(self):
        ctx = make_ctx()
        ev = {"type": "CHAMPION_KILL"}
        assert ctx._event_team_id(ev) is None


# ---------------------------------------------------------------------------
# build_gold_frames
# ---------------------------------------------------------------------------


class TestBuildGoldFrames:
    def test_returns_list_of_frames(self):
        ctx = make_ctx()
        frames = ctx.build_gold_frames(MINIMAL_TIMELINE)
        assert len(frames) == 1  # MINIMAL_TIMELINE has one frame
        assert "t" in frames[0]
        assert "diff" in frames[0]

    def test_diff_is_numeric(self):
        ctx = make_ctx()
        frames = ctx.build_gold_frames(MINIMAL_TIMELINE)
        assert isinstance(frames[0]["diff"], int | float)

    def test_friend_team100_gets_positive_gold_when_ahead(self):
        """Team 100 (friend) has pids 1-5, team 200 has pids 6-10.
        MINIMAL_TIMELINE gives totalGold = 500*(pid), so team100 > team200 only
        if sum(500*1..5) > sum(500*6..10). Actually team200 has more gold here,
        so diff should be negative for team100 as friend."""
        ctx = make_ctx(puuid="puuid_0")  # friend = team 100
        frames = ctx.build_gold_frames(MINIMAL_TIMELINE)
        # team100 gold = 500*(1+2+3+4+5) = 7500
        # team200 gold = 500*(6+7+8+9+10) = 20000
        assert frames[0]["diff"] == 7500 - 20000

    def test_friend_team200_diff_reversed(self):
        ctx = make_ctx(puuid="puuid_5")  # friend = team 200
        frames = ctx.build_gold_frames(MINIMAL_TIMELINE)
        assert frames[0]["diff"] == 20000 - 7500


# ---------------------------------------------------------------------------
# html_escape
# ---------------------------------------------------------------------------


class TestHtmlEscape:
    def test_escapes_lt_gt(self):
        assert html_escape("<script>") == "&lt;script&gt;"

    def test_escapes_ampersand(self):
        assert html_escape("a&b") == "a&amp;b"

    def test_escapes_quotes(self):
        assert html_escape('"hello"') == "&quot;hello&quot;"

    def test_non_string_coerced(self):
        assert html_escape(42) == "42"


# ---------------------------------------------------------------------------
# table_html
# ---------------------------------------------------------------------------


class TestTableHtml:
    def _sample_rows(self):
        ctx = make_ctx()
        _, _, friend_rows, _ = ctx.build_all_rows()
        return friend_rows

    def test_returns_string(self):
        rows = self._sample_rows()
        result = table_html(rows, "ally_team", 100)
        assert isinstance(result, str)

    def test_contains_table_tag(self):
        rows = self._sample_rows()
        result = table_html(rows, "ally_team", 100)
        assert "<table>" in result

    def test_data_i18n_ally_team(self):
        rows = self._sample_rows()
        result = table_html(rows, "ally_team", 100)
        assert 'data-i18n="ally_team"' in result

    def test_data_i18n_enemy_team(self):
        rows = self._sample_rows()
        result = table_html(rows, "enemy_team", 200)
        assert 'data-i18n="enemy_team"' in result

    def test_user_row_has_class(self):
        rows = self._sample_rows()
        result = table_html(rows, "ally_team", 100)
        assert "<tr class='user'>" in result

    def test_player_names_present(self):
        rows = self._sample_rows()
        result = table_html(rows, "ally_team", 100)
        assert "Player0" in result
