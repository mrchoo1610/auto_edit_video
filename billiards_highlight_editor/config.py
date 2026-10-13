"""
Configuration specifications for Billiards Highlight AI Editor
Matching the requirements in billiards_ai_editor_agent_spec.md
"""

from dataclasses import dataclass, field
from typing import Tuple, List, Optional
from enum import Enum


class VideoFormat(str, Enum):
    HORIZONTAL_YOUTUBE = "horizontal_16_9"
    VERTICAL_SHORTS = "vertical_9_16"


class ShotType(str, Enum):
    BREAK_SHOT = "break_shot"
    STANDARD_POT = "standard_pot"
    POSITIONAL_DRAW_FOLLOW = "positional_draw_follow"
    SAFETY_EXCHANGE = "safety_exchange"
    JUMP_SHOT = "jump_shot"
    MASSE_SHOT = "masse_shot"
    BANK_KICK_SHOT = "bank_kick_shot"
    DECIDING_SHOT = "deciding_shot"
    MISSED_SHOT = "missed_shot"
    DRAMATIC_MISS = "dramatic_miss"


@dataclass
class AudioConfig:
    # Spec 4.2 & 5.1: Audio Mixing & Break Detection
    fx_volume: float = 1.00          # FX: 100% (priority #1)
    bgm_volume: float = 0.30         # BGM: 25% - 35%
    ducking_volume: float = 0.15     # Audio ducking: 15% on impact/commentary
    climax_silence_duration: float = 1.0  # 1.0s silence before clutch shot
    
    # Break Shot Audio Anchor: 2kHz - 6kHz, peak threshold > -3dB
    break_filter_low_hz: float = 2000.0
    break_filter_high_hz: float = 6000.0
    break_peak_threshold_db: float = -3.0
    break_min_distance_seconds: float = 8.0  # Min time between distinct breaks


@dataclass
class TrimmingConfig:
    # Spec 2.1: Dead Time Elimination
    max_walking_observation_sec: float = 2.5
    allow_chalking_close_up_deciding_rack: bool = True
    cut_rack_setup_completely: bool = True
    cut_timeouts_referee_completely: bool = True
    
    # Spec 2.2 & 3: 3-Beat Shot Sequence (60s Golden Ratio per rack)
    beat_1_tension_min_sec: float = 2.0
    beat_1_tension_max_sec: float = 2.5
    beat_2_impact_speed: float = 1.0      # Real-time 100%
    beat_3_resolution_min_sec: float = 2.5
    beat_3_resolution_max_sec: float = 3.5
    beat_3_slowmotion_speed: float = 0.50  # 50% slow-motion for masterpieces
    ball_stopped_buffer_sec: float = 0.5   # Stop 0.5s after velocity = 0
    
    # Missed Shots policy
    include_routine_misses: bool = False       # Drop unforced routine misses to keep highlight clean
    include_dramatic_clutch_misses: bool = True # Keep dramatic rattle/miss in deciding Hill-Hill rack
    
    # Break shot window: 2.5s preparation + 5.5s ball scatter & cue action (~8.0s)
    break_shot_pre_peak_sec: float = 2.5
    break_shot_post_peak_sec: float = 5.5


@dataclass
class ScoreboardConfig:
    # Spec 4.1: Minimalist Dark Frosted Glass
    position: str = "top_left"       # 'top_left' or 'bottom_left'
    safe_margin_pct: float = 0.05    # 5% safe margin
    background_color: Tuple[int, int, int, int] = (18, 18, 22, 180)  # 70% black frosted
    border_color: Tuple[int, int, int, int] = (255, 255, 255, 80)     # 1px subtle white
    corner_radius_px: int = 6
    border_width_px: int = 1
    font_family: str = "sans-serif"
    hill_hill_badge_text: str = "HILL-HILL"
    final_badge_text: str = "FINAL"


@dataclass
class TimelineScriptConfig:
    # Spec 1 & 3: Overall Script & Target Durations
    target_duration_horizontal_sec: float = 240.0   # 3-6 mins (typical 4m00s)
    target_duration_shorts_sec: float = 55.0        # 45-60s
    intro_hook_duration_sec: float = 8.0            # 0:00 - 0:08
    camera_shake_intensity: float = 0.03            # 3% camera shake
    outro_duration_sec: float = 4.0                 # 3-5s outro


@dataclass
class EditorConfig:
    audio: AudioConfig = field(default_factory=AudioConfig)
    trimming: TrimmingConfig = field(default_factory=TrimmingConfig)
    scoreboard: ScoreboardConfig = field(default_factory=ScoreboardConfig)
    script: TimelineScriptConfig = field(default_factory=TimelineScriptConfig)
    video_format: VideoFormat = VideoFormat.HORIZONTAL_YOUTUBE
    target_fps: int = 30
    horizontal_resolution: Tuple[int, int] = (1920, 1080)
    vertical_resolution: Tuple[int, int] = (1080, 1920)
    enable_gpu: bool = False
