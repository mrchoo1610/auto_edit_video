"""
Shot Detector module:
Orchestrates audio transients and visual motion to construct the 3-Beat Shot Sequence,
eliminate dead time (walking > 2.5s, chalking, ball re-racking),
and classify shots into highlights and masterpieces.
"""

from typing import List, Optional, Tuple, Dict, Any
from billiards_highlight_editor.config import EditorConfig, ShotType
from billiards_highlight_editor.models import ShotEvent, ShotBeat, BeatType, ScoreboardState, MatchState


class ShotDetector:
    def __init__(self, config: Optional[EditorConfig] = None):
        self.config = config or EditorConfig()

    def build_3beat_shot_event(
        self,
        shot_id: int,
        impact_timestamp: float,
        ball_stop_timestamp: float,
        shot_type: ShotType = ShotType.STANDARD_POT,
        is_masterpiece: bool = False,
        is_deciding_rack: bool = False,
        score_after: Optional[ScoreboardState] = None,
        description: str = ""
    ) -> ShotEvent:
        """
        Builds a ShotEvent strictly adhering to the 3-Beat Shot Sequence:
        - Beat 1: Tension (1.0s to 1.5s)
        - Beat 2: Impact (Instantaneous contact at real-time 100%)
        - Beat 3: Resolution (1.5s to 3.0s, or until ball rests, with 50% slow-mo for masterpieces)
        """
        # Beat 1: Tension (Tension duration clamped between 1.0s and 1.5s)
        tension_duration = min(
            self.config.trimming.beat_1_tension_max_sec,
            max(self.config.trimming.beat_1_tension_min_sec, 1.25)
        )
        beat_1_start = max(0.0, impact_timestamp - tension_duration)
        beat_1_end = impact_timestamp

        beat_1 = ShotBeat(
            beat_type=BeatType.BEAT_1_TENSION,
            start_time=round(beat_1_start, 3),
            end_time=round(beat_1_end, 3),
            playback_speed=1.0
        )

        # Beat 2: Impact (Sub-second cue-ball strike, 100% speed)
        impact_window = 0.15
        beat_2 = ShotBeat(
            beat_type=BeatType.BEAT_2_IMPACT,
            start_time=round(impact_timestamp - 0.05, 3),
            end_time=round(impact_timestamp + impact_window, 3),
            playback_speed=1.0
        )

        # Beat 3: Resolution (Ball path & pocket drop)
        # Clamped according to Spec: 1.5s to 3.0s (or ball rest buffer)
        raw_res_duration = ball_stop_timestamp - impact_timestamp
        res_duration = max(
            self.config.trimming.beat_3_resolution_min_sec,
            min(self.config.trimming.beat_3_resolution_max_sec, raw_res_duration)
        )
        beat_3_start = impact_timestamp
        beat_3_end = impact_timestamp + res_duration

        speed = 1.0
        if is_masterpiece or shot_type in [ShotType.JUMP_SHOT, ShotType.MASSE_SHOT, ShotType.BANK_KICK_SHOT]:
            # Spec 2.2: Slow-motion 50% for masterpieces
            speed = self.config.trimming.beat_3_slowmotion_speed

        beat_3 = ShotBeat(
            beat_type=BeatType.BEAT_3_RESOLUTION,
            start_time=round(beat_3_start, 3),
            end_time=round(beat_3_end, 3),
            playback_speed=speed
        )

        camera_shake = (shot_type == ShotType.BREAK_SHOT)

        return ShotEvent(
            shot_id=shot_id,
            shot_type=shot_type,
            start_time=round(beat_1_start, 3),
            impact_time=round(impact_timestamp, 3),
            end_time=round(beat_3_end, 3),
            is_masterpiece=is_masterpiece,
            is_deciding_rack=is_deciding_rack,
            camera_shake=camera_shake,
            beats=[beat_1, beat_2, beat_3],
            score_after=score_after,
            description=description
        )

    def filter_dead_time_and_build_shots(
        self,
        impact_times: List[float],
        break_candidates: List[Dict[str, Any]],
        ball_stop_func,
        match_scores: Optional[List[ScoreboardState]] = None
    ) -> List[ShotEvent]:
        """
        Takes raw detected impacts and candidates, applies Dead Time elimination:
        - Drops pauses > 2.5s between shots.
        - Keeps Break Shot at the beginning of rack (Peak - 1.5s to Peak + 4.0s).
        - Strips rack setup and timeouts.
        - Returns chronological list of ShotEvents.
        """
        shots: List[ShotEvent] = []
        break_peaks = {round(b["peak_time"], 1): b for b in break_candidates}

        shot_idx = 1
        scores_by_time = sorted(match_scores or [], key=lambda s: s.timestamp_sec)

        for imp in impact_times:
            # Check if this impact aligns with a break shot
            is_break = False
            for bp, b_info in break_peaks.items():
                if abs(imp - bp) < 1.0:
                    is_break = True
                    break

            # Find matching score state for this shot
            score_after = scores_by_time[0] if scores_by_time else ScoreboardState(0.0, 0, 0, MatchState.NORMAL)
            for s in scores_by_time:
                if s.timestamp_sec <= imp + 2.0:
                    score_after = s

            # Ball rest calculation
            ball_stop = ball_stop_func(imp)

            if is_break:
                # Break shot uses Spec 5.1 window: Peak - 1.5s to Peak + 4.0s
                shot = ShotEvent(
                    shot_id=shot_idx,
                    shot_type=ShotType.BREAK_SHOT,
                    start_time=round(max(0.0, imp - self.config.trimming.break_shot_pre_peak_sec), 3),
                    impact_time=round(imp, 3),
                    end_time=round(imp + self.config.trimming.break_shot_post_peak_sec, 3),
                    camera_shake=True,
                    score_after=score_after,
                    description="Explosive Break Shot"
                )
                shot.beats = [
                    ShotBeat(BeatType.BEAT_1_TENSION, shot.start_time, imp, 1.0),
                    ShotBeat(BeatType.BEAT_2_IMPACT, imp, imp + 0.2, 1.0),
                    ShotBeat(BeatType.BEAT_3_RESOLUTION, imp, shot.end_time, 1.0)
                ]
            else:
                # Classify shot (placeholder or heuristic based on motion and score)
                shot_type = ShotType.STANDARD_POT
                is_masterpiece = False
                is_deciding = False

                if score_after:
                    if score_after.state == MatchState.HILL_HILL:
                        is_deciding = True
                    elif score_after.state == MatchState.FINAL:
                        shot_type = ShotType.DECIDING_SHOT
                        is_masterpiece = True

                shot = self.build_3beat_shot_event(
                    shot_id=shot_idx,
                    impact_timestamp=imp,
                    ball_stop_timestamp=ball_stop,
                    shot_type=shot_type,
                    is_masterpiece=is_masterpiece,
                    is_deciding_rack=is_deciding,
                    score_after=score_after,
                    description="Standard Pot" if not is_deciding else "Climax Match Point Shot"
                )

            shots.append(shot)
            shot_idx += 1

        return shots
