"""
Tests for AudioAnalyzer: bandpass filter, break shot peak detection, ducking intervals.
"""

import unittest
import numpy as np
from billiards_highlight_editor.audio_analyzer import AudioAnalyzer
from billiards_highlight_editor.config import AudioConfig, TrimmingConfig


class TestAudioAnalyzer(unittest.TestCase):
    def setUp(self):
        self.audio_cfg = AudioConfig()
        self.trim_cfg = TrimmingConfig()
        self.analyzer = AudioAnalyzer(self.audio_cfg, self.trim_cfg)
        self.sr = 44100

    def test_bandpass_filter(self):
        # 5 seconds test signal with 100Hz (hum), 3000Hz (rack crack), 15000Hz (hiss)
        t = np.linspace(0, 2.0, 2 * self.sr, endpoint=False)
        sig_low = np.sin(2 * np.pi * 100 * t)
        sig_mid = np.sin(2 * np.pi * 3500 * t)  # In target band 2kHz - 6kHz
        sig_high = np.sin(2 * np.pi * 15000 * t)
        mixed = (sig_low + sig_mid + sig_high).astype(np.float32)

        filtered = self.analyzer.apply_bandpass_filter(mixed, self.sr, 2000.0, 6000.0)
        
        # Energy in 3500Hz should be preserved while 100Hz and 15000Hz are attenuated
        mid_energy = np.mean(filtered ** 2)
        self.assertGreater(mid_energy, 0.1)

    def test_break_shot_candidate_detection(self):
        # Create audio with an intense sharp crack at 3.0 seconds
        duration = 10.0
        t = np.linspace(0, duration, int(duration * self.sr), endpoint=False)
        audio = 0.05 * np.random.randn(len(t)).astype(np.float32)  # background room noise

        # Insert sharp break shot crack at t = 3.0s (3500Hz resonance burst)
        crack_idx = int(3.0 * self.sr)
        crack_len = int(0.15 * self.sr)
        crack_t = np.linspace(0, 0.15, crack_len)
        crack_wave = 1.0 * np.sin(2 * np.pi * 3500 * crack_t) * np.exp(-crack_t * 25)
        audio[crack_idx:crack_idx + crack_len] += crack_wave

        candidates = self.analyzer.detect_break_shot_candidates(
            audio, self.sr, threshold_db=-3.0, min_distance_sec=5.0
        )

        self.assertGreaterEqual(len(candidates), 1)
        first = candidates[0]
        self.assertAlmostEqual(first["peak_time"], 3.0, delta=0.2)
        # Check window: Peak - pre_peak to Peak + post_peak
        self.assertAlmostEqual(first["start_time"], 3.0 - self.trim_cfg.break_shot_pre_peak_sec, delta=0.2)
        self.assertAlmostEqual(first["end_time"], 3.0 + self.trim_cfg.break_shot_post_peak_sec, delta=0.2)

    def test_ducking_intervals(self):
        impacts = [2.0, 5.0, 10.0]
        intervals = self.analyzer.generate_ducking_intervals(impacts, duck_duration_before=0.5, duck_duration_after=2.0)
        self.assertEqual(len(intervals), 3)
        self.assertEqual(intervals[0], (1.5, 4.0))


if __name__ == "__main__":
    unittest.main()
