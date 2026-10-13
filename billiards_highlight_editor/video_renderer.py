"""
Video Renderer Module:
Assembles video segments, renders visual overlays (Camera Shake, Kinetic Typography, Frosted Scoreboard, Outro),
and exports the final high-definition video via FFmpeg.
Supports both Horizontal 16:9 (YouTube) and Vertical 9:16 (Shorts/TikTok/Reels).
"""

import os
import subprocess
import tempfile
import cv2
import numpy as np
from PIL import Image
from typing import List, Optional, Tuple, Dict, Any, Callable
import imageio_ffmpeg

from billiards_highlight_editor.config import EditorConfig, VideoFormat
from billiards_highlight_editor.models import (
    HighlightScript, TimelineSegment, TimelinePhase, MatchState, ScoreboardState
)
from billiards_highlight_editor.scoreboard_engine import ScoreboardEngine
from billiards_highlight_editor.video_effects import VideoEffects
from billiards_highlight_editor.hardware_profiler import HardwareProfiler


class VideoRenderer:
    def __init__(self, config: Optional[EditorConfig] = None):
        self.config = config or EditorConfig()
        self.ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        self.scoreboard_engine = ScoreboardEngine(self.config.scoreboard)
        self.effects = VideoEffects()
        self.profiler = HardwareProfiler(self.ffmpeg_exe)

    def _format_frame_dimensions(self) -> Tuple[int, int]:
        if self.config.video_format == VideoFormat.VERTICAL_SHORTS:
            return self.config.vertical_resolution
        return self.config.horizontal_resolution

    def _convert_frame_aspect(
        self,
        frame: np.ndarray,
        target_w: int,
        target_h: int
    ) -> np.ndarray:
        """
        Adapts source frame to target resolution.
        If Vertical (9:16), creates aesthetic blurred background with crisp centered action.
        """
        h, w = frame.shape[:2]
        if w == target_w and h == target_h:
            return frame

        if self.config.video_format == VideoFormat.VERTICAL_SHORTS:
            # Create 9:16 vertical canvas:
            # 1. Background: blurred fill
            bg_scale = max(target_w / float(w), target_h / float(h))
            bg_w, bg_h = int(w * bg_scale), int(h * bg_scale)
            bg = cv2.resize(frame, (bg_w, bg_h), interpolation=cv2.INTER_LINEAR)
            
            # Crop background to exact vertical target
            bx = (bg_w - target_w) // 2
            by = (bg_h - target_h) // 2
            bg_crop = bg[by:by+target_h, bx:bx+target_w]
            bg_blur = cv2.GaussianBlur(bg_crop, (51, 51), 0)
            # Darken background slightly
            bg_blur = (bg_blur * 0.6).astype(np.uint8)

            # 2. Foreground: centered crisp 16:9 view
            fg_scale = target_w / float(w)
            fg_w = target_w
            fg_h = int(h * fg_scale)
            fg_resized = cv2.resize(frame, (fg_w, fg_h), interpolation=cv2.INTER_LINEAR)

            fg_y = (target_h - fg_h) // 2
            bg_blur[fg_y:fg_y+fg_h, 0:fg_w] = fg_resized
            return bg_blur
        else:
            # Standard horizontal 16:9 resize
            return cv2.resize(frame, (target_w, target_h), interpolation=cv2.INTER_LINEAR)

    def render_highlight_video(
        self,
        source_video_path: str,
        script: HighlightScript,
        output_video_path: str,
        mixed_audio_wav_path: Optional[str] = None,
        progress_callback: Optional[Callable[[float, str], None]] = None
    ):
        """
        Executes frame-by-frame rendering and compositing according to the highlight timeline script.
        Pipes frames directly into FFmpeg H.264 encoder.
        """
        if not os.path.exists(source_video_path):
            raise FileNotFoundError(f"Source video not found: {source_video_path}")

        target_w, target_h = self._format_frame_dimensions()
        fps = self.config.target_fps

        cap = cv2.VideoCapture(source_video_path)
        if not cap.isOpened():
            raise RuntimeError(f"Unable to open source video: {source_video_path}")

        src_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0

        os.makedirs(os.path.dirname(os.path.abspath(output_video_path)), exist_ok=True)

        # Temporary video-only file if we need to mux audio
        with_audio = mixed_audio_wav_path and os.path.exists(mixed_audio_wav_path)
        temp_video_only = output_video_path + ".temp.mp4" if with_audio else output_video_path

        # Check machine hardware configuration and select optimal render technology
        hw_profile = self.profiler.profile_and_optimize()
        self.profiler.print_profile_banner(hw_profile)
        enc_args = hw_profile.ffmpeg_encoder_args

        ffmpeg_cmd = [
            self.ffmpeg_exe,
            "-y",
            "-f", "rawvideo",
            "-vcodec", "rawvideo",
            "-s", f"{target_w}x{target_h}",
            "-pix_fmt", "bgr24",
            "-r", str(fps),
            "-i", "-",
            *enc_args,
            "-pix_fmt", "yuv420p",
            temp_video_only
        ]

        pipe = subprocess.Popen(ffmpeg_cmd, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)

        total_segments = len(script.segments)
        current_time_out = 0.0
        active_score_1 = 0
        active_score_2 = 0
        active_state = MatchState.NORMAL
        active_rack_label = "VÁN 1"
        active_video_path = source_video_path

        frame_shake_idx = 0

        try:
            for seg_idx, seg in enumerate(script.segments):
                if progress_callback:
                    pct = float(seg_idx) / max(1, total_segments)
                    progress_callback(pct, f"Rendering Segment {seg_idx+1}/{total_segments} ({seg.phase.value})")

                # Switch source video capture if segment belongs to secondary clip (e.g. 1012(1).mp4)
                seg_source = seg.source_file if (seg.source_file and os.path.exists(seg.source_file)) else source_video_path
                if seg_source != active_video_path:
                    cap.release()
                    active_video_path = seg_source
                    cap = cv2.VideoCapture(active_video_path)

                # Update rack label and score state
                if seg.rack_label:
                    active_rack_label = seg.rack_label

                if seg.scoreboard_state:
                    active_score_1 = seg.scoreboard_state.player_1_score
                    active_score_2 = seg.scoreboard_state.player_2_score
                    active_state = seg.scoreboard_state.state
                    if seg.scoreboard_state.rack_label:
                        active_rack_label = seg.scoreboard_state.rack_label

                # Seek video to segment source start ONCE
                cap.set(cv2.CAP_PROP_POS_MSEC, seg.source_start_sec * 1000.0)

                seg_duration = seg.source_end_sec - seg.source_start_sec
                effective_speed = max(0.2, seg.playback_speed)
                target_frames = int((seg_duration / effective_speed) * fps)

                last_valid_frame = None
                frame = None

                for f_idx in range(target_frames):
                    need_new_frame = True
                    if effective_speed < 0.99:
                        step_ratio = max(1, int(round(1.0 / effective_speed)))
                        need_new_frame = (f_idx % step_ratio == 0)

                    if need_new_frame:
                        ret, read_frame = cap.read()
                        if ret:
                            last_valid_frame = read_frame
                            frame = read_frame
                        else:
                            frame = last_valid_frame if last_valid_frame is not None else np.zeros((target_h, target_w, 3), dtype=np.uint8)
                    else:
                        frame = last_valid_frame if last_valid_frame is not None else np.zeros((target_h, target_w, 3), dtype=np.uint8)

                    # Adapt aspect ratio
                    out_frame = self._convert_frame_aspect(frame, target_w, target_h)

                    # 1. Camera Shake during Break Shot impact (Spec 3 Phase 1)
                    if seg.has_camera_shake:
                        out_frame = self.effects.apply_camera_shake(
                            out_frame,
                            intensity_pct=seg.camera_shake_intensity,
                            seed_frame_idx=frame_shake_idx
                        )
                        frame_shake_idx += 1

                    # Convert to PIL Image for overlay drawing
                    pil_frame = Image.fromarray(cv2.cvtColor(out_frame, cv2.COLOR_BGR2RGB)).convert("RGBA")

                    # 1. Cinematic Match Intro Screen (0:00 - 0:03.5)
                    if seg.phase == TimelinePhase.PHASE_0_INTRO:
                        intro_progress = float(f_idx) / max(1, target_frames)
                        intro_overlay = self.effects.render_cinematic_intro_screen(
                            target_w, target_h, script.metadata, intro_progress
                        )
                        pil_frame = Image.alpha_composite(pil_frame, intro_overlay)

                    # 2. Minimalist Dark Frosted Scoreboard Overlay (appears after Intro)
                    elif seg.phase != TimelinePhase.PHASE_0_INTRO:
                        score_alpha = 1.0
                        sb_overlay = self.scoreboard_engine.render_scoreboard_overlay(
                            target_w, target_h,
                            player_1_name=script.metadata.player_1_name,
                            player_2_name=script.metadata.player_2_name,
                            score_1=active_score_1,
                            score_2=active_score_2,
                            state=active_state,
                            race_to=script.metadata.race_to,
                            alpha_in=score_alpha,
                            rack_label=active_rack_label
                        )
                        pil_frame = Image.alpha_composite(pil_frame, sb_overlay)

                        # 2.1 Rack Chapter Banner Transition (shows during first 2.5s of rack)
                        banner_frames = int(fps * 2.5)
                        if seg.rack_banner_title and f_idx < banner_frames:
                            banner_prog = float(f_idx) / max(1, banner_frames)
                            banner_overlay = self.effects.render_rack_chapter_banner(
                                target_w, target_h,
                                banner_title=seg.rack_banner_title,
                                banner_subtitle=seg.rack_banner_subtitle,
                                progress=banner_prog
                            )
                            pil_frame = Image.alpha_composite(pil_frame, banner_overlay)

                    # 3. Outro CTA screen (during Phase 4 Resolution / Outro)
                    if seg.phase == TimelinePhase.PHASE_4_OUTRO and f_idx > target_frames - int(fps * 3.5):
                        outro_prog = (f_idx - (target_frames - int(fps * 3.5))) / float(fps * 3.5)
                        outro_overlay = self.effects.render_outro_cta(
                            target_w, target_h, script.metadata, outro_prog
                        )
                        pil_frame = Image.alpha_composite(pil_frame, outro_overlay)

                    # Convert back to BGR numpy array and write to FFmpeg stdin
                    final_bgr = cv2.cvtColor(np.array(pil_frame.convert("RGB")), cv2.COLOR_RGB2BGR)
                    pipe.stdin.write(final_bgr.tobytes())

                    current_time_out += 1.0 / fps

            pipe.stdin.close()
            pipe.wait()

        finally:
            cap.release()

        # If we have mixed audio, mux video and audio together
        if with_audio:
            if progress_callback:
                progress_callback(0.98, "Muxing master audio and final video...")

            mux_cmd = [
                self.ffmpeg_exe,
                "-y",
                "-i", temp_video_only,
                "-i", mixed_audio_wav_path,
                "-c:v", "copy",
                "-c:a", "aac",
                "-b:a", "192k",
                "-shortest",
                output_video_path
            ]
            res = subprocess.run(mux_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if res.returncode != 0:
                raise RuntimeError(f"FFmpeg audio muxing failed: {res.stderr.decode('utf-8', errors='ignore')}")

            if os.path.exists(temp_video_only):
                try:
                    os.remove(temp_video_only)
                except OSError:
                    pass

        if progress_callback:
            progress_callback(1.0, "Rendering completed successfully!")
