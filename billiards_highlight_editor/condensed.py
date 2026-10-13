"""
Full Match Condensed: cut a whole billiards match down to only the shots.

Pipeline (each stage caches to <project>/analysis/):
  roi    : preview the table ROI on one frame (set --table-roi if felt is not auto-detected)
  plan   : audio strike detection (+ video end-of-shot check) -> clips.json, racks.json, contact_sheet.jpg
  racks  : rebuild racks.json / contact sheet from (edited) clips.json
  score  : record the winner of every rack -> scoreboard timeline, drop show-match racks
  render : per-clip FFmpeg (GPU encoder) + scoreboard overlay -> concat -> loudnorm -> chapters.txt

Run:  python -m billiards_highlight_editor.condensed <plan|racks|score|render> --project <dir> ...
"""

import argparse
import bisect
import glob
import json
import os
import re
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field, fields, replace
from typing import Callable, Dict, Iterable, Iterator, List, NamedTuple, Optional, Sequence, Tuple

import numpy as np
from scipy import signal


# --------------------------------------------------------------------------- config

@dataclass
class CondensedConfig:
    # audio strike detection
    sample_rate: int = 22050
    band_low_hz: float = 1000.0
    band_high_hz: float = 8000.0
    hop_sec: float = 0.01
    peak_min_gap_sec: float = 0.15
    over_floor_db: float = 18.0          # a peak must stand this far above the local noise floor
    floor_percentile: float = 20.0
    floor_block_sec: float = 60.0
    quiet_before_sec: float = 1.5        # a cue strike has no other transient in the 1.5s before it
    # break detection
    break_level_percentile: float = 85.0
    break_gap_sec: float = 15.0          # fallback when the rack-cluster check fails
    break_min_cluster_balls: int = 9
    break_check_offset_sec: float = 0.8
    # rack-based break detection (needs rack_roi = the foot-spot area in source pixels, fixed camera)
    rack_roi: Optional[List[int]] = None
    rack_color_dist: float = 45.0        # a pixel counts as "ball" when this far from the median felt colour
    rack_min_fraction: float = 0.08      # share of ball pixels that means "rack is standing there"
    rack_break_ratio: float = 0.6        # break = rack share after the strike <= ratio * share before
    rack_check_percentile: float = 60.0  # only the loudest strikes are checked visually
    rack_ready_margin_sec: float = 6.0   # clips this close before the rack stands are racking noise
    # clip boundaries
    pre_roll_sec: float = 4.0            # keeps the aiming; was 2.0 (too short), value not yet verified on real footage
    break_pre_roll_sec: float = 4.5      # long enough to see the full 9-ball diamond
    tail_sec: float = 1.5                # was 1.0; the end of a shot was being cut too early
    merge_gap_sec: float = 1.5
    min_run_sec: float = 3.0             # was 0.8; a slow cue ball must still reach the target ball before a shot can end
    min_still_sec: float = 1.0           # was 0.5; the table must stay still this long before the shot is over
    max_clip_sec: float = 25.0
    # motion (ball velocity -> 0)
    motion_fps: float = 10.0
    motion_width: int = 480
    table_roi: Optional[List[int]] = None   # [x, y, w, h] in source pixels; set it when the felt is not auto-detected
    still_energy: float = 0.25           # % of ROI pixels changing; was 0.35. 0.15 made more clips hit max_clip_sec without ending any shot more precisely (trial, 10 min); re-check per camera
    min_motion_energy: float = 1.0       # below this peak the strike was not a real shot
    # missed-shot filter (--drop-misses): drop a single-shot clip only when the ball count did NOT go down
    miss_diff_min: float = 1.0           # median balls after - median balls before must be >= this (count went UP)
    miss_min_before: int = 2             # need at least this many balls seen before the shot to trust the count
    nine_window_sec: float = 45.0        # shots this close to the rack's last pot are always kept (the 9-ball)
    count_step_sec: float = 1.5
    count_samples: int = 5
    count_min_samples: int = 3
    count_occlusion_max: float = 1.0    # share of 'large blob' pixels above which a frame is ignored; 1.0 = off (the measure sits at 0.17-0.22 on every frame, even empty ones, so it cannot flag a person)
    # render
    width: int = 1920
    height: int = 1080
    fps: int = 30
    audio_fade_sec: float = 0.03         # click guard on edges that are NOT a real cut (clip continues from the previous one)
    join_video_fade_sec: float = 0.15    # short dip-to-black on both sides of a real cut; 0 = hard cut. The scoreboard is not faded
    join_audio_fade_sec: float = 0.20    # audio fade on both sides of a real cut; 0 = use audio_fade_sec
    target_lufs: float = -14.0
    handshake_sec: float = 20.0
    workers: int = 1
    zoom: float = 1.3                    # static punch-in on the table (fixed camera); 1.0 = off. Centred on table_roi, clamped inside the frame. 1.5 already cuts the cue/arm of a player standing beside the table
    cap_extend_window_sec: float = 15.0  # a shot cut by shot_cap_sec is extended while another strike follows within this many seconds (the next aim stays in the clip)
    audit_diff_px: int = 100             # audit: still cloth differs by at least this many full-res pixels (arms/hands at the cloth edge are ignored) across a cut -> something happened inside it
    audit_min_gap_sec: float = 3.0       # audit: shorter cuts are not checked
    motion_felt: bool = False            # measure motion only inside the cloth polygon (not rails, legs, people at the edge); motion mode turns it on
    felt_polygon: Optional[List[List[float]]] = None   # 4 corners [x,y] in source px: far-left, far-right, near-right, near-left; None = derived from table_roi
    motion_mode: bool = False            # no audio: a clip is every stretch of table activity, from motion_pre to motion_post (pre_roll_sec / tail_sec)
    move_energy: float = 0.4             # % of cloth pixels that STARTS an activity (a far, soft shot moves only 0.4-0.7 %; still level is <= 0.2)
    move_low_energy: float = 0.2         # an activity goes on while the energy stays >= this (slow rolling ball, a person at the table); move_energy only STARTS it
    move_smooth_sec: float = 0.3         # energy is averaged over this window before thresholding (removes single-frame flicker)
    move_gap_sec: float = 2.0            # the table must be still this long before the activity counts as over (the balls have stopped for good)
    min_move_sec: float = 0.4            # shorter bursts are noise unless they are strong ...
    min_move_peak: float = 1.0           # ... (peak energy at least this)
    onset_before_sec: float = 0.6        # ball-motion onset check: the table must be (nearly) still this long before the strike ...
    onset_after_sec: float = 0.8         # ... and motion must jump up within this long after it. Loud sounds from OTHER tables fail this
    min_onset_energy: float = 0.3        # % of ROI pixels changing right after the strike (a real shot seen: 0.46-1.5; other-table sound: <=0.2)
    min_onset_rise: float = 0.2          # ... and it must exceed the level before the strike by this much
    shot_cap_sec: float = 0.0            # >0: a shot never lasts longer than this after the strike (cuts walking around the table; 0 = off)
    room_tone: bool = False              # continuous quiet room-noise bed under the whole video (hides audio dips at the cuts)
    room_tone_db: float = -29.0          # RMS level of the bed in dBFS
    score_sfx: bool = True               # soft click on the frame the score jumps (9-ball drop)
    score_sfx_volume: float = 0.25       # peak level of the click (fraction of full scale)
    zoom_center: Optional[List[float]] = None   # [cx, cy] source pixels = middle of the whole table (rails included); None = centre of table_roi
    style: str = "swiss"                # scoreboard look: "swiss" (templates/swiss_style) | "classic" (ScoreboardEngine)


def config_from_dict(d: Dict) -> CondensedConfig:
    names = {f.name for f in fields(CondensedConfig)}
    return CondensedConfig(**{k: v for k, v in (d or {}).items() if k in names})


# --------------------------------------------------------------------------- audio

class Strike(NamedTuple):
    t: float
    db: float
    gap_before: float


def audio_envelope_db(audio: np.ndarray, sr: int, cfg: CondensedConfig) -> np.ndarray:
    """10 ms RMS envelope (dB) of the 1-8 kHz band where cue/ball clicks live."""
    sos = signal.butter(4, [cfg.band_low_hz, cfg.band_high_hz], btype="band", fs=sr, output="sos")
    band = signal.sosfiltfilt(sos, audio.astype(np.float32))
    hop = max(1, int(round(sr * cfg.hop_sec)))
    n = (len(band) // hop) * hop
    if n == 0:
        return np.array([], dtype=np.float32)
    rms = np.sqrt(np.mean(band[:n].reshape(-1, hop) ** 2, axis=1))
    return 20.0 * np.log10(np.maximum(rms, 1e-6))


def noise_floor_db(env_db: np.ndarray, cfg: CondensedConfig) -> np.ndarray:
    """Per-frame noise floor: low percentile of each block, so crowd noise changes do not shift the threshold globally."""
    block = max(1, int(cfg.floor_block_sec / cfg.hop_sec))
    out = np.empty_like(env_db)
    for i in range(0, len(env_db), block):
        out[i:i + block] = np.percentile(env_db[i:i + block], cfg.floor_percentile)
    return out


def detect_peaks(env_db: np.ndarray, cfg: CondensedConfig) -> List[Tuple[float, float]]:
    """All transients (t, dB): cue hits, ball clicks, cushions, pocket drops, rack noise."""
    if env_db.size == 0:
        return []
    height = noise_floor_db(env_db, cfg) + cfg.over_floor_db
    distance = max(1, int(round(cfg.peak_min_gap_sec / cfg.hop_sec)))
    idx, _ = signal.find_peaks(env_db, height=height, distance=distance)
    return [(float(i * cfg.hop_sec), float(env_db[i])) for i in idx]


def strike_candidates(peaks: Sequence[Tuple[float, float]], cfg: CondensedConfig) -> List[Strike]:
    """Quiet-before gate: keep a transient only if nothing else rang in the preceding quiet_before_sec.
    Follow-up clicks of the same shot (ball-ball, cushion, pocket) are therefore not new strikes."""
    strikes: List[Strike] = []
    prev = -1e9
    for t, db in peaks:
        gap = t - prev
        if gap >= cfg.quiet_before_sec:
            strikes.append(Strike(t, db, gap))
        prev = t
    return strikes


def _has_peak(sorted_times: Sequence[float], t0: float, t1: float) -> bool:
    i = bisect.bisect_left(sorted_times, t0)
    return i < len(sorted_times) and sorted_times[i] <= t1


def extract_audio(ffmpeg: str, path: str, sr: int, limit_sec: Optional[float] = None) -> np.ndarray:
    cmd = [ffmpeg, "-v", "error", "-i", path]
    if limit_sec:
        cmd += ["-t", f"{limit_sec:.3f}"]
    cmd += ["-vn", "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if res.returncode != 0:
        raise RuntimeError(f"audio extraction failed: {res.stderr.decode('utf-8', 'ignore')[-400:]}")
    return np.frombuffer(res.stdout, dtype=np.float32)


# --------------------------------------------------------------------------- clips

@dataclass
class Clip:
    source: int
    start: float
    end: float
    strike_t: float
    is_break: bool = False
    rack_check: str = ""          # "ok" | "review" for break clips
    peak_motion: float = 0.0
    capped: bool = False          # hit max_clip_sec without ball stillness (player walking in frame?)
    n_strikes: int = 1
    last_sound_t: float = 0.0     # last transient inside the clip: pocket-drop candidate
    skip: bool = False            # dropped by the missed-shot filter (kept in clips.json so it can be reviewed)
    skip_reason: str = ""


def has_ball_onset(samples: Sequence[Tuple[float, float]], strike_t: float, cfg: CondensedConfig) -> bool:
    """A cue strike on THIS table sets balls moving at once: the table was still before it and the motion jumps right after it.
    A loud sound from another table leaves our table unchanged. samples = (t, motion_energy) covering [strike-onset_before, strike+onset_after]."""
    if not cfg.min_onset_energy:
        return True
    before = [e for t, e in samples if strike_t - cfg.onset_before_sec <= t < strike_t - 0.1]
    after = [e for t, e in samples if strike_t - 0.05 <= t <= strike_t + cfg.onset_after_sec]
    if not after:
        return False
    b = sum(before) / len(before) if before else 0.0
    a = max(after)
    return a >= cfg.min_onset_energy and a - b >= cfg.min_onset_rise


def effective_cap_sec(strike_t: float, strike_times: Sequence[float], cfg: CondensedConfig) -> float:
    """Seconds after strike_t at which the shot budget runs out. Another strike that follows within cap_extend_window_sec
    of that point is a shot of the same visit to the table (the player was already aiming at it): the budget moves on to
    that strike, so the clip is not cut in the middle of the next aim."""
    cap = cfg.shot_cap_sec
    if not cap:
        return 0.0
    end = strike_t + cap
    for st in sorted(strike_times):
        if st <= strike_t:
            continue
        if st <= end + cfg.cap_extend_window_sec:
            end = max(end, st + cap)
        else:
            break
    return end - strike_t


def detect_shot_end(
    samples: Iterable[Tuple[float, float]],
    strike_t: float,
    audio_peak_times: Sequence[float],
    cfg: CondensedConfig,
    strike_times: Sequence[float] = (),
) -> Tuple[float, float, bool]:
    """Walk (t, motion_energy) samples after a strike; the shot ends when the table has been
    still for min_still_sec with no audio transient. Returns (end_t, peak_energy, capped)."""
    peak = 0.0
    still_since: Optional[float] = None
    last_t = strike_t
    cap_after = effective_cap_sec(strike_t, strike_times, cfg)
    for t, e in samples:
        last_t = t
        if t < strike_t:
            continue
        peak = max(peak, e)
        age = t - strike_t
        if age > cfg.max_clip_sec and not (cap_after and age <= cap_after):
            return t, peak, True
        if cap_after and age >= cap_after:                    # budget per shot: the rest is the player walking around
            return t, peak, False
        if age < cfg.min_run_sec:
            still_since = None
            continue
        if e <= cfg.still_energy and not _has_peak(audio_peak_times, t - 0.3, t):
            if still_since is None:
                still_since = t
            if t - still_since >= cfg.min_still_sec:
                return still_since, peak, False
        else:
            still_since = None
    return last_t, peak, False


def build_clips(
    strikes: Sequence[Strike],
    end_fn: Callable[[float], Tuple[float, float, bool]],
    cfg: CondensedConfig,
    source: int = 0,
    is_break_fn: Optional[Callable[[Strike], bool]] = None,
    interrupt_fn: Optional[Callable[[Strike], bool]] = None,
) -> List[Clip]:
    clips: List[Clip] = []
    busy_until = -1.0
    for s in strikes:
        if s.t < busy_until:                       # tail sound of a shot already being cut
            if not (interrupt_fn and interrupt_fn(s)):
                continue
            if clips:                              # a confirmed break inside a long "busy" window: cut the previous clip before it
                clips[-1].end = round(min(clips[-1].end, s.t - cfg.break_pre_roll_sec), 3)
                if clips[-1].end - clips[-1].start < cfg.min_run_sec:
                    clips.pop()
        end, peak, capped = end_fn(s.t)
        if peak < cfg.min_motion_energy:           # chalk tap, ball placed, talking: nothing moved
            continue
        busy_until = end                           # only a real shot makes the following sounds "its tail" (a rejected trigger must not hide the next shot)
        brk = bool(is_break_fn and is_break_fn(s))
        start = max(0.0, s.t - (cfg.break_pre_roll_sec if brk else cfg.pre_roll_sec))
        stop = end + cfg.tail_sec
        if clips and start - clips[-1].end < cfg.merge_gap_sec:   # run-out: one continuous clip
            c = clips[-1]
            c.start = min(c.start, start)
            c.end = max(c.end, stop)
            c.n_strikes += 1
            c.peak_motion = max(c.peak_motion, peak)
            c.capped = c.capped or capped
            c.is_break = c.is_break or brk
            if brk:
                c.strike_t = s.t
        else:
            clips.append(Clip(source, round(start, 3), round(stop, 3), round(s.t, 3),
                              is_break=brk, peak_motion=round(peak, 3), capped=capped))
    return clips


def annotate_last_sound(clips: List[Clip], peak_times: Sequence[float], cfg: CondensedConfig) -> None:
    for c in clips:
        lo = bisect.bisect_left(peak_times, c.strike_t)
        hi = bisect.bisect_right(peak_times, c.end - cfg.tail_sec * 0.5)
        c.last_sound_t = round(peak_times[hi - 1], 3) if hi > lo else c.strike_t


def rack_fraction(frame: np.ndarray, roi: Sequence[int], dist: float = 45.0) -> float:
    """Share of pixels in the foot-spot area that differ from the felt (median colour):
    ~0.13 with a standing rack, ~0.05 without (measured on the 1080p wide-angle clip)."""
    x, y, w, h = roi
    region = frame[y:y + h, x:x + w].astype(np.float32)
    if region.size == 0:
        return 0.0
    med = np.median(region.reshape(-1, 3), axis=0)
    return float((np.linalg.norm(region - med, axis=2) > dist).mean())


def drop_racking_clips(clips: List[Clip], ready_by_break: Dict[int, float], cfg: CondensedConfig) -> List[Clip]:
    """Remove the racking noise before each break: non-break clips of the same source that start
    within rack_ready_margin_sec of the moment the rack stands (or later)."""
    drop = set()
    for i, ready in ready_by_break.items():
        j = i - 1
        while (j >= 0 and not clips[j].is_break and clips[j].source == clips[i].source
               and clips[j].strike_t >= ready - cfg.rack_ready_margin_sec):
            drop.add(j)
            j -= 1
    return [c for k, c in enumerate(clips) if k not in drop]


# --------------------------------------------------------------------------- video

class VideoMotion:
    """Ball-motion energy sampled from the table felt of one source video (frame diff on a downscaled ROI)."""

    def __init__(self, path: str, cfg: CondensedConfig):
        import cv2
        from billiards_highlight_editor.motion_tracker import MotionTracker
        self.cv2 = cv2
        self.cfg = cfg
        self.path = path
        self.cap = cv2.VideoCapture(path)
        if not self.cap.isOpened():
            raise RuntimeError(f"cannot open video: {path}")
        self.src_w = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 1920)
        self.src_h = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 1080)
        self.fps = self.cap.get(cv2.CAP_PROP_FPS) or 30.0
        self.duration = (self.cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0) / self.fps
        self.tracker = MotionTracker()
        self.roi_full: Optional[Tuple[int, int, int, int]] = None
        self.roi_is_fallback = False
        self.scale = 1.0

    def frame_at(self, t: float):
        self.cap.set(self.cv2.CAP_PROP_POS_MSEC, max(0.0, t) * 1000.0)
        ok, frame = self.cap.read()
        return frame if ok else None

    def rack_fraction_at(self, t: float) -> float:
        frame = self.frame_at(t)
        return 0.0 if frame is None else rack_fraction(frame, self.cfg.rack_roi, self.cfg.rack_color_dist)

    def rack_ready_t(self, t_break: float, max_back_sec: float = 150.0) -> float:
        """Earliest time (walking back from the break) from which the rack stands continuously; tolerates 2 occluded samples."""
        ready, misses, t = t_break, 0, t_break - 1.0
        while t > max(0.0, t_break - max_back_sec):
            if self.rack_fraction_at(t) >= self.cfg.rack_min_fraction:
                ready, misses = t, 0
            else:
                misses += 1
                if misses > 2:
                    break
            t -= 1.0
        return ready

    def _ensure_roi(self, t: float):
        if self.roi_full is not None:
            return
        frame = self.frame_at(t)
        if frame is None:
            raise RuntimeError(f"cannot read frame at {t:.1f}s from {self.path}")
        if self.cfg.table_roi:
            self.roi_full = tuple(int(v) for v in self.cfg.table_roi)
        else:
            self.roi_full = self.tracker.detect_table_felt_roi(frame)
            fh, fw = frame.shape[:2]
            # detect_table_felt_roi falls back to the centre 70% when no green/blue felt is found
            self.roi_is_fallback = self.roi_full == (int(fw * 0.15), int(fh * 0.15), int(fw * 0.70), int(fh * 0.70))
        self.scale = self.cfg.motion_width / float(frame.shape[1])

    def table_roi(self, t: float) -> Tuple[int, int, int, int]:
        self._ensure_roi(t)
        return self.roi_full

    def samples(self, t0: float, t1: float) -> Iterator[Tuple[float, float]]:
        cv2 = self.cv2
        self._ensure_roi(t0)
        x, y, w, h = self.roi_full
        s = self.scale
        roi = (int(x * s), int(y * s), max(1, int(w * s)), max(1, int(h * s)))
        step = max(1, int(round(self.fps / self.cfg.motion_fps)))
        self.mask = None
        if self.cfg.motion_felt:                       # cloth polygon only, in the scaled frame
            poly = np.array(felt_polygon_for(self.cfg, self.roi_full), dtype=np.float32) * s
            m = np.zeros(small_shape(self), dtype=np.uint8)
            cv2.fillConvexPoly(m, poly.astype(np.int32), 255)
            self.mask = m
            self.mask_area = max(1, int(cv2.countNonZero(m)))
        self.cap.set(cv2.CAP_PROP_POS_MSEC, max(0.0, t0) * 1000.0)
        prev = None
        base = None
        i = 0
        while True:
            if not self.cap.grab():
                return
            if base is None:
                base = self.cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0
            t = base + i / self.fps
            if i % step == 0:
                ok, frame = self.cap.retrieve()
                if not ok:
                    return
                small = cv2.resize(frame, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
                gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
                if prev is not None:
                    if self.mask is not None:
                        yield t, self._masked_energy(prev, gray)
                    else:
                        yield t, self.tracker.compute_ball_motion_energy(prev, gray, roi)
                prev = gray
            i += 1
            if t > t1:
                return

    def _masked_energy(self, prev: np.ndarray, gray: np.ndarray) -> float:
        cv2 = self.cv2
        diff = cv2.absdiff(prev, gray)
        _, th = cv2.threshold(diff, 25, 255, cv2.THRESH_BINARY)
        return float(cv2.countNonZero(cv2.bitwise_and(th, self.mask))) / self.mask_area * 100.0

    def close(self):
        self.cap.release()


# cloth corners relative to table_roi, measured on the sample camera (ROI 620,520,740,290): far-left, far-right, near-right, near-left
FELT_REL = [(0.284, 0.097), (0.615, 0.097), (0.818, 0.717), (0.085, 0.717)]   # a few px outside the cloth edge so balls against a cushion still count


def felt_polygon_for(cfg: CondensedConfig, roi: Sequence[int]) -> List[List[float]]:
    if cfg.felt_polygon:
        return [list(map(float, p)) for p in cfg.felt_polygon]
    x, y, w, h = roi
    return [[x + fx * w, y + fy * h] for fx, fy in FELT_REL]


def small_shape(video: "VideoMotion") -> Tuple[int, int]:
    """(rows, cols) of the downscaled frame used for motion."""
    return (int(round(video.src_h * video.scale)), int(round(video.src_w * video.scale)))


def motion_timeline(video: "VideoMotion", cfg: CondensedConfig, limit_sec: Optional[float],
                    cache_path: Optional[str] = None, log: Callable[[str], None] = print) -> np.ndarray:
    """(t, energy) at motion_fps for the whole source (or the first limit_sec). Slow (decodes the video), so it is cached."""
    if cache_path and os.path.exists(cache_path):
        log(f"motion timeline from cache {os.path.basename(cache_path)}")
        return np.load(cache_path)
    rows = list(video.samples(0.0, limit_sec if limit_sec else 1e9))
    arr = np.array(rows, dtype=np.float64).reshape(-1, 2)
    if cache_path:
        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
        np.save(cache_path, arr)
    return arr


def clips_from_motion(timeline: np.ndarray, cfg: CondensedConfig, source: int = 0,
                      duration: Optional[float] = None) -> List[Clip]:
    """Audio-free segmentation on the cloth only. An activity needs one strong moment (energy >= move_energy), but it lasts as long
    as anything still changes on the cloth (energy >= move_low_energy: a slow ball, a player aiming or walking over the table).
    It is over only when the table has been completely still for move_gap_sec, so a ball that has not fully stopped is never cut.
    Each activity becomes [start - pre_roll_sec, end + tail_sec]; clips that overlap are one continuous clip.
    Movement that never reaches move_energy (someone passing at the edge) is not an activity."""
    if timeline.size == 0:
        return []
    t, e = timeline[:, 0], timeline[:, 1]
    dt = float(np.median(np.diff(t))) if len(t) > 1 else 0.1
    k = max(1, int(round(cfg.move_smooth_sec / dt)))
    es = np.convolve(e, np.ones(k) / k, mode="same") if k > 1 else e
    low = min(cfg.move_low_energy, cfg.move_energy)
    on = es >= low                                    # anything moving on the cloth: balls, but also a player
    runs: List[List[float]] = []                      # [start, end, peak]
    i = 0
    n = len(on)
    while i < n:
        if not on[i]:
            i += 1
            continue
        j = i
        while j + 1 < n and on[j + 1]:
            j += 1
        runs.append([float(t[i]), float(t[j]), float(e[i:j + 1].max())])
        i = j + 1
    merged: List[List[float]] = []
    for r in runs:
        if merged and r[0] - merged[-1][1] < cfg.move_gap_sec:
            merged[-1][1] = r[1]
            merged[-1][2] = max(merged[-1][2], r[2])
        else:
            merged.append(r)
    runs = [r for r in merged if r[2] >= cfg.move_energy and ((r[1] - r[0]) >= cfg.min_move_sec or r[2] >= cfg.min_move_peak)]
    clips: List[Clip] = []
    for a, b, peak in runs:
        start = max(0.0, a - cfg.pre_roll_sec)
        stop = b + cfg.tail_sec
        if duration:
            stop = min(stop, duration)
        if clips and start - clips[-1].end < cfg.merge_gap_sec:
            c = clips[-1]
            c.end = round(max(c.end, stop), 3)
            c.peak_motion = max(c.peak_motion, round(peak, 3))
            c.n_strikes += 1
            continue
        clips.append(Clip(source, round(start, 3), round(stop, 3), round(a, 3), peak_motion=round(peak, 3),
                          last_sound_t=round(b, 3)))
    return clips


def analyze_source(
    path: str,
    index: int,
    cfg: CondensedConfig,
    ffmpeg: str,
    limit_sec: Optional[float] = None,
    log: Callable[[str], None] = print,
    cache_dir: Optional[str] = None,
) -> List[Clip]:
    if cfg.motion_mode:
        cfg.motion_felt = True
        video = VideoMotion(path, cfg)
        try:
            video.table_roi(0.0)
            if video.roi_is_fallback:
                log(f"[{index}] WARNING: table felt not detected; pass --table-roi x,y,w,h (see `roi`)")
            cache = os.path.join(cache_dir, f"motion_felt_{index}_{int(limit_sec or 0)}.npy") if cache_dir else None
            line = motion_timeline(video, cfg, limit_sec, cache, log)
            total = (video.cap.get(video.cv2.CAP_PROP_FRAME_COUNT) or 0) / (video.fps or 30.0)
        finally:
            video.close()
        clips = clips_from_motion(line, cfg, index, limit_sec or total or None)
        log(f"[{index}] motion mode: {len(clips)} clips, {sum(c.end - c.start for c in clips) / 60:.1f} min")
        return clips
    log(f"[{index}] audio: {os.path.basename(path)}")
    audio = extract_audio(ffmpeg, path, cfg.sample_rate, limit_sec)
    env = audio_envelope_db(audio, cfg.sample_rate, cfg)
    peaks = detect_peaks(env, cfg)
    peak_times = [p[0] for p in peaks]
    strikes = strike_candidates(peaks, cfg)
    log(f"[{index}] {len(peaks)} transients -> {len(strikes)} strike candidates")
    if not strikes:
        return []

    video = VideoMotion(path, cfg)
    try:
        video.table_roi(strikes[0].t)
        if video.roi_is_fallback:
            log(f"[{index}] WARNING: table felt not detected, using the centre of the frame. "
                f"Motion will include players and background; pass --table-roi x,y,w,h (see `roi` command)")
        thr = float(np.percentile([s.db for s in strikes], cfg.break_level_percentile))
        rack_ok: Dict[float, bool] = {}

        check_thr = float(np.percentile([s.db for s in strikes], cfg.rack_check_percentile))
        rack_cache: Dict[float, bool] = {}

        def is_break_rack(s: Strike) -> bool:
            """Break = a rack was standing at the foot spot before the strike and is gone 2.5-3s after it."""
            if s.db < check_thr:
                return False
            if s.t not in rack_cache:
                before = max(video.rack_fraction_at(s.t - d) for d in (1.0, 0.5))
                after = min(video.rack_fraction_at(s.t + d) for d in (2.5, 3.0))
                rack_cache[s.t] = before >= cfg.rack_min_fraction and after <= before * cfg.rack_break_ratio
            return rack_cache[s.t]

        def is_break_audio(s: Strike) -> bool:
            if s.db < thr:
                return False
            ok = False
            frame = video.frame_at(s.t - cfg.break_check_offset_sec)
            if frame is not None:
                ok = video.tracker.detect_racked_cluster(
                    frame, video.table_roi(s.t), min_cluster_balls=cfg.break_min_cluster_balls)
            rack_ok[round(s.t, 3)] = ok
            return ok or s.gap_before >= cfg.break_gap_sec

        def end_fn(t: float):
            smp = list(video.samples(t - max(0.3, cfg.onset_before_sec), t + cfg.max_clip_sec + 2.0))
            end, peak, capped = detect_shot_end(smp, t, peak_times, cfg, strike_times)
            if not has_ball_onset(smp, t, cfg):       # sound from another table: nothing started moving on ours
                peak = 0.0
            return end, peak, capped

        strike_times = [st.t for st in strikes]
        if cfg.rack_roi:
            clips = build_clips(strikes, end_fn, cfg, source=index, is_break_fn=is_break_rack,
                                interrupt_fn=is_break_rack)
            for c in clips:
                if c.is_break:
                    c.rack_check = "rack-roi"
            ready = {i: video.rack_ready_t(c.strike_t) for i, c in enumerate(clips) if c.is_break}
            before_n = len(clips)
            clips = drop_racking_clips(clips, ready, cfg)
            if before_n != len(clips):
                log(f"[{index}] dropped {before_n - len(clips)} racking clips before breaks")
        else:
            log(f"[{index}] no --rack-roi: break detection is a loudness heuristic, expect false breaks")
            clips = build_clips(strikes, end_fn, cfg, source=index, is_break_fn=is_break_audio)
            for c in clips:
                if c.is_break:
                    c.rack_check = "ok" if rack_ok.get(round(c.strike_t, 3)) else "review"
        annotate_last_sound(clips, peak_times, cfg)
    finally:
        video.close()
    log(f"[{index}] {len(clips)} clips, {sum(c.is_break for c in clips)} breaks, "
        f"{sum(c.end - c.start for c in clips) / 60:.1f} min")
    return clips


# --------------------------------------------------------------------------- missed-shot filter

def felt_interior(table_roi: Sequence[int]) -> Tuple[int, int, int, int]:
    """Felt area inside the rails, derived from the table ROI (same proportions as the one used for the motion check)."""
    x, y, w, h = table_roi
    return int(x + 0.03 * w), int(y + 0.09 * h), int(0.94 * w), int(0.74 * h)


def count_balls(frame: np.ndarray, roi: Sequence[int], thr: float = 20.0) -> Tuple[int, float]:
    """(balls, occluded_share): compact blobs that differ from the local felt colour, and the share of the felt
    covered by large blobs (a player's arm or body)."""
    import cv2
    x, y, w, h = roi
    crop = frame[y:y + h, x:x + w]
    if crop.size == 0:
        return 0, 1.0
    lab = cv2.cvtColor(crop, cv2.COLOR_BGR2LAB).astype(np.float32)
    bg = cv2.cvtColor(cv2.medianBlur(crop, 51), cv2.COLOR_BGR2LAB).astype(np.float32)
    mask = (np.linalg.norm(lab - bg, axis=2) > thr).astype(np.uint8) * 255
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    n, _, st, _ = cv2.connectedComponentsWithStats(mask)
    balls, big_area = 0, 0
    for i in range(1, n):
        a, bw, bh = int(st[i, 4]), int(st[i, 2]), int(st[i, 3])
        if 90 <= a <= 420 and 0.6 < bw / max(1, bh) < 1.7 and a / float(bw * bh) > 0.55:
            balls += 1
        elif a > 900:
            big_area += a
    return balls, big_area / float(w * h)


def sample_times_before(clip_strike: float, floor: float, cfg: CondensedConfig) -> List[float]:
    out, t = [], clip_strike - 0.6
    while len(out) < cfg.count_samples and t > max(floor, clip_strike - 12.0):
        out.append(round(t, 2))
        t -= cfg.count_step_sec
    return out


def sample_times_after(clip_end: float, ceiling: float, cfg: CondensedConfig) -> List[float]:
    out, t = [], clip_end + 0.2
    while len(out) < cfg.count_samples and t < min(ceiling, clip_end + 12.0):
        out.append(round(t, 2))
        t += cfg.count_step_sec
    return out


def protected_clips(clips: Sequence[Clip], racks: Sequence[Dict], cfg: CondensedConfig) -> Dict[int, str]:
    """Clips the filter must never drop: breaks, run-outs (2+ strikes), capped clips, the rack's last clip and
    everything within nine_window_sec of the last pot (that is where the 9-ball is played)."""
    prot: Dict[int, str] = {}
    for r in racks:
        if not r.get("include"):
            continue
        for i in range(r["first_clip"], r["last_clip"] + 1):
            c = clips[i]
            if c.is_break:
                prot[i] = "break"
            elif c.n_strikes >= 2:
                prot[i] = "run-out"
            elif c.capped:
                prot[i] = "capped"
            elif i == r["last_clip"]:
                prot[i] = "last clip of the rack"
            elif c.source == r["win_source"] and c.end >= r["win_t"] - cfg.nine_window_sec:
                prot[i] = "9-ball window"
    return prot


def select_missed_clips(
    clips: Sequence[Clip],
    racks: Sequence[Dict],
    counts: Dict[int, Tuple[List[int], List[int]]],
    cfg: CondensedConfig,
) -> List[Dict]:
    """Clips to drop: single-shot, not protected, enough trustworthy count samples on both sides, and the median ball
    count went up by at least miss_diff_min. A pot lowers the count, so a rise means no ball left the table.
    Anything uncertain is kept."""
    prot = protected_clips(clips, racks, cfg)
    dropped = []
    for r in racks:
        if not r.get("include"):
            continue
        for i in range(r["first_clip"], r["last_clip"] + 1):
            if i in prot or i not in counts:
                continue
            before, after = counts[i]
            if len(before) < cfg.count_min_samples or len(after) < cfg.count_min_samples:
                continue
            mb, ma = float(np.median(before)), float(np.median(after))
            if mb >= cfg.miss_min_before and ma - mb >= cfg.miss_diff_min:
                dropped.append({"clip": i, "rack": r["rack"], "source": clips[i].source, "start": clips[i].start,
                                "end": clips[i].end, "strike_t": clips[i].strike_t, "balls_before": mb,
                                "balls_after": ma, "reason": f"ball count rose {mb:g} -> {ma:g}: no ball left the table"})
    return dropped


def measure_counts(project: str, sources: Sequence[str], clips: Sequence[Clip], racks: Sequence[Dict],
                   cfg: CondensedConfig, log: Callable[[str], None] = print) -> Dict[int, Tuple[List[int], List[int]]]:
    """Ball counts around every unprotected single-shot clip of the included racks."""
    import cv2
    roi = felt_interior(cfg.table_roi or [620, 520, 740, 290])
    prot = protected_clips(clips, racks, cfg)
    caps: Dict[int, "cv2.VideoCapture"] = {}
    counts: Dict[int, Tuple[List[int], List[int]]] = {}

    def frame(src: int, t: float):
        cap = caps.setdefault(src, cv2.VideoCapture(_abs(project, sources[src])))
        cap.set(cv2.CAP_PROP_POS_MSEC, max(0.0, t) * 1000.0)
        ok, f = cap.read()
        return f if ok else None

    def sample(src: int, times: Sequence[float]) -> List[int]:
        out = []
        for t in times:
            f = frame(src, t)
            if f is None:
                continue
            n, occ = count_balls(f, roi)
            if occ <= cfg.count_occlusion_max:
                out.append(n)
        return out

    todo = [(r, i) for r in racks if r.get("include") for i in range(r["first_clip"], r["last_clip"] + 1) if i not in prot]
    for k, (r, i) in enumerate(todo):
        c = clips[i]
        prev_end = clips[i - 1].end if i > 0 and clips[i - 1].source == c.source else 0.0
        nxt = clips[i + 1] if i + 1 < len(clips) and clips[i + 1].source == c.source else None
        ceiling = (nxt.strike_t - 2.0) if nxt else c.end + 12.0
        counts[i] = (sample(c.source, sample_times_before(c.strike_t, prev_end, cfg)),
                     sample(c.source, sample_times_after(c.end, ceiling, cfg)))
        if k % 10 == 0:
            log(f"  ball counts {k + 1}/{len(todo)}")
    for cap in caps.values():
        cap.release()
    return counts


def write_dropped_report(project: str, sources: Sequence[str], dropped: Sequence[Dict], cfg: CondensedConfig):
    """analysis/dropped_clips.json + analysis/dropped_sheet.jpg: before/after frames of every clip that was removed."""
    import cv2
    P = _paths(project)
    _save(os.path.join(P["analysis"], "dropped_clips.json"), {"dropped": list(dropped)})
    if not dropped:
        return
    caps: Dict[int, "cv2.VideoCapture"] = {}
    tiles = []

    def tile(src: int, t: float, text: str):
        cap = caps.setdefault(src, cv2.VideoCapture(_abs(project, sources[src])))
        cap.set(cv2.CAP_PROP_POS_MSEC, max(0.0, t) * 1000.0)
        ok, f = cap.read()
        img = cv2.resize(f[470:830, 500:1420], (400, 156)) if ok else np.zeros((156, 400, 3), np.uint8)
        cv2.putText(img, text, (4, 15), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 3)
        cv2.putText(img, text, (4, 15), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)
        return img

    for d in dropped:
        tiles.append(np.hstack([
            tile(d["source"], d["strike_t"] - 0.6, f"R{d['rack']} s{d['source']} {d['strike_t']:.0f}s before n={d['balls_before']:g}"),
            tile(d["source"], d["end"] + 0.4, f"after n={d['balls_after']:g}")]))
    for cap in caps.values():
        cap.release()
    if len(tiles) % 2:
        tiles.append(np.zeros_like(tiles[0]))
    sheet = np.vstack([np.hstack(tiles[i:i + 2]) for i in range(0, len(tiles), 2)])
    cv2.imwrite(os.path.join(P["analysis"], "dropped_sheet.jpg"), sheet)


# --------------------------------------------------------------------------- racks & score

def segment_racks(clips: Sequence[Clip]) -> List[Dict]:
    """A rack starts at each break clip and runs until the next one. Clips before the first break are warm-up."""
    racks: List[Dict] = []
    for i, c in enumerate(clips):
        if c.is_break:
            racks.append({"rack": len(racks) + 1, "first_clip": i, "last_clip": i})
        elif racks:
            racks[-1]["last_clip"] = i
    for r in racks:
        brk, last = clips[r["first_clip"]], clips[r["last_clip"]]
        r.update({
            "break_source": brk.source, "break_t": brk.strike_t, "rack_check": brk.rack_check or "unchecked",
            "win_source": last.source, "win_t": last.last_sound_t,
            "winner": None, "include": True,
        })
    return racks


def parse_winners(text: str) -> List[int]:
    out = []
    for tok in re.split(r"[,\s]+", text.strip()):
        if not tok:
            continue
        t = tok.upper().lstrip("P")
        if t not in ("1", "2"):
            raise ValueError(f"winner must be P1 or P2, got '{tok}'")
        out.append(int(t))
    return out


def apply_manual_breaks(
    clips: List[Clip],
    tokens: Sequence[str],
    cfg: CondensedConfig,
    end_fn: Optional[Callable[[int, float], Tuple[float, float, bool]]] = None,
) -> List[int]:
    """Override automatic break detection. Tokens are source-time seconds, "t" (source 0) or "src:t".
    Each token marks the clip containing it as a rack start and re-anchors the pre-roll on it.
    When no clip covers the time (the shot was missed by detection) a new clip is built with end_fn(src, t)
    -> (end, peak, capped); without end_fn the nearest clip is used."""
    for c in clips:
        c.is_break = False
        c.rack_check = ""
    for tok in tokens:
        src, _, t = tok.rpartition(":")
        src_i, t_s = (int(src) if src else 0), float(t)
        cand = [c for c in clips if c.source == src_i]
        if not cand:
            raise ValueError(f"no clips for source {src_i}")
        inside = [c for c in cand if c.start <= t_s <= c.end]
        if inside:
            c = inside[0]
            if c.start < t_s - cfg.break_pre_roll_sec - 0.5:
                # a long clip that started before the break: the earlier part belongs to the previous rack
                head_end = round(t_s - cfg.break_pre_roll_sec, 3)
                head = replace(c, end=head_end, is_break=False, rack_check="",
                               strike_t=min(c.strike_t, head_end - 0.5),
                               last_sound_t=min(c.last_sound_t, head_end - 0.5))
                clips.insert(clips.index(c), head)
        elif end_fn:
            end, peak, capped = end_fn(src_i, t_s)
            c = Clip(src_i, round(max(0.0, t_s - cfg.break_pre_roll_sec), 3), round(end + cfg.tail_sec, 3), t_s,
                     peak_motion=round(peak, 3), capped=capped, last_sound_t=t_s)
            clips.append(c)
            clips.sort(key=lambda x: (x.source, x.start))
            # footage already covered by the new clip must not be played twice
            k = clips.index(c)
            for nxt in clips[k + 1:]:
                if nxt.source != src_i:
                    break
                if nxt.start < c.end:
                    nxt.start = round(c.end, 3)
            clips[:] = [x for x in clips if x.end - x.start >= cfg.min_run_sec]
        else:
            c = min(cand, key=lambda x: min(abs(x.start - t_s), abs(x.end - t_s)))
        c.is_break, c.rack_check, c.strike_t = True, "manual", t_s
        c.start = round(max(0.0, t_s - cfg.break_pre_roll_sec), 3)
        c.end = max(c.end, round(t_s + 3.0, 3))
    return [i for i, c in enumerate(clips) if c.is_break]


def trim_before_breaks(
    clips: List[Clip],
    default_sec: float = 0.0,
    per_break: Optional[Dict[Tuple[int, float], float]] = None,
) -> List[Clip]:
    """Drop non-break clips of the same source that start within N seconds before a break (racking noise).
    N is per_break[(source, break_time)] when given, else default_sec."""
    per_break = per_break or {}
    breaks = [(c.source, c.strike_t, per_break.get((c.source, round(c.strike_t, 3)), default_sec))
              for c in clips if c.is_break]
    return [c for c in clips if c.is_break or not any(
        src == c.source and 0 <= t - c.strike_t < sec for src, t, sec in breaks)]


def parse_break_tokens(text: str) -> Tuple[List[str], Dict[Tuple[int, float], float]]:
    """"31.9,497.3/20,1:88.0/46" -> (["31.9", "497.3", "1:88.0"], {(0, 497.3): 20.0, (1, 88.0): 46.0}).
    The optional /N says racking noise starts N seconds before that break (clips from there on are dropped)."""
    tokens, trims = [], {}
    for raw in re.split(r"[,\s]+", text.strip()):
        if not raw:
            continue
        body, _, trim = raw.partition("/")
        src, _, t = body.rpartition(":")
        tokens.append(body)
        if trim:
            trims[(int(src) if src else 0, round(float(t), 3))] = float(trim)
    return tokens, trims


def apply_manual_wins(racks: List[Dict], clips: List[Clip], tokens: Sequence[str],
                      cfg: Optional[CondensedConfig] = None) -> None:
    """Set the moment the 9-ball drops for each rack, in rack order.
    Tokens: "t", "src:t", or with a cut point "t/e" / "src:t/e": the last clip is trimmed to end at e (source time),
    which removes the racking that follows the last shot. Without /e the clip ends at t + tail_sec.
    The clip holding t becomes the rack's last clip, so every later clip of that rack is dropped."""
    cfg = cfg or CondensedConfig()
    if len(tokens) != len(racks):
        raise ValueError(f"{len(tokens)} win times given for {len(racks)} racks")
    for n, (r, tok) in enumerate(zip(racks, tokens)):
        body, _, cut = tok.partition("/")
        src, _, t = body.rpartition(":")
        src_i, t_s = (int(src) if src else 0), float(t)
        hi = racks[n + 1]["first_clip"] if n + 1 < len(racks) else len(clips)
        rng = [i for i in range(r["first_clip"], hi) if clips[i].source == src_i]
        if not rng:
            raise ValueError(f"rack {r['rack']}: no clip in source {src_i}")
        inside = [i for i in rng if clips[i].start <= t_s <= clips[i].end]
        before = [i for i in rng if clips[i].start <= t_s]
        r["last_clip"] = inside[0] if inside else (before[-1] if before else rng[0])
        r["win_source"], r["win_t"] = src_i, t_s
        last = clips[r["last_clip"]]
        end = float(cut) if cut else t_s + cfg.tail_sec
        if last.start < end < last.end:
            last.end = round(end, 3)
        elif end > last.end and last.start <= t_s:
            last.end = round(end, 3)           # detection ended the clip before the last shot: extend it


def match_state(s1: int, s2: int, race_to: int) -> str:
    if max(s1, s2) >= race_to:
        return "FINAL"
    if s1 == race_to - 1 and s2 == race_to - 1:
        return "HILL-HILL"
    if max(s1, s2) == race_to - 1:
        return "GAME_POINT"
    return "NORMAL"


def apply_winners(racks: List[Dict], winners: Sequence[int], race_to: int) -> List[str]:
    """Assign winners in rack order; racks after the match is decided (show matches) are excluded."""
    warnings: List[str] = []
    if len(winners) > len(racks):
        raise ValueError(f"{len(winners)} winners given but only {len(racks)} racks detected")
    s1 = s2 = 0
    for i, r in enumerate(racks):
        if i < len(winners) and max(s1, s2) < race_to:
            r["winner"] = winners[i]
            r["include"] = True
            s1 += winners[i] == 1
            s2 += winners[i] == 2
            r["score_after"] = [s1, s2]
        else:
            r["winner"] = None
            r["include"] = False
            r.pop("score_after", None)
    if max(s1, s2) < race_to:
        warnings.append(f"race to {race_to} not reached ({s1}-{s2}); more racks may be missing")
    if len(winners) > sum(r["include"] for r in racks):
        warnings.append("winners given after the match was already decided were ignored")
    return warnings


# --------------------------------------------------------------------------- render plan

@dataclass
class RenderItem:
    source: int
    start: float
    end: float
    rack: int
    before: Tuple[int, int]
    after: Optional[Tuple[int, int]] = None
    switch_local: Optional[float] = None   # seconds into the clip when the 9-ball drops
    clip: int = -1                         # index in clips.json (lets `audit --restore` extend the clip)
    rack_start: Optional[Tuple[int, int]] = None   # score when the rack began (drives the HILL-HILL / MATCH POINT label)
    join_in: bool = True                   # a real cut precedes this clip (fade in); False when it continues the previous clip
    join_out: bool = True                  # a real cut follows this clip (fade out)


def build_render_plan(
    clips: Sequence[Clip],
    racks: Sequence[Dict],
    cfg: CondensedConfig,
    durations: Optional[Dict[int, float]] = None,
) -> List[RenderItem]:
    included = [r for r in racks if r.get("include")]
    missing = [r["rack"] for r in included if r.get("winner") not in (1, 2)]
    if missing:
        raise ValueError(f"racks without winner: {missing} (run `score` or set include=false)")
    items: List[RenderItem] = []
    s1 = s2 = 0
    for n, r in enumerate(included):
        a1, a2 = s1 + (r["winner"] == 1), s2 + (r["winner"] == 2)
        first, last = r["first_clip"], r["last_clip"]
        win_idx = last
        for i in range(first, last + 1):
            c = clips[i]
            if c.source == r["win_source"] and c.start <= r["win_t"] <= c.end:
                win_idx = i
        for i in range(first, last + 1):
            c = clips[i]
            if c.skip and i != win_idx and i != last:
                continue
            end = c.end
            if n == len(included) - 1 and i == last and durations:
                end = min(end + cfg.handshake_sec, durations.get(c.source, end + cfg.handshake_sec))
            if i < win_idx:
                items.append(RenderItem(c.source, c.start, end, r["rack"], (s1, s2), rack_start=(s1, s2), clip=i))
            elif i == win_idx:
                local = min(max(r["win_t"] - c.start, 0.1), max(0.1, end - c.start - 0.1))
                items.append(RenderItem(c.source, c.start, end, r["rack"], (s1, s2), (a1, a2), round(local, 3),
                                        rack_start=(s1, s2), clip=i))
            else:
                items.append(RenderItem(c.source, c.start, end, r["rack"], (a1, a2), rack_start=(s1, s2), clip=i))
        s1, s2 = a1, a2
    for prev, cur in zip(items, items[1:]):
        if prev.source == cur.source and abs(cur.start - prev.end) <= 0.05:   # same footage continues: no cut, no fade
            prev.join_out = False
            cur.join_in = False
    return items


def format_timestamp(sec: float) -> str:
    sec = int(round(sec))
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def build_chapters(items: Sequence[RenderItem], p1: str, p2: str, intro_sec: float = 0.0,
                  outro_sec: float = 0.0, separate_cards: bool = False) -> str:
    """YouTube chapter list from the output timeline, one line per rack.
    By default the intro belongs to the first rack chapter (which starts at 0:00) and the outro to the last one,
    because a 4-6 s chapter is shorter than the 10 s minimum YouTube is believed to require [unverified].
    separate_cards=True adds "0:00 Intro" and a closing "Kết quả" line instead."""
    lines, t, cur = [], float(intro_sec), None
    if intro_sec > 0 and separate_cards:
        lines.append(f"{format_timestamp(0)} Intro")
    last_item_of_rack: Dict[int, RenderItem] = {}
    for it in items:
        last_item_of_rack[it.rack] = it
    for it in items:
        if it.rack != cur:
            cur = it.rack
            fin = last_item_of_rack[cur]
            a = fin.after or fin.before
            stamp = 0.0 if (not lines and not separate_cards) else t
            lines.append(f"{format_timestamp(stamp)} Ván {cur}: {p1} {a[0]} - {a[1]} {p2}")
        t += it.end - it.start
    if outro_sec > 0 and separate_cards:
        lines.append(f"{format_timestamp(t)} Kết quả")
    return "\n".join(lines) + "\n"


def final_result(racks: Sequence[Dict]) -> Optional[Tuple[int, int, Optional[int]]]:
    """(score1, score2, winner) after the last included rack, from racks.json; None when no rack has a score."""
    inc = [r for r in racks if r.get("include") and r.get("score_after")]
    if not inc:
        return None
    last = inc[-1]
    return int(last["score_after"][0]), int(last["score_after"][1]), last.get("winner")


# --------------------------------------------------------------------------- ffmpeg

def pick_encoder_args() -> List[str]:
    from billiards_highlight_editor.hardware_profiler import HardwareProfiler
    prof = HardwareProfiler().profile_and_optimize()
    if prof.selected_encoder == "h264_nvenc":
        return ["-c:v", "h264_nvenc", "-preset", "p4", "-rc", "vbr", "-cq", "23", "-b:v", "0", "-profile:v", "high"]
    if prof.selected_encoder == "libx264":
        return ["-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-profile:v", "high"]
    return list(prof.ffmpeg_encoder_args)


def zoom_crop(cfg: CondensedConfig) -> str:
    """ffmpeg crop that punches in on the table by cfg.zoom, centred on table_roi (source pixels) and kept inside the frame.
    Empty string when zoom <= 1. Works for any source size: the crop size is iw/zoom x ih/zoom (same aspect ratio)."""
    z = cfg.zoom
    if not z or z <= 1.0:
        return ""
    if cfg.zoom_center:
        cx, cy = cfg.zoom_center
    elif cfg.table_roi:
        x, y, w, h = cfg.table_roi
        cx, cy = x + w / 2.0, y + h / 2.0
    else:
        return f"crop=w=trunc(iw/{z:.3f}/2)*2:h=trunc(ih/{z:.3f}/2)*2,"
    c ="\\,"                                  # escaped comma inside a filter option
    return (f"crop=w=trunc(iw/{z:.3f}/2)*2:h=trunc(ih/{z:.3f}/2)*2:"
            f"x=clip({cx:.1f}-iw/{z:.3f}/2{c}0{c}iw-iw/{z:.3f}):y=clip({cy:.1f}-ih/{z:.3f}/2{c}0{c}ih-ih/{z:.3f}),")


def clip_command(
    ffmpeg: str,
    enc_args: Sequence[str],
    item: RenderItem,
    src_path: str,
    png_before: str,
    png_after: Optional[str],
    out_path: str,
    cfg: CondensedConfig,
) -> List[str]:
    d = item.end - item.start
    W, H = cfg.width, cfg.height
    fv = min(cfg.join_video_fade_sec, d / 4.0)
    vfade = ""
    if fv > 0:                                   # fade only the picture under the scoreboard: the HUD stays solid and in place
        if item.join_in:
            vfade += f",fade=t=in:st=0:d={fv:.3f}"
        if item.join_out:
            vfade += f",fade=t=out:st={max(0.0, d - fv):.3f}:d={fv:.3f}"
    base = (f"[0:v]{zoom_crop(cfg)}scale={W}:{H}:force_original_aspect_ratio=decrease,"
            f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={cfg.fps}{vfade}[b]")
    if png_after and item.switch_local is not None:
        sw = f"{item.switch_local:.3f}"
        vf = (f"{base};[b][1:v]overlay=0:0:enable='lt(t,{sw})'[x];"
              f"[x][2:v]overlay=0:0:enable='gte(t,{sw})',format=yuv420p[v]")
    else:
        vf = f"{base};[b][1:v]overlay=0:0,format=yuv420p[v]"
    fa_join = min(cfg.join_audio_fade_sec or cfg.audio_fade_sec, d / 4.0)
    fa_in = fa_join if item.join_in else cfg.audio_fade_sec
    fa_out = fa_join if item.join_out else cfg.audio_fade_sec
    af = (f"[0:a]aresample=48000,afade=t=in:d={fa_in:.3f},"
          f"afade=t=out:st={max(0.0, d - fa_out):.3f}:d={fa_out:.3f}[a]")
    if cfg.score_sfx and item.switch_local is not None:     # click exactly when the scoreboard flips
        ms = int(round(item.switch_local * 1000))
        af = (f"[0:a]aresample=48000,afade=t=in:d={fa_in:.3f},"
              f"afade=t=out:st={max(0.0, d - fa_out):.3f}:d={fa_out:.3f},aformat=channel_layouts=stereo[a0];"
              f"sine=frequency=2000:sample_rate=48000:duration=0.09,afade=t=out:st=0.02:d=0.07,"
              f"volume={cfg.score_sfx_volume / 0.125:.3f},aformat=channel_layouts=stereo,adelay={ms}|{ms}[k];"
              f"[a0][k]amix=inputs=2:duration=first:normalize=0[a]")
    cmd = [ffmpeg, "-y", "-v", "error", "-ss", f"{item.start:.3f}", "-t", f"{d:.3f}", "-i", src_path,
           "-i", png_before]
    if png_after and item.switch_local is not None:
        cmd += ["-i", png_after]
    cmd += ["-filter_complex", f"{vf};{af}", "-map", "[v]", "-map", "[a]", *enc_args,
            "-g", str(cfg.fps * 2), "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
            "-ac", "2", out_path]      # always stereo: intro/outro (silent stereo) must match for concat -c copy
    return cmd


def pick_room_tone_window(audio: np.ndarray, sr: int, win_sec: float = 12.0) -> Tuple[float, float]:
    """Quietest steady stretch of the recording: the window whose loudest 1 s block is the lowest.
    Returns (start_sec, rms_db) of that window."""
    block = sr
    n = len(audio) // block
    if n < int(win_sec) + 1:
        return 0.0, -60.0
    rms = np.sqrt(np.mean(audio[:n * block].reshape(n, block).astype(np.float64) ** 2, axis=1)) + 1e-9
    k = int(win_sec)
    worst = np.array([rms[i:i + k].max() for i in range(n - k + 1)])
    i = int(np.argmin(worst))
    return float(i), float(20 * np.log10(np.sqrt(np.mean(rms[i:i + k] ** 2))))


def room_tone_command(ffmpeg: str, src_path: str, start: float, win_sec: float, gain_db: float, out_path: str) -> List[str]:
    """24 s seamless loop: the quiet window followed by itself reversed (no click at the loop point), set to the target level."""
    graph = (f"[0:a]atrim=0:{win_sec:.3f},asetpts=PTS-STARTPTS,aresample=48000,aformat=channel_layouts=stereo,asplit[a][b];"
             f"[b]areverse[r];[a][r]concat=n=2:v=0:a=1,volume={gain_db:.2f}dB[o]")
    return [ffmpeg, "-y", "-v", "error", "-ss", f"{start:.3f}", "-t", f"{win_sec:.3f}", "-i", src_path,
            "-filter_complex", graph, "-map", "[o]", "-c:a", "pcm_s16le", "-ar", "48000", out_path]


def concat_command(ffmpeg: str, list_path: str, out_path: str, cfg: CondensedConfig,
                   room_tone_path: Optional[str] = None) -> List[str]:
    if room_tone_path:      # the bed runs under the whole video; amix keeps the programme level (normalize=0)
        return [ffmpeg, "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", list_path,
                "-stream_loop", "-1", "-i", room_tone_path,
                "-filter_complex", f"[0:a][1:a]amix=inputs=2:duration=first:normalize=0,loudnorm=I={cfg.target_lufs}:TP=-1.5:LRA=11[a]",
                "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
                "-movflags", "+faststart", out_path]
    return _concat_plain(ffmpeg, list_path, out_path, cfg)


def _concat_plain(ffmpeg: str, list_path: str, out_path: str, cfg: CondensedConfig) -> List[str]:
    return [ffmpeg, "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", list_path,
            "-c:v", "copy", "-af", f"loudnorm=I={cfg.target_lufs}:TP=-1.5:LRA=11",
            "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart", out_path]


def _run(cmd: List[str]):
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if res.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {res.stderr.decode('utf-8', 'ignore')[-600:]}")


# --------------------------------------------------------------------------- project IO

def _ffmpeg_exe(override: Optional[str] = None) -> str:
    if override:
        return override
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def _paths(project: str) -> Dict[str, str]:
    return {
        "analysis": os.path.join(project, "analysis"),
        "clips": os.path.join(project, "analysis", "clips.json"),
        "clips_auto": os.path.join(project, "analysis", "clips_auto.json"),
        "racks": os.path.join(project, "analysis", "racks.json"),
        "sheet": os.path.join(project, "analysis", "contact_sheet.jpg"),
        "assets": os.path.join(project, "assets"),
        "temp": os.path.join(project, "temp", "condensed_clips"),
        "output": os.path.join(project, "output"),
    }


def _load(path: str) -> Dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _save(path: str, data: Dict):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _abs(project: str, p: str) -> str:
    return p if os.path.isabs(p) else os.path.join(project, p)


def _metadata(project: str, args) -> Tuple[str, str, int]:
    p1, p2, race_to = "P1", "P2", 7
    meta_path = os.path.join(project, "match_metadata.json")
    if os.path.exists(meta_path):
        m = _load(meta_path)
        p1 = m.get("players", {}).get("player_1", {}).get("name", p1)
        p2 = m.get("players", {}).get("player_2", {}).get("name", p2)
        digits = re.findall(r"\d+", str(m.get("format", "")))
        if digits:
            race_to = int(digits[-1])
    racks_path = _paths(project)["racks"]
    if os.path.exists(racks_path):            # keep what plan/score stored unless a flag overrides it
        prev = _load(racks_path)
        p1, p2, race_to = prev.get("p1", p1), prev.get("p2", p2), prev.get("race_to", race_to)
    return (getattr(args, "p1", None) or p1, getattr(args, "p2", None) or p2,
            getattr(args, "race_to", None) or race_to)


def make_contact_sheet(project: str, sources: Sequence[str], clips: Sequence[Clip], racks: Sequence[Dict],
                       cfg: CondensedConfig, out_path: str):
    """Per rack: frame before the break (9-ball diamond intact?), 3s after it (balls scattered?), and after the last sound (did 9 drop?)."""
    import cv2
    tile_w = 480
    tiles = []
    caps: Dict[int, "cv2.VideoCapture"] = {}

    def grab(src: int, t: float):
        cap = caps.setdefault(src, cv2.VideoCapture(_abs(project, sources[src])))
        cap.set(cv2.CAP_PROP_POS_MSEC, max(0.0, t) * 1000.0)
        ok, frame = cap.read()
        if not ok:
            return np.zeros((270, tile_w, 3), np.uint8)
        return cv2.resize(frame, (tile_w, int(frame.shape[0] * tile_w / frame.shape[1])))

    def label(img, text):
        cv2.putText(img, text, (8, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 0, 0), 4)
        cv2.putText(img, text, (8, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 1)
        return img

    for r in racks:
        a = label(grab(r["break_source"], r["break_t"] - cfg.break_check_offset_sec),
                  f"R{r['rack']} break {r['break_t']:.0f}s [{r['rack_check']}]")
        m = label(grab(r["break_source"], r["break_t"] + 3.0), f"R{r['rack']} +3s (balls scattered?)")
        b = label(grab(r["win_source"], r["win_t"] + 0.5), f"R{r['rack']} win_t {r['win_t']:.0f}s")
        tiles += [a, m, b]
    for cap in caps.values():
        cap.release()
    if not tiles:
        return
    h = max(t.shape[0] for t in tiles)
    tiles = [cv2.copyMakeBorder(t, 0, h - t.shape[0], 0, 0, cv2.BORDER_CONSTANT) for t in tiles]
    per_row = 3
    while len(tiles) % per_row:
        tiles.append(np.zeros_like(tiles[0]))
    rows = [np.hstack(tiles[i:i + per_row]) for i in range(0, len(tiles), per_row)]
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    cv2.imwrite(out_path, np.vstack(rows))


# --------------------------------------------------------------------------- commands

def _write_racks(project: str, args, clips: List[Clip], sources: List[str], cfg: CondensedConfig):
    P = _paths(project)
    p1, p2, race_to = _metadata(project, args)
    if getattr(args, "breaks", None):
        videos: Dict[int, VideoMotion] = {}

        def end_fn(src: int, t: float):
            if src not in videos:
                videos[src] = VideoMotion(_abs(project, sources[src]), cfg)
            v = videos[src]
            return detect_shot_end(v.samples(t - 0.3, t + cfg.max_clip_sec + 2.0), t, [], cfg)

        try:
            tokens, per_break = parse_break_tokens(args.breaks)
            apply_manual_breaks(clips, tokens, cfg, end_fn)
        finally:
            for v in videos.values():
                v.close()
        clips[:] = trim_before_breaks(clips, getattr(args, "trim_before_break", 0) or 0, per_break)
        data = _load(P["clips"])
        data["clips"] = [asdict(c) for c in clips]
        _save(P["clips"], data)
    racks = segment_racks(clips)
    if getattr(args, "wins", None):
        apply_manual_wins(racks, clips, re.split(r"[,\s]+", args.wins.strip()), cfg)
        data = _load(P["clips"])
        data["clips"] = [asdict(c) for c in clips]          # the trimmed last clips must reach `render`
        _save(P["clips"], data)
    warnings: List[str] = []
    winners_arg = getattr(args, "winners", None)
    if winners_arg:
        warnings = apply_winners(racks, parse_winners(winners_arg), race_to)
    for c in clips:                      # always start from "nothing dropped"; the filter below sets the flags again
        c.skip, c.skip_reason = False, ""
    if getattr(args, "drop_misses", False):
        print("missed-shot filter: counting balls before/after each single-shot clip ...")
        counts = measure_counts(project, sources, clips, racks, cfg)
        _save(os.path.join(P["analysis"], "ball_counts.json"),
              {str(i): {"before": b, "after": a, "strike_t": clips[i].strike_t, "source": clips[i].source}
               for i, (b, a) in counts.items()})          # kept so the thresholds can be tuned without recounting
        dropped = select_missed_clips(clips, racks, counts, cfg)
        for d in dropped:
            clips[d["clip"]].skip, clips[d["clip"]].skip_reason = True, d["reason"]
        write_dropped_report(project, sources, dropped, cfg)
        kept_min = sum(c.end - c.start for r in racks if r.get("include") for c in clips[r["first_clip"]:r["last_clip"] + 1]
                       if not c.skip) / 60.0
        print(f"missed-shot filter: dropped {len(dropped)} clips "
              f"({sum(d['end'] - d['start'] for d in dropped) / 60.0:.1f} min), kept {kept_min:.1f} min of play")
        print(f"  review: {os.path.join(P['analysis'], 'dropped_sheet.jpg')}")
    data = _load(P["clips"])
    data["clips"] = [asdict(c) for c in clips]
    _save(P["clips"], data)
    _save(P["racks"], {"p1": p1, "p2": p2, "race_to": race_to, "racks": racks})
    make_contact_sheet(project, sources, clips, racks, cfg, P["sheet"])
    print(f"{len(racks)} racks -> {P['racks']}")
    print(f"contact sheet  -> {P['sheet']}")
    print("Automatic break detection is a heuristic: confirm every rack on the contact sheet, "
          "or pass --breaks <seconds,...> with the real break times.")
    for w in warnings:
        print("warning:", w)


def cmd_plan(args):
    project = os.path.abspath(args.project)
    cfg = CondensedConfig()
    if getattr(args, "motion_mode", False):
        cfg.motion_mode = True
    for name in ("still_energy", "min_motion_energy", "pre_roll_sec", "tail_sec", "max_clip_sec",
                 "min_run_sec", "min_still_sec", "merge_gap_sec", "shot_cap_sec", "cap_extend_window_sec",
                 "min_onset_energy", "min_onset_rise", "move_energy", "move_low_energy", "move_gap_sec", "min_move_sec", "over_floor_db", "break_level_percentile"):
        v = getattr(args, name, None)
        if v is not None:
            setattr(cfg, name, v)
    if args.table_roi:
        cfg.table_roi = _parse_roi(args.table_roi)
    if args.rack_roi:
        cfg.rack_roi = _parse_roi(args.rack_roi)
    ffmpeg = _ffmpeg_exe(args.ffmpeg)
    P = _paths(project)
    clips: List[Clip] = []
    limits = [float(v) for v in str(args.limit_sec).split(",")] if args.limit_sec else [0.0]
    for i, src in enumerate(args.sources):
        lim = limits[i] if i < len(limits) else limits[-1]
        clips += analyze_source(_abs(project, src), i, cfg, ffmpeg, lim or None, cache_dir=P["analysis"])
    doc = {"sources": list(args.sources), "config": asdict(cfg), "clips": [asdict(c) for c in clips]}
    _save(P["clips"], doc)
    _save(P["clips_auto"], doc)          # pristine detection result: `racks` always starts from it
    total = sum(c.end - c.start for c in clips)
    print(f"{len(clips)} clips, condensed length {total / 60:.1f} min -> {P['clips']}")
    capped = sum(c.capped for c in clips)
    if capped:
        print(f"{capped} clips hit max_clip_sec without the table going still; check still_energy")
    _write_racks(project, args, clips, list(args.sources), cfg)


def _load_clips(project: str, pristine: bool = False) -> Tuple[List[str], CondensedConfig, List[Clip]]:
    P = _paths(project)
    data = _load(P["clips_auto"] if pristine and os.path.exists(P["clips_auto"]) else P["clips"])
    return data["sources"], config_from_dict(data.get("config")), [Clip(**c) for c in data["clips"]]


def _parse_roi(text: str) -> List[int]:
    vals = [int(float(v)) for v in text.split(",")]
    if len(vals) != 4:
        raise ValueError("--table-roi needs x,y,w,h")
    return vals


def cmd_roi(args):
    """Draw the table ROI on a frame so it can be checked by eye before a long analysis."""
    import cv2
    project = os.path.abspath(args.project)
    cfg = CondensedConfig()
    if args.table_roi:
        cfg.table_roi = _parse_roi(args.table_roi)
    video = VideoMotion(_abs(project, args.source), cfg)
    try:
        frame = video.frame_at(args.at)
        x, y, w, h = video.table_roi(args.at)
        cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 0, 255), max(2, frame.shape[1] // 320))
        poly = np.array(felt_polygon_for(cfg, [x, y, w, h]), dtype=np.int32)       # the cloth area motion mode measures
        cv2.polylines(frame, [poly], True, (0, 255, 0), max(2, frame.shape[1] // 320))
        if args.rack_roi:
            rx, ry, rw, rh = _parse_roi(args.rack_roi)
            cv2.rectangle(frame, (rx, ry), (rx + rw, ry + rh), (0, 255, 0), max(2, frame.shape[1] // 320))
        out = os.path.join(_paths(project)["analysis"], "roi_preview.jpg")
        os.makedirs(os.path.dirname(out), exist_ok=True)
        cv2.imwrite(out, cv2.resize(frame, (1280, int(frame.shape[0] * 1280 / frame.shape[1]))))
        print(f"roi {x},{y},{w},{h}{' (FALLBACK: felt not detected)' if video.roi_is_fallback else ''} -> {out}")
        zoom = getattr(args, "zoom", None)
        if zoom and zoom > 1.0:
            zc = CondensedConfig(zoom=zoom, table_roi=[x, y, w, h])
            if getattr(args, "zoom_center", None):
                zc.zoom_center = [float(v) for v in args.zoom_center.split(",")]
            zout = os.path.join(_paths(project)["analysis"], "zoom_preview.jpg")
            vf = zoom_crop(zc) + f"scale={zc.width}:{zc.height}"
            _run([_ffmpeg_exe(getattr(args, "ffmpeg", None)), "-y", "-v", "error", "-ss", f"{args.at:.3f}",
                  "-i", _abs(project, args.source), "-frames:v", "1", "-vf", vf, zout])
            print(f"zoom {zoom} centre {zc.zoom_center or [x + w / 2, y + h / 2]} -> {zout}")
    finally:
        video.close()


def snapshot_diff(a: np.ndarray, b: np.ndarray, mask: np.ndarray, thr: int = 30, edge_px: int = 8, group_px: int = 31) -> int:
    """Pixels inside mask that differ between two blurred grayscale snapshots of the (still) cloth. A ball that moved or was potted
    changes roughly 200-400 full-resolution pixels; compression noise changes none after the opening.
    A changed area that touches the edge of the cloth (within edge_px) is ignored as a whole: an arm, a hand or a cue always
    comes in over the rail, while a ball that moved sits inside the cloth. (A ball moved while lying against a cushion is missed.)"""
    import cv2
    th = cv2.threshold(cv2.absdiff(a, b), thr, 255, cv2.THRESH_BINARY)[1]
    th = cv2.morphologyEx(th, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    th = cv2.bitwise_and(th, mask)
    if edge_px > 0:
        inner = cv2.erode(mask, np.ones((2 * edge_px + 1, 2 * edge_px + 1), np.uint8))
        band = cv2.bitwise_and(mask, cv2.bitwise_not(inner))
        # group the fragments of one arm / hand / cue (they are broken up by the opening) before testing the edge
        grouped = cv2.dilate(th, np.ones((group_px, group_px), np.uint8))
        n, labels = cv2.connectedComponents(grouped)
        for lab in np.unique(labels[band > 0]):
            if lab != 0:
                th[labels == lab] = 0
    return int(cv2.countNonZero(th))


def audit_gaps(items: Sequence[RenderItem], grab: Callable[[int, float], Optional[np.ndarray]], mask: np.ndarray,
               cfg: CondensedConfig, intro_sec: float = 4.0) -> List[Dict]:
    """Check every cut of the render plan: is the cloth the same before and after it? If not, a shot (or a pot) may have been cut out.
    Cuts between two racks (the racking that was cut on purpose) are reported but never flagged."""
    out: List[Dict] = []
    t = intro_sec
    for a, b in zip(items, items[1:]):
        t += a.end - a.start
        if a.source == b.source and b.start - a.end < cfg.audit_min_gap_sec:
            continue
        ga, gb = grab(a.source, a.end - 0.2), grab(b.source, b.start + 0.2)
        px = snapshot_diff(ga, gb, mask) if ga is not None and gb is not None else -1
        rack_change = a.rack != b.rack
        out.append({"out_time": round(t, 1), "from": [a.source, round(a.end, 1)], "to": [b.source, round(b.start, 1)],
                    "rack": a.rack, "to_rack": b.rack, "clip_from": a.clip, "clip_to": b.clip, "gap_sec": round(b.start - a.end, 1) if a.source == b.source else None,
                    "diff_px": px, "rack_change": rack_change,
                    "flagged": bool(px >= cfg.audit_diff_px and not rack_change)})
    return out


def restore_cuts(clips: List[Clip], rows: Sequence[Dict], durations: Dict[int, float], max_gap_sec: float) -> List[Dict]:
    """Close every flagged cut by extending the clips around it so the footage inside the cut is kept (and, being contiguous,
    plays without a cut or a fade). A cut longer than max_gap_sec is left alone and reported. Returns what was done."""
    done: List[Dict] = []
    for r in rows:
        if not r["flagged"] or r.get("clip_from", -1) < 0 or r.get("clip_to", -1) < 0:
            continue
        a, b = clips[r["clip_from"]], clips[r["clip_to"]]
        if a.source == b.source:
            gap = b.start - a.end
            if gap <= 0:
                continue
            if gap > max_gap_sec:
                done.append({"out_time": r["out_time"], "restored_sec": 0.0, "skipped": f"gap {gap:.0f}s > {max_gap_sec:.0f}s"})
                continue
            a.end = round(b.start, 3)
            done.append({"out_time": r["out_time"], "restored_sec": round(gap, 1), "skipped": ""})
        else:                                              # cut between two files: keep the end of the first and the start of the second
            add = max(0.0, durations.get(a.source, a.end) - a.end) + b.start
            if add > max_gap_sec:
                done.append({"out_time": r["out_time"], "restored_sec": 0.0, "skipped": f"gap {add:.0f}s > {max_gap_sec:.0f}s"})
                continue
            a.end = round(durations.get(a.source, a.end), 3)
            b.start = 0.0
            done.append({"out_time": r["out_time"], "restored_sec": round(add, 1), "skipped": ""})
    return done


def cmd_audit(args):
    """Report the cuts after which the cloth looks different: candidates for a shot that was cut out."""
    import cv2
    project = os.path.abspath(args.project)
    P = _paths(project)
    sources, cfg, clips = _load_clips(project)
    defaults = CondensedConfig()                       # the audit thresholds are not read from the (older) saved config
    cfg.audit_diff_px = args.diff_px if args.diff_px is not None else defaults.audit_diff_px
    cfg.audit_min_gap_sec = args.min_gap if args.min_gap is not None else defaults.audit_min_gap_sec
    if getattr(args, "handshake", None) is not None:
        cfg.handshake_sec = args.handshake
    doc = _load(P["racks"])
    caps = {i: cv2.VideoCapture(_abs(project, s)) for i, s in enumerate(sources)}
    durations = {i: (c.get(cv2.CAP_PROP_FRAME_COUNT) or 0) / (c.get(cv2.CAP_PROP_FPS) or 30.0) for i, c in caps.items()}
    items = build_render_plan(clips, doc["racks"], cfg, durations)
    w0 = int(caps[0].get(cv2.CAP_PROP_FRAME_WIDTH) or 1920)
    h0 = int(caps[0].get(cv2.CAP_PROP_FRAME_HEIGHT) or 1080)
    roi = cfg.table_roi or [int(0.2 * w0), int(0.35 * h0), int(0.5 * w0), int(0.3 * h0)]
    poly = np.array(felt_polygon_for(cfg, roi), dtype=np.int32)
    mask = np.zeros((h0, w0), np.uint8)
    cv2.fillConvexPoly(mask, poly, 255)
    frames: Dict[Tuple[int, float], np.ndarray] = {}

    def grab(src: int, t: float):
        key = (src, round(t, 2))
        if key not in frames:
            caps[src].set(cv2.CAP_PROP_POS_MSEC, max(0.0, t) * 1000.0)
            ok, f = caps[src].read()
            frames[key] = f if ok else None
        f = frames[key]
        return None if f is None else cv2.GaussianBlur(cv2.cvtColor(f, cv2.COLOR_BGR2GRAY), (5, 5), 0)

    rows = audit_gaps(items, grab, mask, cfg, intro_sec=args.intro_sec)
    _save(os.path.join(P["analysis"], "gap_audit.json"), {"diff_px": cfg.audit_diff_px, "min_gap_sec": cfg.audit_min_gap_sec, "cuts": rows})
    flagged = [r for r in rows if r["flagged"]]
    if flagged:                                              # before / after picture of every flagged cut
        tiles = []
        for r in flagged:
            pair = []
            for (src, t), tag in (((r["from"][0], r["from"][1] - 0.2), "BEFORE"), ((r["to"][0], r["to"][1] + 0.2), "AFTER")):
                f = grab(src, t)
                img = frames.get((src, round(t, 2)))
                tile = cv2.resize(img[int(0.25 * h0):int(0.9 * h0), int(0.2 * w0):int(0.8 * w0)], (480, 280)) if img is not None else np.zeros((280, 480, 3), np.uint8)
                cv2.putText(tile, f"{tag} src{src} {t:.1f}s", (6, 20), 0, 0.55, (0, 255, 255), 2)
                pair.append(tile)
            both = np.hstack(pair)
            cv2.putText(both, f"cut @ video {int(r['out_time'] // 60)}:{r['out_time'] % 60:04.1f}  diff {r['diff_px']} px", (6, 270), 0, 0.6, (0, 255, 0), 2)
            tiles.append(both)
        cols = 2
        while len(tiles) % cols:
            tiles.append(np.zeros_like(tiles[0]))
        sheet = np.vstack([np.hstack(tiles[i:i + cols]) for i in range(0, len(tiles), cols)])
        cv2.imwrite(os.path.join(P["analysis"], "gap_audit_sheet.jpg"), sheet)
    print(f"{len(rows)} cuts checked (gap >= {cfg.audit_min_gap_sec:.0f}s or between files), {len(flagged)} flagged (>= {cfg.audit_diff_px} px, not rack changes)")
    for r in flagged:
        print(f"  video {int(r['out_time'] // 60)}:{r['out_time'] % 60:04.1f}  rack {r['rack']}  src{r['from'][0]} {r['from'][1]}s -> src{r['to'][0]} {r['to'][1]}s  diff {r['diff_px']} px")
    print(f"report -> {os.path.join(P['analysis'], 'gap_audit.json')}" + (f", pictures -> gap_audit_sheet.jpg" if flagged else ""))
    if getattr(args, "restore", False) and flagged:
        shutil.copyfile(P["clips"], os.path.join(P["analysis"], "clips_before_restore.json"))
        data = _load(P["clips"])
        done = restore_cuts(clips, rows, durations, args.restore_max)
        data["clips"] = [asdict(c) for c in clips]
        _save(P["clips"], data)
        added = sum(d["restored_sec"] for d in done)
        print(f"restored {sum(1 for d in done if not d['skipped'])} of {len(flagged)} flagged cuts, +{added:.0f} s of footage "
              f"(backup: clips_before_restore.json)")
        for d in done:
            if d["skipped"]:
                print(f"  NOT restored @ video {int(d['out_time'] // 60)}:{d['out_time'] % 60:04.1f}: {d['skipped']}")
        print("note: `racks` / `plan` rebuild clips.json from the detection and drop the restore; run `audit --restore` again after them, before `render`.")


def cmd_racks(args):
    project = os.path.abspath(args.project)
    sources, cfg, clips = _load_clips(project, pristine=True)
    _write_racks(project, args, clips, sources, cfg)


def cmd_score(args):
    project = os.path.abspath(args.project)
    P = _paths(project)
    doc = _load(P["racks"])
    race_to = args.race_to or doc["race_to"]
    doc["race_to"] = race_to
    for w in apply_winners(doc["racks"], parse_winners(args.winners), race_to):
        print("warning:", w)
    _save(P["racks"], doc)
    for r in doc["racks"]:
        print(f"R{r['rack']}: " + (f"P{r['winner']} -> {r['score_after'][0]}-{r['score_after'][1]}"
                                    if r["include"] else "excluded (after match end)"))


def _card_sec(disabled: bool, value: Optional[float], default: float) -> float:
    """Duration of an intro/outro card: 0 when switched off (--no-intro / --no-outro or a 0 duration)."""
    if disabled:
        return 0.0
    return default if value is None else max(0.0, float(value))


def cmd_render(args):
    project = os.path.abspath(args.project)
    P = _paths(project)
    sources, cfg, clips = _load_clips(project)
    cfg.workers = args.workers or cfg.workers
    if getattr(args, "handshake", None) is not None:
        cfg.handshake_sec = args.handshake
    cfg.style = getattr(args, "style", None) or cfg.style
    if getattr(args, "zoom", None) is not None:
        cfg.zoom = args.zoom
    if getattr(args, "zoom_center", None):
        cfg.zoom_center = [float(v) for v in args.zoom_center.split(",")]
    if getattr(args, "zoom", None) is not None or getattr(args, "zoom_center", None):
        data = _load(P["clips"])                       # remember the framing for the next render of this project
        data.setdefault("config", {}).update(zoom=cfg.zoom, zoom_center=cfg.zoom_center)
        _save(P["clips"], data)
    if getattr(args, "room_tone", False):
        cfg.room_tone = True
    if getattr(args, "room_tone_db", None) is not None:
        cfg.room_tone_db = args.room_tone_db
    if getattr(args, "no_score_sfx", False):
        cfg.score_sfx = False
    if getattr(args, "no_fade", False):
        cfg.join_video_fade_sec, cfg.join_audio_fade_sec = 0.0, 0.0
    if getattr(args, "fade_video", None) is not None:
        cfg.join_video_fade_sec = args.fade_video
    if getattr(args, "fade_audio", None) is not None:
        cfg.join_audio_fade_sec = args.fade_audio
    doc = _load(P["racks"])
    p1, p2, race_to = doc["p1"], doc["p2"], doc["race_to"]
    ffmpeg = _ffmpeg_exe(args.ffmpeg)

    import cv2
    durations = {}
    for i, s in enumerate(sources):
        cap = cv2.VideoCapture(_abs(project, s))
        durations[i] = (cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0) / (cap.get(cv2.CAP_PROP_FPS) or 30.0)
        cap.release()
    items = build_render_plan(clips, doc["racks"], cfg, durations)
    print(f"{len(items)} clips, {sum(i.end - i.start for i in items) / 60:.1f} min")

    if cfg.style not in ("swiss", "classic"):
        raise ValueError(f"unknown scoreboard style '{cfg.style}' (use swiss or classic)")
    engine = None
    if cfg.style == "classic":
        from billiards_highlight_editor.config import ScoreboardConfig
        from billiards_highlight_editor.models import MatchState
        from billiards_highlight_editor.scoreboard_engine import ScoreboardEngine
        engine = ScoreboardEngine(ScoreboardConfig())
    else:
        from billiards_highlight_editor.condensed_swiss import rack_label_for, render_swiss_scoreboard
    os.makedirs(P["assets"], exist_ok=True)
    pngs: Dict[Tuple[int, int, int], str] = {}

    def png_for(rack: int, score: Tuple[int, int], start: Optional[Tuple[int, int]] = None) -> str:
        key = (rack, score[0], score[1])
        if key not in pngs:
            path = os.path.join(P["assets"], f"scoreboard_condensed_r{rack}_{score[0]}_{score[1]}.png")
            if engine is None:   # swiss: full-frame RGBA, HUD pinned at the same spot in every PNG
                img = render_swiss_scoreboard(cfg.width, cfg.height, p1, p2, score[0], score[1], race_to,
                                              rack_label=rack_label_for(rack, score, race_to, start))
            else:
                state = MatchState(match_state(score[0], score[1], race_to))
                img = engine.render_scoreboard_overlay(cfg.width, cfg.height, p1, p2, score[0], score[1], state,
                                                       race_to=race_to, rack_label=f"VÁN {rack}")
            img.save(path)
            pngs[key] = path
        return pngs[key]

    shutil.rmtree(P["temp"], ignore_errors=True)
    os.makedirs(P["temp"], exist_ok=True)
    enc = pick_encoder_args()
    from billiards_highlight_editor import condensed_cards as cards
    intro_sec = _card_sec(getattr(args, "no_intro", False), getattr(args, "intro_sec", None), 4.0)
    outro_sec = _card_sec(getattr(args, "no_outro", False), getattr(args, "outro_sec", None), 6.0)
    result = final_result(doc["racks"])
    if outro_sec > 0 and result is None:
        print("warning: no scored rack in racks.json, outro skipped")
        outro_sec = 0.0
    jobs = []
    if intro_sec > 0:
        png = os.path.join(P["assets"], "intro_card_condensed.png")
        cards.render_intro_card(p1, p2, race_to, venue=(getattr(args, "venue", None) or ""),
                                width=cfg.width, height=cfg.height).save(png)
        out = os.path.join(P["temp"], "intro.mp4")
        jobs.append((len(jobs), cards.card_clip_command(ffmpeg, enc, png, out, intro_sec, cfg), out))
    for it in items:
        out = os.path.join(P["temp"], f"clip_{len(jobs):04d}.mp4")
        cmd = clip_command(ffmpeg, enc, it, _abs(project, sources[it.source]), png_for(it.rack, it.before, it.rack_start),
                           png_for(it.rack, it.after, it.rack_start) if it.after else None, out, cfg)
        jobs.append((len(jobs), cmd, out))
    if outro_sec > 0:
        s1, s2, winner = result
        png = os.path.join(P["assets"], "outro_card_condensed.png")
        cards.render_outro_card(p1, p2, s1, s2, race_to, winner=winner, width=cfg.width,
                                height=cfg.height).save(png)
        out = os.path.join(P["temp"], "outro.mp4")
        jobs.append((len(jobs), cards.card_clip_command(ffmpeg, enc, png, out, outro_sec, cfg), out))

    def run(job):
        n, cmd, _ = job
        _run(cmd)
        if n % 10 == 0:
            print(f"  clip {n + 1}/{len(jobs)}", flush=True)

    if cfg.workers > 1:
        with ThreadPoolExecutor(cfg.workers) as ex:
            list(ex.map(run, jobs))
    else:
        for j in jobs:
            run(j)

    list_path = os.path.join(P["temp"], "list.txt")
    with open(list_path, "w", encoding="utf-8") as f:
        for _, _, out in jobs:
            f.write("file '" + out.replace("\\", "/").replace("'", "'\\''") + "'\n")
    os.makedirs(P["output"], exist_ok=True)
    safe = lambda s: re.sub(r"[^\w\-]+", "", s.replace(" ", ""))
    out_name = args.out or f"Condensed_RaceTo{race_to}_{safe(p1)}_vs_{safe(p2)}_Full.mp4"
    out_path = os.path.join(P["output"], out_name)
    bed = None
    if cfg.room_tone:
        sr = 16000
        a = extract_audio(ffmpeg, _abs(project, sources[0]), sr)
        t0, rms_db = pick_room_tone_window(a, sr)
        bed = os.path.join(P["temp"], "room_tone.wav")
        _run(room_tone_command(ffmpeg, _abs(project, sources[0]), t0, 12.0, cfg.room_tone_db - rms_db, bed))
        print(f"room tone from {t0:.0f}s of source 0 ({rms_db:.1f} dBFS) -> {cfg.room_tone_db:.0f} dBFS")
    _run(concat_command(ffmpeg, list_path, out_path, cfg, bed))
    chapters = os.path.join(P["output"], "chapters.txt" if not args.out
                            else os.path.splitext(os.path.basename(args.out))[0] + "_chapters.txt")
    with open(chapters, "w", encoding="utf-8") as f:
        f.write(build_chapters(items, p1, p2, intro_sec, outro_sec))
    if not args.keep_temp:
        shutil.rmtree(P["temp"], ignore_errors=True)
    print(f"video    -> {out_path} ({os.path.getsize(out_path) / 1e6:.0f} MB)")
    print(f"chapters -> {chapters}")
    if not getattr(args, "no_youtube", False):
        write_youtube_files(project, args, p1, p2, race_to, doc["racks"], build_chapters(items, p1, p2, intro_sec, outro_sec),
                            out_path)


def write_youtube_files(project: str, args, p1: str, p2: str, race_to: int, racks: Sequence[Dict],
                        chapters_text: str, video_path: Optional[str]) -> Tuple[str, str]:
    """Write output/youtube_metadata.md (all fields) and output/youtube_description.txt (paste-ready)."""
    from billiards_highlight_editor import condensed_seo as seo
    from datetime import date as _date
    P = _paths(project)
    result = final_result(racks)
    duration = None
    if video_path and os.path.exists(video_path):
        import cv2
        cap = cv2.VideoCapture(video_path)
        frames, fps = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0, cap.get(cv2.CAP_PROP_FPS) or 0
        cap.release()
        duration = frames / fps / 60.0 if fps else None
    played = None
    if getattr(args, "date", None):
        played = _date.fromisoformat(args.date)
    else:
        played = seo.parse_date_from_project_name(os.path.basename(os.path.normpath(project)))
    facts = seo.MatchFacts(
        p1=p1, p2=p2, race_to=race_to,
        score=(result[0], result[1]) if result else None,
        winner=result[2] if result and result[0] != result[1] and max(result[0], result[1]) >= race_to else None,
        chapters=chapters_text, duration_min=duration, played_on=played,
        venue=getattr(args, "venue", None) or "", tournament=getattr(args, "tournament", None) or "",
        channel=getattr(args, "channel", None) or "")
    meta = seo.build_youtube_metadata(facts)
    os.makedirs(P["output"], exist_ok=True)
    md_path = os.path.join(P["output"], "youtube_metadata.md")
    txt_path = os.path.join(P["output"], "youtube_description.txt")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(seo.to_markdown(meta, seo.missing_facts(facts)))
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(str(meta["description"]))
    print(f"title    -> {meta['title']} ({len(str(meta['title']))} chars)")
    print(f"youtube  -> {md_path}")
    return md_path, txt_path


def cmd_seo(args):
    """Regenerate the YouTube title/description from the files of an already rendered project."""
    project = os.path.abspath(args.project)
    P = _paths(project)
    doc = _load(P["racks"])
    chapters_path = os.path.join(P["output"], "chapters.txt")
    chapters_text = open(chapters_path, encoding="utf-8").read() if os.path.exists(chapters_path) else ""
    video = args.video
    if video:
        video = _abs(project, video)
    else:
        found = sorted(glob.glob(os.path.join(P["output"], "Condensed_*.mp4")), key=os.path.getmtime)
        video = found[-1] if found else None
    write_youtube_files(project, args, doc["p1"], doc["p2"], doc["race_to"], doc["racks"], chapters_text, video)


def main(argv: Optional[Sequence[str]] = None):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser(prog="condensed", description="Full Match Condensed for billiards")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(p):
        p.add_argument("--project", required=True, help="projects/<date>_<P1>_vs_<P2>")
        p.add_argument("--ffmpeg")

    p = sub.add_parser("plan", help="detect shots, clips and racks")
    common(p)
    p.add_argument("--sources", nargs="+", required=True, help="source videos IN MATCH ORDER (relative to project)")
    p.add_argument("--p1"); p.add_argument("--p2"); p.add_argument("--race-to", type=int)
    p.add_argument("--winners", help="e.g. P1,P1,P2,... (optional, can be given later with `score`)")
    p.add_argument("--limit-sec", help="analyse only the first N seconds; one value for all sources or one per source, 0 = whole file (e.g. 0,60)")
    p.add_argument("--table-roi", help="x,y,w,h of the table felt in source pixels")
    p.add_argument("--rack-roi", help="x,y,w,h of the foot-spot area where the 9-ball rack stands (enables visual break detection)")
    p.add_argument("--breaks", help="real break times in source seconds, e.g. 18.8,590.2 or 1:35.0 (source:seconds); add /N to drop clips starting N s before that break, e.g. 590.2/20")
    p.add_argument("--wins", help="time the 9-ball drops in each rack, in rack order (same format as --breaks); add /E to cut the last clip at source time E, e.g. 448.5/450")
    p.add_argument("--drop-misses", dest="drop_misses", action="store_true",
                   help="experimental: drop single-shot clips where the ball count rose (no pot); keeps breaks, run-outs and the 9-ball window")
    p.add_argument("--trim-before-break", dest="trim_before_break", type=float, default=0.0,
                   help="with --breaks: drop clips starting this many seconds before each break (racking noise)")
    p.add_argument("--still-energy", dest="still_energy", type=float)
    p.add_argument("--min-motion", dest="min_motion_energy", type=float)
    p.add_argument("--pre-roll", dest="pre_roll_sec", type=float)
    p.add_argument("--tail", dest="tail_sec", type=float)
    p.add_argument("--max-clip", dest="max_clip_sec", type=float)
    p.add_argument("--min-run", dest="min_run_sec", type=float)
    p.add_argument("--min-still", dest="min_still_sec", type=float)
    p.add_argument("--merge-gap", dest="merge_gap_sec", type=float)
    p.add_argument("--over-floor", dest="over_floor_db", type=float, help="a strike must stand this many dB above the local noise floor (default 18); lower = more sensitive, more false strikes")
    p.add_argument("--cap-extend", dest="cap_extend_window_sec", type=float, help="extend a capped shot while another strike follows within N s (default 15)")
    p.add_argument("--motion", dest="motion_mode", action="store_true", help="NO audio: segment by table activity only (3 s before / 2 s after, via --pre-roll / --tail)")
    p.add_argument("--move-energy", dest="move_energy", type=float, help="motion mode: %% of cloth pixels changing that STARTS an activity (default 0.4)")
    p.add_argument("--move-low", dest="move_low_energy", type=float, help="motion mode: the activity goes on while energy stays >= this (default 0.2)")
    p.add_argument("--move-gap", dest="move_gap_sec", type=float, help="motion mode: the table must be still this long before the activity is over (default 2.0)")
    p.add_argument("--min-move", dest="min_move_sec", type=float, help="motion mode: shorter bursts are dropped unless strong (default 0.4)")
    p.add_argument("--min-onset", dest="min_onset_energy", type=float, help="ball-motion onset needed right after a strike (default 0.3); 0 = off")
    p.add_argument("--min-onset-rise", dest="min_onset_rise", type=float, help="onset must exceed the pre-strike level by this much (default 0.2)")
    p.add_argument("--shot-cap", dest="shot_cap_sec", type=float, help="max seconds a shot lasts after the strike (0 = off); cuts people walking around the table")
    p.add_argument("--break-percentile", dest="break_level_percentile", type=float)
    p.set_defaults(fn=cmd_plan)

    p = sub.add_parser("roi", help="preview the table ROI on one frame")
    common(p)
    p.add_argument("--source", required=True)
    p.add_argument("--at", type=float, default=15.0)
    p.add_argument("--table-roi")
    p.add_argument("--rack-roi")
    p.add_argument("--zoom", type=float, help="also write analysis/zoom_preview.jpg: the frame as the render will crop it")
    p.add_argument("--zoom-center", help="cx,cy in source pixels (middle of the whole table)")
    p.set_defaults(fn=cmd_roi)

    p = sub.add_parser("audit", help="list the cuts after which the cloth looks different (a shot may have been cut out)")
    common(p)
    p.add_argument("--diff-px", type=int, help="pixels that must differ across a cut to flag it (default 100)")
    p.add_argument("--min-gap", type=float, help="cuts shorter than this many seconds are not checked (default 3)")
    p.add_argument("--handshake", type=float, help="same value as used for render (affects the video time shown)")
    p.add_argument("--intro-sec", type=float, default=4.0, help="intro length used for the video time shown (default 4)")
    p.add_argument("--restore", action="store_true", help="keep the footage inside every flagged cut (extends the clips in clips.json; backup kept)")
    p.add_argument("--restore-max", type=float, default=30.0, help="with --restore: cuts longer than this many seconds are only reported (default 30)")
    p.set_defaults(fn=cmd_audit)

    p = sub.add_parser("racks", help="rebuild racks.json from edited clips.json")
    common(p)
    p.add_argument("--p1"); p.add_argument("--p2"); p.add_argument("--race-to", type=int)
    p.add_argument("--winners")
    p.add_argument("--breaks", help="real break times in source seconds, e.g. 18.8,590.2 or 1:35.0 (source:seconds); add /N to drop clips starting N s before that break, e.g. 590.2/20")
    p.add_argument("--wins", help="time the 9-ball drops in each rack, in rack order (same format as --breaks); add /E to cut the last clip at source time E, e.g. 448.5/450")
    p.add_argument("--drop-misses", dest="drop_misses", action="store_true",
                   help="experimental: drop single-shot clips where the ball count rose (no pot); keeps breaks, run-outs and the 9-ball window")
    p.add_argument("--trim-before-break", dest="trim_before_break", type=float, default=0.0,
                   help="with --breaks: drop clips starting this many seconds before each break (racking noise)")
    p.set_defaults(fn=cmd_racks)

    p = sub.add_parser("score", help="set the winner of each rack")
    common(p)
    p.add_argument("--winners", required=True)
    p.add_argument("--race-to", type=int)
    p.set_defaults(fn=cmd_score)

    p = sub.add_parser("seo", help="write the YouTube title / description / tags for a rendered project")
    common(p)
    p.add_argument("--video", help="rendered video (default: newest output/Condensed_*.mp4)")
    p.add_argument("--venue")
    p.add_argument("--channel")
    p.add_argument("--date")
    p.add_argument("--tournament")
    p.set_defaults(fn=cmd_seo)

    p = sub.add_parser("render", help="render the condensed video")
    common(p)
    p.add_argument("--out")
    p.add_argument("--workers", type=int)
    p.add_argument("--keep-temp", action="store_true")
    p.add_argument("--handshake", type=float, help="seconds kept after the last shot of the match (default 20; shorten it when the next game is being racked)")
    p.add_argument("--style", choices=["swiss", "classic"], help="scoreboard look (default: swiss, templates/swiss_style)")
    p.add_argument("--no-intro", action="store_true", help="do not add the Swiss intro card (default: on, 4 s)")
    p.add_argument("--no-outro", action="store_true", help="do not add the Swiss outro card (default: on, 6 s)")
    p.add_argument("--intro-sec", type=float, help="intro duration in seconds (default 4.0, 0 = no intro)")
    p.add_argument("--outro-sec", type=float, help="outro duration in seconds (default 6.0, 0 = no outro)")
    p.add_argument("--venue", help="optional venue/tournament text shown in the intro capsule (also used in the YouTube description)")
    p.add_argument("--channel", help="channel name used in the YouTube description call to action")
    p.add_argument("--date", help="match date YYYY-MM-DD for the description (default: from the project folder name)")
    p.add_argument("--tournament", help="event name for the YouTube description and tags")
    p.add_argument("--no-youtube", dest="no_youtube", action="store_true", help="do not write the YouTube title/description files")
    p.add_argument("--zoom", type=float, help="punch-in on the table (default 1.3); 1 = no zoom")
    p.add_argument("--zoom-center", help="cx,cy in source pixels: middle of the WHOLE table incl. rails, so the table sits in the middle of the frame (check with `roi --zoom-center ...`)")
    p.add_argument("--room-tone", action="store_true", help="add a quiet room-noise bed under the whole video (picked from the quietest 12 s of the source)")
    p.add_argument("--room-tone-db", type=float, help="level of the room-noise bed in dBFS (default -29)")
    p.add_argument("--no-score-sfx", action="store_true", help="no soft click when the score jumps")
    p.add_argument("--no-fade", action="store_true", help="hard cuts between clips (no fade at the joins)")
    p.add_argument("--fade-video", type=float, help="seconds of picture fade on each side of a cut (default 0.15)")
    p.add_argument("--fade-audio", type=float, help="seconds of audio fade on each side of a cut (default 0.20)")
    p.set_defaults(fn=cmd_render)

    args = ap.parse_args(argv)
    args.fn(args)


if __name__ == "__main__":
    main()
