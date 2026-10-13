"""
Tests for ScoreboardEngine: JSON parsing, frosted glass overlay rendering, Hill-Hill & Final state.
"""

import unittest
from billiards_highlight_editor.scoreboard_engine import ScoreboardEngine
from billiards_highlight_editor.models import MatchState


class TestScoreboardEngine(unittest.TestCase):
    def setUp(self):
        self.engine = ScoreboardEngine()

    def test_parse_score_metadata_json(self):
        json_str = """[
          {"timestamp": "02:45.00", "player_1_score": 5, "player_2_score": 4, "state": "GAME_POINT"},
          {"timestamp": "03:10.00", "player_1_score": 6, "player_2_score": 6, "state": "HILL-HILL"},
          {"timestamp": "04:00.00", "player_1_score": 7, "player_2_score": 6, "state": "FINAL"}
        ]"""
        states = self.engine.parse_score_metadata_json(json_str)
        self.assertEqual(len(states), 3)

        self.assertAlmostEqual(states[0].timestamp_sec, 165.0)
        self.assertEqual(states[0].player_1_score, 5)
        self.assertEqual(states[0].player_2_score, 4)
        self.assertEqual(states[0].state, MatchState.GAME_POINT)

        self.assertEqual(states[1].state, MatchState.HILL_HILL)
        self.assertEqual(states[2].state, MatchState.FINAL)

    def test_render_scoreboard_overlay(self):
        img = self.engine.render_scoreboard_overlay(
            frame_width=1920,
            frame_height=1080,
            player_1_name="Shane Van Boening",
            player_2_name="Aloysius Yapp",
            score_1=6,
            score_2=6,
            state=MatchState.HILL_HILL,
            race_to=7
        )
        self.assertEqual(img.size, (1920, 1080))
        self.assertEqual(img.mode, "RGBA")


if __name__ == "__main__":
    unittest.main()
