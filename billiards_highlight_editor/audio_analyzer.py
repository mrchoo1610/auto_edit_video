"""
Audio analyzer module for Billiards Highlight AI Editor.
Implements:
1. Break Shot Detection: 2kHz - 6kHz Butterworth Bandpass filter + Audio Peak Detection (> -3dB).
2. Cue Impact & Transient Detection.
3. Audio ducking and climax silence timeline generation.
"""

import os
import subprocess
import tempfile
import numpy as np
from scipy import signal
from scipy.io import wavfile
from typing import List, Tuple, Dict, Any, Optional
import imageio_ffmpeg

from billiards_highlight_editor.config import AudioConfig, TrimmingConfig


class AudioAnalyzer:
    def __init__(self, config: Optional[AudioConfig] = None, trimming_config: Optional[TrimmingConfig] = None):
        self.config = config or AudioConfig()
        self.trimming = trimming_config or TrimmingConfig()
        self.ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()

    def extract_audio_wav(self, video_path: str, sample_rate: int = 44100) -> Tuple[int, np.ndarray]:
        """
        Extracts mono audio PCM WAV from video to memory numpy array.
        """
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Input video file not found: {video_path}")

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_wav = tmp.name

        try:
            cmd = [
                self.ffmpeg_exe,
                "-y",
                "-i", video_path,
                "-vn",
                "-acodec", "pcm_s16le",
                "-ar", str(sample_rate),
                "-ac", "1",
                tmp_wav
            ]
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if result.returncode != 0:
                raise RuntimeError(f"FFmpeg audio extraction failed: {result.stderr.decode('utf-8', errors='ignore')}")

            sr, data = wavfile.read(tmp_wav)
            # Normalize to float in range [-1.0, 1.0]
            if data.dtype == np.int16:
                audio_float = data.astype(np.float32) / 32768.0
            elif data.dtype == np.int32:
                audio_float = data.astype(np.float32) / 2147483648.0
            elif data.dtype == np.uint8:
                audio_float = (data.astype(np.float32) - 128.0) / 128.0
            else:
                audio_float = data.astype(np.float32)
            
            return sr, audio_float
        finally:
            if os.path.exists(tmp_wav):
                try:
                    os.remove(tmp_wav)
                except OSError:
                    pass

    def apply_bandpass_filter(self, data: np.ndarray, sample_rate: int, low_hz: float, high_hz: float, order: int = 4) -> np.ndarray:
        """
        Butterworth bandpass filter for the 2kHz - 6kHz rack-break impact frequencies.
        """
        nyquist = 0.5 * sample_rate
        low = max(0.01, low_hz / nyquist)
        high = min(0.99, high_hz / nyquist)
        b, a = signal.butter(order, [low, high], btype='band')
        filtered = signal.filtfilt(b, a, data)
        return filtered

    def detect_break_shot_candidates(
        self,
        audio_data: np.ndarray,
        sample_rate: int,
        threshold_db: Optional[float] = None,
        min_distance_sec: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        """
        Spec 5.1: Break Shot Detection Audio Anchor.
        Bandpass filter 2kHz - 6kHz, peak detection with threshold > -3dB.
        Returns list of candidate break peaks:
        [{
            'peak_time': float,
            'peak_db': float,
            'start_time': float (peak - 1.5s),
            'end_time': float (peak + 4.0s)
        }]
        """
        if len(audio_data) == 0:
            return []

        th_db = threshold_db if threshold_db is not None else self.config.break_peak_threshold_db
        min_dist = min_distance_sec if min_distance_sec is not None else self.config.break_min_distance_seconds
        
        # 1. Bandpass filter 2kHz - 6kHz
        filtered = self.apply_bandpass_filter(
            audio_data, sample_rate, 
            self.config.break_filter_low_hz, 
            self.config.break_filter_high_hz
        )

        # 2. Compute amplitude envelope (rolling RMS or absolute max window)
        window_size = int(sample_rate * 0.05)  # 50ms window
        if window_size < 1:
            window_size = 1
        abs_signal = np.abs(filtered)
        envelope = np.convolve(abs_signal, np.ones(window_size) / window_size, mode='same')
        
        # Max peak in dB reference
        max_val = np.max(envelope)
        if max_val <= 1e-6:
            return []
        
        # Convert envelope to dB relative to global max
        envelope_db = 20 * np.log10(np.maximum(envelope / max_val, 1e-6))
        
        # Threshold relative to max: e.g. -3.0 dB
        min_distance_samples = int(min_dist * sample_rate)
        
        # Find peaks above threshold_db
        peaks, properties = signal.find_peaks(
            envelope_db,
            height=th_db,
            distance=min_distance_samples,
            prominence=3.0  # Must stand out from local floor by 3dB
        )

        candidates = []
        for p in peaks:
            peak_time = float(p / sample_rate)
            peak_db = float(envelope_db[p])
            
            start_time = max(0.0, peak_time - self.trimming.break_shot_pre_peak_sec)
            end_time = peak_time + self.trimming.break_shot_post_peak_sec
            
            candidates.append({
                "peak_time": round(peak_time, 3),
                "peak_db": round(peak_db, 2),
                "start_time": round(start_time, 3),
                "end_time": round(end_time, 3),
                "type": "BREAK_SHOT"
            })

        return candidates

    def detect_all_impacts(
        self,
        audio_data: np.ndarray,
        sample_rate: int,
        min_gap_sec: float = 1.2
    ) -> List[float]:
        """
        Detects all cue-to-ball or ball-to-ball impact transients across the entire match.
        """
        if len(audio_data) == 0:
            return []

        # Bandpass between 1000Hz and 8000Hz for all billiard contact clicks
        filtered = self.apply_bandpass_filter(audio_data, sample_rate, 1000.0, 8000.0)
        envelope = np.abs(filtered)
        
        # Local energy spike detection
        window = int(sample_rate * 0.02)  # 20ms
        energy = np.convolve(envelope, np.ones(window) / window, mode='same')
        
        mean_e = np.mean(energy)
        std_e = np.std(energy)
        threshold = mean_e + 2.5 * std_e

        peaks, _ = signal.find_peaks(energy, height=threshold, distance=int(min_gap_sec * sample_rate))
        return [float(p / sample_rate) for p in peaks]

    def generate_ducking_intervals(
        self,
        impact_times: List[float],
        duck_duration_before: float = 0.5,
        duck_duration_after: float = 2.0
    ) -> List[Tuple[float, float]]:
        """
        Generates time ranges [start, end] where BGM is lowered to 15% (audio ducking).
        """
        intervals = []
        for t in impact_times:
            intervals.append((max(0.0, t - duck_duration_before), t + duck_duration_after))
        
        # Merge overlapping intervals
        if not intervals:
            return []
        
        intervals.sort(key=lambda x: x[0])
        merged = [intervals[0]]
        for curr in intervals[1:]:
            prev_start, prev_end = merged[-1]
            if curr[0] <= prev_end:
                merged[-1] = (prev_start, max(prev_end, curr[1]))
            else:
                merged.append(curr)
        return merged
