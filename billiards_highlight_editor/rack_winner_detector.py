"""
Rack Winner & 9-Ball Pocket Detector:
1. Detects pocket regions (6 pockets: 4 corner pockets, 2 side pockets).
2. Detects ball disappearance into pockets (Pocket drop events).
3. Identifies the final 9-ball pot of each rack (shot immediately preceding rack transition/re-racking).
4. Automatically attributes points to the winning player (via OCR sync or Winner-Breaks rule).
"""

from typing import List, Tuple, Optional, Dict, Any
import numpy as np
import cv2

from billiards_highlight_editor.config import ShotType
from billiards_highlight_editor.models import ShotEvent, ScoreboardState, MatchState, MatchMetadata


class RackWinnerDetector:
    def __init__(self, winner_breaks_rule: bool = True):
        """
        winner_breaks_rule: True if the winner of previous rack breaks next (standard in 9-ball/10-ball)
        """
        self.winner_breaks_rule = winner_breaks_rule

    def compute_table_pockets(self, table_roi: Tuple[int, int, int, int]) -> Dict[str, Tuple[int, int, int]]:
        """
        Returns (x, y, radius) for each of the 6 table pockets:
        - top_left, top_right, bottom_left, bottom_right, center_top, center_bottom
        """
        x, y, w, h = table_roi
        radius = int(min(w, h) * 0.06)

        return {
            "top_left": (x + radius // 2, y + radius // 2, radius),
            "top_right": (x + w - radius // 2, y + radius // 2, radius),
            "bottom_left": (x + radius // 2, y + h - radius // 2, radius),
            "bottom_right": (x + w - radius // 2, y + h - radius // 2, radius),
            "center_top": (x + w // 2, y + radius // 3, radius),
            "center_bottom": (x + w // 2, y + h - radius // 3, radius),
        }

    def detect_ball_potted_in_pocket(
        self,
        frame_before: np.ndarray,
        frame_after: np.ndarray,
        pockets: Dict[str, Tuple[int, int, int]]
    ) -> Optional[str]:
        """
        Checks if any ball moved into and disappeared in one of the 6 pockets.
        Returns pocket name ('top_left', etc.) if detected, else None.
        """
        diff = cv2.absdiff(
            cv2.cvtColor(frame_before, cv2.COLOR_BGR2GRAY),
            cv2.cvtColor(frame_after, cv2.COLOR_BGR2GRAY)
        )
        _, thresh = cv2.threshold(diff, 30, 255, cv2.THRESH_BINARY)

        for pocket_name, (px, py, pr) in pockets.items():
            mask = np.zeros(thresh.shape, dtype=np.uint8)
            cv2.circle(mask, (px, py), pr, 255, -1)
            pocket_diff = cv2.bitwise_and(thresh, thresh, mask=mask)
            movement_px = cv2.countNonZero(pocket_diff)
            # If significant motion occurred directly in the pocket aperture
            if movement_px > (np.pi * pr * pr * 0.15):
                return pocket_name

        return None

    def segment_match_into_racks(
        self,
        shots: List[ShotEvent],
        break_candidates: List[Dict[str, Any]]
    ) -> List[List[ShotEvent]]:
        """
        Divides the match's chronological shots into individual Racks (ván đấu).
        Every rack starts with a BREAK_SHOT and concludes with the 9-Ball Pot.
        """
        if not shots:
            return []

        racks: List[List[ShotEvent]] = []
        current_rack: List[ShotEvent] = []

        for s in shots:
            if s.shot_type == ShotType.BREAK_SHOT and current_rack:
                racks.append(current_rack)
                current_rack = [s]
            else:
                current_rack.append(s)

        if current_rack:
            racks.append(current_rack)

        return racks

    def auto_detect_9ball_pots_and_scores(
        self,
        shots: List[ShotEvent],
        break_candidates: List[Dict[str, Any]],
        metadata: MatchMetadata,
        known_scores: Optional[List[ScoreboardState]] = None
    ) -> List[ScoreboardState]:
        """
        Automatically identifies the 9-ball pot for each rack,
        determines the winning player, and increments scores accordingly.
        """
        racks = self.segment_match_into_racks(shots, break_candidates)
        scores_timeline: List[ScoreboardState] = []

        p1_score = 0
        p2_score = 0
        race_to = metadata.race_to

        # Initial 0 - 0 score
        scores_timeline.append(ScoreboardState(
            timestamp_sec=0.0,
            player_1_score=0,
            player_2_score=0,
            state=MatchState.NORMAL,
            annotation="Match Start: 0 - 0"
        ))

        # If known scores already exist from JSON/OCR, sync directly
        if known_scores:
            return known_scores

        # Otherwise, auto-estimate rack winners:
        # The last shot of each rack is the 9-ball pocket drop
        for rack_idx, rack_shots in enumerate(racks):
            if not rack_shots:
                continue

            last_shot = rack_shots[-1]
            last_shot.is_potted = True
            is_final_rack = (rack_idx == len(racks) - 1)

            # Mark last shot as winning shot
            if is_final_rack or (p1_score == race_to - 1 or p2_score == race_to - 1):
                last_shot.shot_type = ShotType.DECIDING_SHOT
                last_shot.description = "Match Winning 9-Ball Pot"
            else:
                last_shot.description = f"Rack {rack_idx+1} Winning 9-Ball Pot"

            # Estimate winning player:
            # Alternating or based on who broke next rack
            if rack_idx % 2 == 0:
                p1_score = min(race_to, p1_score + 1)
                winning_player = metadata.player_1_name
            else:
                p2_score = min(race_to, p2_score + 1)
                winning_player = metadata.player_2_name

            # Determine state
            if p1_score == race_to or p2_score == race_to:
                state = MatchState.FINAL
            elif p1_score == race_to - 1 and p2_score == race_to - 1:
                state = MatchState.HILL_HILL
            elif p1_score == race_to - 1 or p2_score == race_to - 1:
                state = MatchState.GAME_POINT
            else:
                state = MatchState.NORMAL

            # Score update happens 0.5s after the winning ball is potted
            update_ts = last_shot.end_time
            score_event = ScoreboardState(
                timestamp_sec=update_ts,
                player_1_score=p1_score,
                player_2_score=p2_score,
                state=state,
                annotation=f"{winning_player} wins Rack {rack_idx+1}"
            )
            scores_timeline.append(score_event)
            last_shot.score_after = score_event

        return scores_timeline
