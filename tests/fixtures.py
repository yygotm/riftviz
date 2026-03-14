"""Minimal match / timeline fixtures for unit tests."""

# 10-player minimal match JSON (5v5, JP1)
MINIMAL_MATCH = {
    "metadata": {"matchId": "JP1_000000001"},
    "info": {
        "gameMode": "SWIFTPLAY",
        "gameDuration": 1200,
        "gameVersion": "14.1.0.0",
        "teams": [
            {"teamId": 100, "win": True},
            {"teamId": 200, "win": False},
        ],
        "participants": [
            {
                "participantId": i + 1,
                "puuid": f"puuid_{i}",
                "riotIdGameName": f"Player{i}",
                "riotIdTagline": "JP1",
                "summonerName": f"Player{i}",
                "teamId": 100 if i < 5 else 200,
                "championId": 1,
                "championName": "Annie",
                "individualPosition": ["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"][i % 5],
                "kills": i,
                "deaths": 2,
                "assists": 3,
                "totalMinionsKilled": 100,
                "neutralMinionsKilled": 10,
                "goldEarned": 10000,
                "totalDamageDealtToChampions": 20000,
                "totalDamageTaken": 15000,
                "visionScore": 20,
                "timeCCingOthers": 5,
                "totalTimeSpentDead": 60,
            }
            for i in range(10)
        ],
    },
}

# Minimal timeline JSON with one CHAMPION_KILL event
MINIMAL_TIMELINE = {
    "info": {
        "frames": [
            {
                "timestamp": 120000,
                "participantFrames": {
                    str(i + 1): {
                        "participantId": i + 1,
                        "totalGold": 500 * (i + 1),
                    }
                    for i in range(10)
                },
                "events": [
                    {
                        "timestamp": 120000,
                        "type": "CHAMPION_KILL",
                        "killerId": 1,
                        "victimId": 6,
                        "assistingParticipantIds": [2, 3],
                    }
                ],
            }
        ]
    }
}
