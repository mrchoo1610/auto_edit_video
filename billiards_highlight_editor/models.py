"""
Data models representing Billiards highlight events, timeline phases, and score states.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict, Any
from enum import Enum
from billiards_highlight_editor.config import ShotType, VideoFormat


class BeatType(str, Enum):
    BEAT_1_TENSION = "tension"       # 1.0 - 1.5s (pose down, bridge hand set, 1-2 practice strokes)
    BEAT_2_IMPACT = "impact"         # Cue impacts ball (100% speed)
    BEAT_3_RESOLUTION = "resolution" # 1.5 - 3.0s (ball path and pocket drop, 100% or 50% slow-mo)


class MatchState(str, Enum):
    NORMAL = "NORMAL"
    GAME_POINT = "GAME_POINT"
    HILL_HILL = "HILL-HILL"
    FINAL = "FINAL"


class TimelinePhase(str, Enum):
    PHASE_0_INTRO = "match_intro"    # 0:00 - 0:03.5 Cinematic match intro card
    PHASE_1_HOOK = "hook_intro"      # 0:03.5 - 0:08 Break shot hook
    PHASE_2_FLOW = "match_flow"      # Fast-paced flow & technical shots & safety
    PHASE_3_CLIMAX = "climax_hill"   # Problem shots + Hill-Hill + climax audio pause
    PHASE_4_OUTRO = "resolution_outro" # Final winning ball + handshake + FINAL scoreboard


@dataclass
class ScoreboardState:
    timestamp_sec: float
    player_1_score: int
    player_2_score: int
    state: MatchState = MatchState.NORMAL
    annotation: str = ""
    rack_label: str = ""
    break_start_sec: Optional[float] = None
    break_impact_sec: Optional[float] = None
    break_end_sec: Optional[float] = None
    runout_start_sec: Optional[float] = None
    runout_end_sec: Optional[float] = None
    runout_file: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": f"{int(self.timestamp_sec // 60):02d}:{self.timestamp_sec % 60:05.2f}",
            "player_1_score": self.player_1_score,
            "player_2_score": self.player_2_score,
            "state": self.state.value,
            "annotation": self.annotation,
            "rack_label": self.rack_label,
            "break_start_sec": self.break_start_sec,
            "break_end_sec": self.break_end_sec,
            "runout_start_sec": self.runout_start_sec,
            "runout_end_sec": self.runout_end_sec,
            "runout_file": self.runout_file
        }


@dataclass
class MatchMetadata:
    player_1_name: str = "Chung Choo"
    player_2_name: str = "Khương Liều"
    tournament_title: str = "Giao Lưu CLB"
    round_name: str = "Trận Giao Hữu"
    race_to: int = 3
    game_discipline: str = "9 POOL"


@dataclass
class ShotBeat:
    beat_type: BeatType
    start_time: float
    end_time: float
    playback_speed: float = 1.0


@dataclass
class ShotEvent:
    shot_id: int
    shot_type: ShotType
    start_time: float
    impact_time: float
    end_time: float
    is_masterpiece: bool = False
    is_deciding_rack: bool = False
    camera_shake: bool = False
    beats: List[ShotBeat] = field(default_factory=list)
    score_after: Optional[ScoreboardState] = None
    is_potted: bool = True
    is_miss: bool = False
    description: str = ""

    @property
    def duration(self) -> float:
        return max(0.0, self.end_time - self.start_time)


@dataclass
class TimelineSegment:
    segment_id: int
    phase: TimelinePhase
    source_start_sec: float
    source_end_sec: float
    target_start_sec: float
    target_end_sec: float
    playback_speed: float = 1.0
    shot_event: Optional[ShotEvent] = None
    has_camera_shake: bool = False
    camera_shake_intensity: float = 0.03
    overlay_text: str = ""
    scoreboard_state: Optional[ScoreboardState] = None
    audio_ducking: bool = False
    audio_mute_bgm: bool = False
    rack_number: int = 1
    rack_label: str = ""
    rack_banner_title: str = ""
    rack_banner_subtitle: str = ""
    action_label: str = ""
    source_file: str = ""

    @property
    def duration(self) -> float:
        return max(0.0, self.source_end_sec - self.source_start_sec)


@dataclass
class HighlightScript:
    metadata: MatchMetadata
    segments: List[TimelineSegment] = field(default_factory=list)
    total_duration_sec: float = 0.0
    video_format: VideoFormat = VideoFormat.HORIZONTAL_YOUTUBE
