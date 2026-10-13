"""
End-to-End Integration Test:
Creates a synthetic billiard test video clip with audio transients,
runs the full BilliardsHighlightAgent pipeline, and verifies output highlight video creation.
"""

import os
import unittest
import tempfile
import cv2
import numpy as np
import subprocess
from scipy.io import wavfile
import imageio_ffmpeg

from billiards_highlight_editor.config import EditorConfig, VideoFormat
from billiards_highlight_editor.models import MatchMetadata
from billiards_highlight_editor.pipeline import BilliardsHighlightAgent


class TestEndToEndPipeline(unittest.TestCase):
    def setUp(self):
        self.ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        self.temp_dir = tempfile.mkdtemp()
        self.sample_video = os.path.join(self.temp_dir, "synthetic_match.mp4")
        self.output_video = os.path.join(self.temp_dir, "output_highlight.mp4")

        # 1. Create a 15-second synthetic video with green felt table and moving ball
        fps = 24
        duration = 14.0
        total_frames = int(fps * duration)
        w, h = 640, 360

        raw_vid = os.path.join(self.temp_dir, "raw_video.mp4")
        writer = cv2.VideoWriter(raw_vid, cv2.VideoWriter_fourcc(*'mp4v'), fps, (w, h))

        for f in range(total_frames):
            frame = np.zeros((h, w, 3), dtype=np.uint8)
            # Draw green pool table in center
            cv2.rectangle(frame, (80, 40), (560, 320), (30, 140, 40), -1)
            # Draw moving white cue ball
            ball_x = int(120 + (f % 50) * 8)
            ball_y = int(180 + np.sin(f * 0.2) * 40)
            cv2.circle(frame, (ball_x, ball_y), 8, (255, 255, 255), -1)
            writer.write(frame)
        writer.release()

        # 2. Create audio track with a Break Shot crack at t = 2.0s
        sr = 44100
        audio_len = int(duration * sr)
        audio = 0.02 * np.random.randn(audio_len).astype(np.float32)

        # Break shot crack at 2.0s (3500Hz burst)
        crack_idx = int(2.0 * sr)
        crack_len = int(0.12 * sr)
        ct = np.linspace(0, 0.12, crack_len)
        crack = 0.9 * np.sin(2 * np.pi * 3500 * ct) * np.exp(-ct * 30)
        audio[crack_idx:crack_idx + crack_len] += crack

        # Normal shot click at 8.0s
        click_idx = int(8.0 * sr)
        click_len = int(0.05 * sr)
        click_t = np.linspace(0, 0.05, click_len)
        click = 0.6 * np.sin(2 * np.pi * 2500 * click_t) * np.exp(-click_t * 50)
        audio[click_idx:click_idx + click_len] += click

        raw_wav = os.path.join(self.temp_dir, "raw_audio.wav")
        wavfile.write(raw_wav, sr, (audio * 32767).astype(np.int16))

        # 3. Mux into self.sample_video
        cmd = [
            self.ffmpeg_exe, "-y",
            "-i", raw_vid,
            "-i", raw_wav,
            "-c:v", "copy",
            "-c:a", "aac",
            self.sample_video
        ]
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)

    def tearDown(self):
        # Cleanup temp directory
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_full_pipeline_execution(self):
        config = EditorConfig()
        config.target_fps = 24
        config.horizontal_resolution = (640, 360)
        config.vertical_resolution = (360, 640)
        agent = BilliardsHighlightAgent(config)

        meta = MatchMetadata(
            player_1_name="Test P1",
            player_2_name="Test P2",
            race_to=7
        )

        score_json = """[
          {"timestamp": "00:02.00", "player_1_score": 0, "player_2_score": 0, "state": "NORMAL"},
          {"timestamp": "00:08.00", "player_1_score": 1, "player_2_score": 0, "state": "NORMAL"}
        ]"""

        # 1. Analyze video
        script = agent.analyze_video(
            video_path=self.sample_video,
            score_metadata_json=score_json,
            match_metadata=meta
        )

        self.assertGreater(len(script.segments), 0)
        # Verify Phase 0 Intro and Phase 1 Hook
        self.assertEqual(script.segments[0].phase.value, "match_intro")
        self.assertEqual(script.segments[1].phase.value, "hook_intro")

        # 2. Export Highlight Video
        out_path = agent.export_highlight(
            video_path=self.sample_video,
            script=script,
            output_path=self.output_video
        )

        self.assertTrue(os.path.exists(out_path))
        self.assertGreater(os.path.getsize(out_path), 1000)

        # Probe output video with OpenCV
        cap = cv2.VideoCapture(out_path)
        self.assertTrue(cap.isOpened())
        frame_cnt = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.assertGreater(frame_cnt, 10)
        cap.release()


if __name__ == "__main__":
    unittest.main()
