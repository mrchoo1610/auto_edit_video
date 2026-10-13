"""
Tests for ShotDetector: 3-Beat Shot Sequence, Dead Time filtering, masterpiece slow-mo.
"""

import unittest
from billiards_highlight_editor.shot_detector import ShotDetector
from billiards_highlight_editor.config import EditorConfig, ShotType
from billiards_highlight_editor.models import BeatType, ScoreboardState, MatchState


class TestShotDetector(unittest.TestCase):
    def setUp(self):
        self.config = EditorConfig()
        self.detector = ShotDetector(self.config)

    def test_3beat_shot_event_structure(self):
        impact_t = 10.0
        ball_stop_t = 12.5

        shot = self.detector.build_3beat_shot_event(
            shot_id=1,
            impact_timestamp=impact_t,
            ball_stop_timestamp=ball_stop_t,
            shot_type=ShotType.STANDARD_POT,
            is_masterpiece=False
        )

        # Check 3 beats exist
        self.assertEqual(len(shot.beats), 3)
        b1, b2, b3 = shot.beats

        # Beat 1: Tension
        self.assertEqual(b1.beat_type, BeatType.BEAT_1_TENSION)
        self.assertAlmostEqual(b1.end_time, impact_t, delta=0.01)
        self.assertTrue(self.config.trimming.beat_1_tension_min_sec <= (b1.end_time - b1.start_time) <= self.config.trimming.beat_1_tension_max_sec)
        self.assertEqual(b1.playback_speed, 1.0)

        # Beat 2: Impact (real time 100%)
        self.assertEqual(b2.beat_type, BeatType.BEAT_2_IMPACT)
        self.assertEqual(b2.playback_speed, 1.0)

        # Beat 3: Resolution
        self.assertEqual(b3.beat_type, BeatType.BEAT_3_RESOLUTION)
        self.assertEqual(b3.playback_speed, 1.0)
        self.assertTrue(self.config.trimming.beat_3_resolution_min_sec <= (b3.end_time - b3.start_time) <= self.config.trimming.beat_3_resolution_max_sec)

    def test_masterpiece_slowmotion_beat(self):
        # Jump shot or bank shot applies 50% slow-mo
        shot = self.detector.build_3beat_shot_event(
            shot_id=2,
            impact_timestamp=20.0,
            ball_stop_timestamp=22.5,
            shot_type=ShotType.JUMP_SHOT,
            is_masterpiece=True
        )

        b3 = shot.beats[2]
        self.assertEqual(b3.playback_speed, 0.50)  # 50% slow-motion as per Spec 2.2


if __name__ == "__main__":
    unittest.main()
