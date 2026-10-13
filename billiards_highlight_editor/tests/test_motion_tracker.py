"""
Tests for MotionTracker: felt detection, motion energy, and ball rest stop timing.
"""

import unittest
import numpy as np
import cv2
from billiards_highlight_editor.motion_tracker import MotionTracker


class TestMotionTracker(unittest.TestCase):
    def setUp(self):
        self.tracker = MotionTracker()

    def test_detect_table_felt_roi(self):
        # Create an artificial frame with a green pool table in the middle
        h, w = 720, 1280
        frame = np.zeros((h, w, 3), dtype=np.uint8)
        # Green felt in BGR: B: 30, G: 140, R: 40
        table_x, table_y, table_w, table_h = 200, 100, 880, 520
        frame[table_y:table_y+table_h, table_x:table_x+table_w] = (30, 140, 40)

        roi = self.tracker.detect_table_felt_roi(frame)
        self.assertIsNotNone(roi)
        rx, ry, rw, rh = roi
        self.assertAlmostEqual(rx, table_x, delta=30)
        self.assertAlmostEqual(ry, table_y, delta=30)
        self.assertAlmostEqual(rw, table_w, delta=40)
        self.assertAlmostEqual(rh, table_h, delta=40)

    def test_ball_motion_energy_and_rest_detection(self):
        # Simulate moving ball
        gray1 = np.zeros((300, 300), dtype=np.uint8)
        gray2 = np.zeros((300, 300), dtype=np.uint8)
        # Ball moves from (50, 50) to (100, 100)
        cv2.circle(gray1, (50, 50), 10, 255, -1)
        cv2.circle(gray2, (100, 100), 10, 255, -1)

        energy = self.tracker.compute_ball_motion_energy(gray1, gray2)
        self.assertGreater(energy, 0.05)

        # Still frames: energy is 0
        energy_still = self.tracker.compute_ball_motion_energy(gray2, gray2)
        self.assertEqual(energy_still, 0.0)

        # Test find_ball_stop_timestamp:
        # Ball moving from t=1.0 to t=3.5, then resting (vel=0)
        motion_curve = [
            (1.0, 5.0),
            (1.5, 4.0),
            (2.0, 3.0),
            (2.5, 1.5),
            (3.0, 0.5),
            (3.5, 0.0),
            (3.6, 0.0),
            (3.7, 0.0),
            (3.8, 0.0),
            (3.9, 0.0),
            (4.0, 0.0),
            (4.5, 0.0)
        ]
        stop_t = self.tracker.find_ball_stop_timestamp(motion_curve, impact_timestamp=1.0, buffer_sec=0.5)
        # Rest detected around 4.0s + 0.5s buffer = ~4.5s
        self.assertAlmostEqual(stop_t, 4.5, delta=0.3)


if __name__ == "__main__":
    unittest.main()
