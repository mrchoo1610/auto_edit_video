"""
Unit tests for RackWinnerDetector: 6 pockets detection, rack segmentation, 9-ball pot detection, and score progression.
"""

import unittest
from billiards_highlight_editor.rack_winner_detector import RackWinnerDetector
from billiards_highlight_editor.models import ShotEvent, MatchMetadata, MatchState, BeatType
from billiards_highlight_editor.config import ShotType


class TestRackWinnerDetector(unittest.TestCase):
    def setUp(self):
        self.detector = RackWinnerDetector()

    def test_compute_table_pockets(self):
        table_roi = (100, 100, 800, 400)
        pockets = self.detector.compute_table_pockets(table_roi)
        self.assertEqual(len(pockets), 6)
        self.assertIn("top_left", pockets)
        self.assertIn("top_right", pockets)
        self.assertIn("center_top", pockets)
        self.assertIn("center_bottom", pockets)

    def test_auto_detect_9ball_pots_and_scores(self):
        meta = MatchMetadata(player_1_name="Shane", player_2_name="Sanchez", race_to=3)

        # Create shots for 2 racks:
        # Rack 1: Break shot -> Standard pot -> 9-ball pot
        # Rack 2: Break shot -> Standard pot -> 9-ball pot
        shots = [
            ShotEvent(1, ShotType.BREAK_SHOT, 0.0, 1.5, 4.0),
            ShotEvent(2, ShotType.STANDARD_POT, 8.0, 9.2, 11.5),
            ShotEvent(3, ShotType.STANDARD_POT, 15.0, 16.5, 19.0),  # Rack 1 9-ball pot
            ShotEvent(4, ShotType.BREAK_SHOT, 40.0, 41.5, 44.0),  # Rack 2 Break
            ShotEvent(5, ShotType.STANDARD_POT, 48.0, 49.2, 51.5),
            ShotEvent(6, ShotType.STANDARD_POT, 55.0, 56.5, 59.0),  # Rack 2 9-ball pot
        ]

        scores = self.detector.auto_detect_9ball_pots_and_scores(
            shots=shots,
            break_candidates=[{"peak_time": 1.5}, {"peak_time": 41.5}],
            metadata=meta
        )

        # Initial score + Rack 1 score + Rack 2 score
        self.assertGreaterEqual(len(scores), 3)

        # Check that rack 1 ends with a winning shot description
        self.assertIn("Winning", shots[2].description)
        # Check that rack 2 (final rack) ends with winning shot description
        self.assertIn("Match Winning 9-Ball Pot", shots[5].description)

        # Verify scores increment
        self.assertEqual(scores[1].player_1_score, 1)
        self.assertEqual(scores[1].player_2_score, 0)

        self.assertEqual(scores[2].player_1_score, 1)
        self.assertEqual(scores[2].player_2_score, 1)


if __name__ == "__main__":
    unittest.main()
