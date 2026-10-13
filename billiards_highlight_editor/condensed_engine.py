"""
Full Match Condensed Engine for Billiards Video Editing (YouTube 16:9).

Implements the 4 Core Pillars of Condensed Billiards Matches:
1. Strike Trigger (Audio Peak Detection):
   - Transient impact analysis in billiard frequency band (1kHz - 8kHz)
   - Pre-roll lead-in: exact -2.0 seconds before cue-ball impact
2. End Trigger (Optical Flow / Pixel Motion):
   - Table felt ROI motion velocity monitoring
   - Ends when ball velocity decays to 0 (v = 0) OR pocket drop + 1.0s buffer
3. Persistent Scoreboard HUD:
   - Fixed screen position (top-left or bottom-left)
   - Score remains static until the exact second 9-ball drops into pocket
4. High-Speed GPU NVENC Concatenation:
   - Hardware accelerated FFmpeg encoding (-c:v h264_nvenc -preset p4)
   - Generates YouTube-ready 16:9 master video in seconds + YouTube chapters
"""

import os
import sys
import subprocess
import tempfile
import cv2
import numpy as np
from typing import List, Dict, Tuple, Optional, Any, Callable
from dataclasses import dataclass, field
import imageio_ffmpeg

from billiards_highlight_editor.config import EditorConfig, VideoFormat
from billiards_highlight_editor.models import MatchMetadata, ScoreboardState, MatchState
from billiards_highlight_editor.audio_analyzer import AudioAnalyzer
from billiards_highlight_editor.motion_tracker import MotionTracker
from billiards_highlight_editor.rack_winner_detector import RackWinnerDetector
from billiards_highlight_editor.hardware_profiler import HardwareProfiler


@dataclass
class CondensedShot:
    shot_id: int
    rack_number: int
    strike_time: float               # Audio impact peak timestamp in source video (seconds)
    start_time: float                # Strike time - 2.0s
    end_time: float                  # Velocity = 0 or pot + 1.0s
    is_break: bool = False
    is_nine_ball_pot: bool = False
    win_t_offset: Optional[float] = None  # Offset from shot start when 9-ball drops and score flips
    score_before: Tuple[int, int] = (0, 0)
    score_after: Tuple[int, int] = (0, 0)
    source_file: str = ""
    description: str = ""

    @property
    def duration(self) -> float:
        return max(0.1, self.end_time - self.start_time)


@dataclass
class CondensedMatchPlan:
    metadata: MatchMetadata
    shots: List[CondensedShot] = field(default_factory=list)
    total_duration_sec: float = 0.0
    youtube_chapters: List[Dict[str, Any]] = field(default_factory=list)


class BilliardsCondensedEngine:
    def __init__(self, config: Optional[EditorConfig] = None):
        self.config = config or EditorConfig()
        self.audio_analyzer = AudioAnalyzer(self.config.audio, self.config.trimming)
        self.motion_tracker = MotionTracker()
        self.rack_detector = RackWinnerDetector()
        self.ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        self.profiler = HardwareProfiler(self.ffmpeg_exe)

    def detect_strike_triggers(
        self,
        audio_data: np.ndarray,
        sample_rate: int,
        pre_roll_sec: float = 2.0,
        min_interval_sec: float = 2.2
    ) -> List[float]:
        """
        Strike Trigger (Pillar 1):
        Uses Audio Peak Detection / Transient Spike in the 1kHz - 8kHz frequency band.
        Returns list of strike impact timestamps.
        Each shot's in-point will be set to: strike_time - pre_roll_sec (-2.0s).
        """
        raw_impacts = self.audio_analyzer.detect_all_impacts(
            audio_data,
            sample_rate,
            min_gap_sec=min_interval_sec
        )
        return sorted(raw_impacts)

    def detect_end_trigger(
        self,
        cap: cv2.VideoCapture,
        strike_time: float,
        table_roi: Optional[Tuple[int, int, int, int]] = None,
        max_duration_sec: float = 12.0,
        min_duration_sec: float = 1.5,
        fps: float = 30.0,
        pocket_buffer_sec: float = 1.0,
        stillness_buffer_sec: float = 0.5
    ) -> Tuple[float, bool, Optional[float]]:
        """
        End Trigger (Pillar 2):
        Inspects optical flow / pixel motion difference on table felt ROI.
        Ends when ball velocity decays to 0 (v = 0) OR after pocket drop + 1.0s.
        Returns: (end_time, is_potted, pot_timestamp_relative_to_strike)
        """
        if table_roi is None:
            w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 1920)
            h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 1080)
            table_roi = (int(w * 0.15), int(h * 0.15), int(w * 0.70), int(h * 0.70))

        pockets = self.rack_detector.compute_table_pockets(table_roi)

        # Seek to strike_time
        cap.set(cv2.CAP_PROP_POS_MSEC, max(0.0, strike_time - 0.2) * 1000.0)
        ret, prev_frame = cap.read()
        if not ret or prev_frame is None:
            return strike_time + min_duration_sec + stillness_buffer_sec, False, None

        prev_gray = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY)
        tx, ty, tw, th = table_roi

        step_frames = max(1, int(fps / 10.0))  # Sample every ~0.1s for speed
        consecutive_still_samples = 0
        samples_needed = 3  # ~0.3s of stillness
        motion_threshold = 0.12  # motion percentage below which balls are considered still

        current_t = strike_time
        ball_stopped_t = strike_time + min_duration_sec
        pocket_drop_t = None
        is_potted = False

        while current_t - strike_time < max_duration_sec:
            # Skip frames for performance
            for _ in range(step_frames - 1):
                cap.grab()
            ret, curr_frame = cap.read()
            if not ret or curr_frame is None:
                break

            current_t += float(step_frames) / fps
            curr_gray = cv2.cvtColor(curr_frame, cv2.COLOR_BGR2GRAY)

            # 1. Check for ball drop into pockets
            if not is_potted and (current_t - strike_time) >= 0.8:
                p_drop = self.rack_detector.detect_ball_potted_in_pocket(prev_frame, curr_frame, pockets)
                if p_drop:
                    is_potted = True
                    pocket_drop_t = current_t
                    # End trigger: pocket drop + 1.0s buffer
                    ball_stopped_t = current_t + pocket_buffer_sec
                    break

            # 2. Check table felt motion velocity
            p_crop = prev_gray[ty:ty+th, tx:tx+tw]
            c_crop = curr_gray[ty:ty+th, tx:tx+tw]
            diff = cv2.absdiff(p_crop, c_crop)
            _, thresh = cv2.threshold(diff, 25, 255, cv2.THRESH_BINARY)
            moving_px = cv2.countNonZero(thresh)
            motion_ratio = (moving_px / float(tw * th)) * 100.0

            if (current_t - strike_time) >= min_duration_sec:
                if motion_ratio <= motion_threshold:
                    consecutive_still_samples += 1
                    if consecutive_still_samples >= samples_needed:
                        # Ball velocity reached 0
                        ball_stopped_t = current_t + stillness_buffer_sec
                        break
                else:
                    consecutive_still_samples = 0

            prev_frame = curr_frame
            prev_gray = curr_gray

        # Return end_time clamped to safety boundaries
        end_time = max(strike_time + min_duration_sec, min(strike_time + max_duration_sec, ball_stopped_t))
        pot_rel_strike = (pocket_drop_t - strike_time) if pocket_drop_t is not None else None
        return round(end_time, 3), is_potted, pot_rel_strike

    def build_condensed_plan(
        self,
        video_path: str,
        metadata: MatchMetadata,
        known_breaks: Optional[List[Dict[str, Any]]] = None,
        known_racks: Optional[List[Dict[str, Any]]] = None,
        progress_callback: Optional[Callable[[float, str], None]] = None
    ) -> CondensedMatchPlan:
        """
        Constructs the complete Condensed Match timeline:
        - Extracts strikes using audio peak detection (-2.0s lead-in)
        - Calculates end triggers via visual optical flow (v=0 / pot + 1.0s)
        - Maps scores & marks exact 9-ball pot moments
        """
        if progress_callback:
            progress_callback(0.05, "Analyzing audio waveform & extracting strike triggers...")

        sr, audio_data = self.audio_analyzer.extract_audio_wav(video_path)
        strike_times = self.detect_strike_triggers(audio_data, sr, pre_roll_sec=2.0)
        break_candidates = known_breaks or self.audio_analyzer.detect_break_shot_candidates(audio_data, sr)

        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        ret, first_frame = cap.read()
        table_roi = None
        if ret and first_frame is not None:
            table_roi = self.motion_tracker.detect_table_felt_roi(first_frame)

        if progress_callback:
            progress_callback(0.20, f"Detected {len(strike_times)} potential strikes. Computing optical flow end triggers...")

        condensed_shots: List[CondensedShot] = []
        break_timestamps = [b["peak_time"] for b in break_candidates]

        # Group strikes into racks if known_racks provided, or by breaks
        total_strikes = len(strike_times)
        for idx, strike_t in enumerate(strike_times):
            if progress_callback and (idx % 10 == 0 or idx == total_strikes - 1):
                pct = 0.20 + 0.50 * (float(idx) / max(1, total_strikes))
                progress_callback(pct, f"Analyzing Shot {idx+1}/{total_strikes} ({strike_t:.1f}s)...")

            # Check if this strike is a break shot
            is_break = False
            for b_t in break_timestamps:
                if abs(strike_t - b_t) < 1.5:
                    is_break = True
                    break

            start_t = max(0.0, strike_t - 2.0)  # -2.0s rule

            # End Trigger via optical flow / pocket drop
            if is_break:
                # Break shot takes ~7.5s - 9.0s for all balls to scatter and rest
                end_t = strike_t + 7.5
                is_potted = False
                win_offset = None
            else:
                end_t, is_potted, pot_rel = self.detect_end_trigger(
                    cap=cap,
                    strike_time=strike_t,
                    table_roi=table_roi,
                    fps=fps,
                    pocket_buffer_sec=1.0,
                    stillness_buffer_sec=0.5
                )
                win_offset = (2.0 + pot_rel) if pot_rel is not None else None

            shot = CondensedShot(
                shot_id=idx + 1,
                rack_number=1,
                strike_time=round(strike_t, 3),
                start_time=round(start_t, 3),
                end_time=round(end_t, 3),
                is_break=is_break,
                source_file=video_path,
                win_t_offset=win_offset,
                description="Break Shot" if is_break else "Condensed Shot"
            )
            condensed_shots.append(shot)

        cap.release()

        # If known_racks provided, map scores and rack numbers accurately
        if known_racks:
            self._map_known_racks_to_shots(condensed_shots, known_racks, metadata)

        total_dur = sum(s.duration for s in condensed_shots)

        # Build YouTube Chapters
        chapters = self._generate_youtube_chapters(condensed_shots, metadata)

        return CondensedMatchPlan(
            metadata=metadata,
            shots=condensed_shots,
            total_duration_sec=total_dur,
            youtube_chapters=chapters
        )

    def _map_known_racks_to_shots(
        self,
        shots: List[CondensedShot],
        racks: List[Dict[str, Any]],
        metadata: MatchMetadata
    ):
        """
        Maps known rack boundaries, scores, and winning 9-ball pot triggers to shots.
        """
        for r_idx, r in enumerate(racks):
            r_num = r.get("rack", r_idx + 1)
            r_start = r.get("start", 0.0)
            r_end = r.get("end", 999999.0)
            s_before = r.get("s_before", (0, 0))
            s_after = r.get("s_after", (0, 0))
            win_t = r.get("win_t", None)

            rack_shots = [s for s in shots if r_start <= s.strike_time <= r_end]
            if not rack_shots:
                continue

            for s in rack_shots:
                s.rack_number = r_num
                s.score_before = s_before
                s.score_after = s_before  # default maintains score_before

            # Identify last shot of rack as the 9-ball pot
            last_shot = rack_shots[-1]
            last_shot.is_nine_ball_pot = True
            last_shot.score_after = s_after
            if win_t is not None:
                # win_t offset relative to last shot start
                last_shot.win_t_offset = max(1.0, win_t - last_shot.start_time)
            else:
                last_shot.win_t_offset = max(1.0, last_shot.duration - 1.0)
            last_shot.description = f"Ván {r_num} - Cú ăn bi 9 quyết định ván"

    def _generate_youtube_chapters(
        self,
        shots: List[CondensedShot],
        metadata: MatchMetadata
    ) -> List[Dict[str, Any]]:
        """
        Generates standard YouTube timestamps for video description.
        Format: MM:SS - Tiêu đề
        """
        chapters = []
        current_time = 0.0
        seen_racks = set()

        # Intro chapter
        chapters.append({
            "timestamp_str": "00:00",
            "time_sec": 0.0,
            "title": f"Khai mạc trận đấu: {metadata.player_1_name} vs {metadata.player_2_name}"
        })

        for s in shots:
            if s.rack_number not in seen_racks:
                seen_racks.add(s.rack_number)
                mins = int(current_time // 60)
                secs = int(current_time % 60)
                t_str = f"{mins:02d}:{secs:02d}"
                s_txt = f"({s.score_before[0]} - {s.score_before[1]})"
                chapters.append({
                    "timestamp_str": t_str,
                    "time_sec": current_time,
                    "title": f"Ván {s.rack_number} {s_txt}: Phá bi & Diễn biến"
                })

            if s.is_nine_ball_pot:
                win_time = current_time + (s.win_t_offset or (s.duration - 1.0))
                mins = int(win_time // 60)
                secs = int(win_time % 60)
                t_str = f"{mins:02d}:{secs:02d}"
                chapters.append({
                    "timestamp_str": t_str,
                    "time_sec": win_time,
                    "title": f"Ván {s.rack_number} ({s.score_after[0]} - {s.score_after[1]}): Cú ăn bi 9 chốt điểm"
                })

            current_time += s.duration

        return chapters

    def render_condensed_video_nvenc(
        self,
        plan: CondensedMatchPlan,
        scoreboard_asset_generator_func: Callable[[int, int, str], str],
        output_mp4_path: str,
        temp_dir: Optional[str] = None,
        progress_callback: Optional[Callable[[float, str], None]] = None
    ) -> str:
        """
        Concatenation (Pillar 4):
        Assembles all condensed shots sequentially using FFmpeg with GPU NVENC.
        Applies fixed persistent scoreboard HUD that updates ONLY when bi 9 drops.
        """
        os.makedirs(os.path.dirname(os.path.abspath(output_mp4_path)), exist_ok=True)
        work_temp = temp_dir or os.path.join(temp_dir or os.path.dirname(output_mp4_path), "temp_condensed_clips")
        os.makedirs(work_temp, exist_ok=True)

        hw_profile = self.profiler.profile_and_optimize()
        nvenc_args = hw_profile.ffmpeg_encoder_args

        total_shots = len(plan.shots)
        clip_paths = []

        if progress_callback:
            progress_callback(0.70, f"Rendering {total_shots} condensed clips with NVENC GPU acceleration...")

        try:
            for s_idx, shot in enumerate(plan.shots):
                if progress_callback and (s_idx % 5 == 0 or s_idx == total_shots - 1):
                    pct = 0.70 + 0.25 * (float(s_idx) / max(1, total_shots))
                    progress_callback(pct, f"GPU Rendering Shot {s_idx+1}/{total_shots}...")

                out_clip = os.path.join(work_temp, f"shot_{s_idx:04d}.mp4")
                clip_paths.append(out_clip)

                # Scoreboard handling:
                # If this shot has 9-ball pot, use dynamic scoreboard jump
                s_before_png = scoreboard_asset_generator_func(shot.score_before[0], shot.score_before[1], work_temp)
                
                if shot.is_nine_ball_pot and shot.score_after != shot.score_before:
                    s_after_png = scoreboard_asset_generator_func(shot.score_after[0], shot.score_after[1], work_temp)
                    flip_t = shot.win_t_offset or (shot.duration - 1.0)
                    # Two scoreboard layers: before flip_t and after flip_t
                    filter_complex = (
                        f"[0:v]scale=1920:1080[v0]; "
                        f"[1:v]scale=1920:1080[sb1]; "
                        f"[2:v]scale=1920:1080[sb2]; "
                        f"[v0][sb1]overlay=0:0:enable='lt(t,{flip_t:.3f})'[v1]; "
                        f"[v1][sb2]overlay=0:0:enable='gte(t,{flip_t:.3f})'[vout]"
                    )
                    cmd = [
                        self.ffmpeg_exe, "-y",
                        "-ss", f"{shot.start_time:.3f}",
                        "-to", f"{shot.end_time:.3f}",
                        "-i", shot.source_file,
                        "-loop", "1", "-i", s_before_png,
                        "-loop", "1", "-i", s_after_png,
                        "-filter_complex", filter_complex,
                        "-map", "[vout]",
                        "-map", "0:a?",
                        *nvenc_args,
                        "-pix_fmt", "yuv420p",
                        "-c:a", "aac", "-b:a", "192k",
                        "-shortest",
                        out_clip
                    ]
                else:
                    filter_complex = (
                        f"[0:v]scale=1920:1080[v0]; "
                        f"[1:v]scale=1920:1080[sb]; "
                        f"[v0][sb]overlay=0:0[vout]"
                    )
                    cmd = [
                        self.ffmpeg_exe, "-y",
                        "-ss", f"{shot.start_time:.3f}",
                        "-to", f"{shot.end_time:.3f}",
                        "-i", shot.source_file,
                        "-loop", "1", "-i", s_before_png,
                        "-filter_complex", filter_complex,
                        "-map", "[vout]",
                        "-map", "0:a?",
                        *nvenc_args,
                        "-pix_fmt", "yuv420p",
                        "-c:a", "aac", "-b:a", "192k",
                        "-shortest",
                        out_clip
                    ]

                result = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
                if result.returncode != 0:
                    raise RuntimeError(f"FFmpeg failed rendering clip {out_clip}: {result.stderr.decode('utf-8', errors='ignore')}")

            # Concat all clips using FFmpeg concat demuxer (lossless stream copy, 0 re-encode)
            if progress_callback:
                progress_callback(0.96, "Concatenating all condensed shots into Master video...")

            concat_txt = os.path.join(work_temp, "concat_list.txt")
            with open(concat_txt, "w", encoding="utf-8") as f:
                for cp in clip_paths:
                    norm = os.path.abspath(cp).replace("\\", "/")
                    f.write(f"file '{norm}'\n")

            concat_cmd = [
                self.ffmpeg_exe, "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", concat_txt,
                "-c", "copy",
                output_mp4_path
            ]
            subprocess.run(concat_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=True)

            # Save YouTube Chapters file
            chapters_file = os.path.splitext(output_mp4_path)[0] + "_YouTube_Chapters.txt"
            with open(chapters_file, "w", encoding="utf-8") as f:
                f.write(f"=== YOUTUBE CHAPTERS: {plan.metadata.player_1_name} vs {plan.metadata.player_2_name} ===\n\n")
                for ch in plan.youtube_chapters:
                    f.write(f"{ch['timestamp_str']} - {ch['title']}\n")

            if progress_callback:
                progress_callback(1.0, f"Condensed Master export complete: {output_mp4_path}")

            return output_mp4_path

        finally:
            # Cleanup temp clips
            if os.path.exists(work_temp):
                try:
                    for f in os.listdir(work_temp):
                        os.remove(os.path.join(work_temp, f))
                    os.rmdir(work_temp)
                except Exception:
                    pass
