import unittest
import numpy as np
from billiards_highlight_editor.condensed_engine import BilliardsCondensedEngine, CondensedShot, CondensedMatchPlan
from billiards_highlight_editor.models import MatchMetadata


class TestCondensedEngine(unittest.TestCase):
    def setUp(self):
        self.engine = BilliardsCondensedEngine()
        self.metadata = MatchMetadata(
            player_1_name="Chung Choo",
            player_2_name="Khương Liều",
            race_to=7
        )

    def test_strike_trigger_detection(self):
        # Generate synthetic audio click at 5.0 seconds
        sr = 22050
        duration = 10.0
        audio = np.zeros(int(sr * duration), dtype=np.float32)
        click_idx = int(5.0 * sr)
        audio[click_idx:click_idx + 100] = 0.95

        strikes = self.engine.detect_strike_triggers(audio, sr, pre_roll_sec=2.0)
        self.assertTrue(len(strikes) >= 1)
        # Check strike detected close to 5.0s
        first_strike = strikes[0]
        self.assertAlmostEqual(first_strike, 5.0, delta=0.2)

    def test_youtube_chapters_generation(self):
        shots = [
            CondensedShot(
                shot_id=1,
                rack_number=1,
                strike_time=10.0,
                start_time=8.0,
                end_time=14.0,
                is_break=True,
                score_before=(0, 0),
                score_after=(0, 0),
                description="Break Shot"
            ),
            CondensedShot(
                shot_id=2,
                rack_number=1,
                strike_time=25.0,
                start_time=23.0,
                end_time=28.0,
                is_nine_ball_pot=True,
                win_t_offset=3.5,
                score_before=(0, 0),
                score_after=(1, 0),
                description="9-ball Pot"
            ),
            CondensedShot(
                shot_id=3,
                rack_number=2,
                strike_time=45.0,
                start_time=43.0,
                end_time=51.0,
                is_break=True,
                score_before=(1, 0),
                score_after=(1, 0),
                description="Rack 2 Break"
            )
        ]

        chapters = self.engine._generate_youtube_chapters(shots, self.metadata)
        self.assertTrue(len(chapters) >= 3)
        self.assertEqual(chapters[0]["timestamp_str"], "00:00")
        self.assertIn("Khai mạc", chapters[0]["title"])
        self.assertIn("Ván 1", chapters[1]["title"])


if __name__ == "__main__":
    unittest.main()
