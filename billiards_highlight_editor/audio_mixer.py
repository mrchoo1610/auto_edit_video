"""
Audio Mixer Module:
Mixes FX original audio (100% volume) and BGM (25% - 35% volume) with:
1. Dynamic Audio Ducking down to 15% on impact transients.
2. Climax 1.0-second BGM mute pause before the deciding/clutch shot.
3. Smooth crossfades and normalization.
"""

import os
import subprocess
import tempfile
import numpy as np
from scipy.io import wavfile
from typing import List, Tuple, Optional
import imageio_ffmpeg

from billiards_highlight_editor.config import AudioConfig


class AudioMixer:
    def __init__(self, config: Optional[AudioConfig] = None):
        self.config = config or AudioConfig()
        self.ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()

    def load_or_generate_bgm(
        self,
        bgm_path: Optional[str],
        duration_sec: float,
        sample_rate: int = 44100
    ) -> np.ndarray:
        """
        Loads BGM from file or generates a clean ambient Chillstep/Lo-fi beat if none provided.
        """
        target_len = int(duration_sec * sample_rate)
        if bgm_path and os.path.exists(bgm_path):
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                tmp_bgm_wav = tmp.name
            try:
                cmd = [
                    self.ffmpeg_exe, "-y", "-i", bgm_path,
                    "-vn", "-acodec", "pcm_s16le", "-ar", str(sample_rate), "-ac", "1",
                    tmp_bgm_wav
                ]
                subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                sr, bgm_data = wavfile.read(tmp_bgm_wav)
                bgm_float = bgm_data.astype(np.float32) / 32768.0
                
                # Loop BGM to fill duration
                if len(bgm_float) < target_len:
                    repeats = int(np.ceil(target_len / len(bgm_float)))
                    bgm_float = np.tile(bgm_float, repeats)
                return bgm_float[:target_len]
            finally:
                if os.path.exists(tmp_bgm_wav):
                    try:
                        os.remove(tmp_bgm_wav)
                    except OSError:
                        pass

        # Generate clean procedural ambient rhythm track if no BGM file is passed
        t = np.linspace(0, duration_sec, target_len, endpoint=False)
        # Deep lo-fi sub bass + gentle rhythm pulses
        bass = 0.4 * np.sin(2 * np.pi * 55.0 * t) + 0.2 * np.sin(2 * np.pi * 110.0 * t)
        beat = (np.sin(2 * np.pi * 1.8 * t) > 0.85).astype(np.float32) * 0.15
        synth = 0.1 * np.sin(2 * np.pi * 220.0 * t + 0.5 * np.sin(2 * np.pi * 2.0 * t))
        bgm = bass * 0.5 + beat + synth
        return bgm.astype(np.float32)

    def mix_tracks(
        self,
        fx_audio: np.ndarray,
        sample_rate: int,
        ducking_intervals: List[Tuple[float, float]],
        climax_pause_interval: Optional[Tuple[float, float]] = None,
        bgm_path: Optional[str] = None
    ) -> np.ndarray:
        """
        Spec 4.2:
        - FX priority: 100%
        - BGM: 25% - 35% (self.config.bgm_volume)
        - Ducking: 15% (self.config.ducking_volume) on impact
        - Climax: BGM drops completely silent for 1.0s before clutch shot
        """
        duration_sec = len(fx_audio) / float(sample_rate)
        bgm_audio = self.load_or_generate_bgm(bgm_path, duration_sec, sample_rate)

        # Build dynamic BGM gain curve
        bgm_gain = np.full(len(bgm_audio), self.config.bgm_volume, dtype=np.float32)

        # Apply ducking (smooth fade to 15%)
        for start_t, end_t in ducking_intervals:
            start_idx = int(max(0.0, start_t) * sample_rate)
            end_idx = min(len(bgm_gain), int(end_t * sample_rate))
            if start_idx < end_idx:
                bgm_gain[start_idx:end_idx] = self.config.ducking_volume

        # Apply Climax mute (drop to 0.0)
        if climax_pause_interval:
            c_start, c_end = climax_pause_interval
            c_s_idx = int(max(0.0, c_start) * sample_rate)
            c_e_idx = min(len(bgm_gain), int(c_end * sample_rate))
            if c_s_idx < c_e_idx:
                bgm_gain[c_s_idx:c_e_idx] = 0.0

        # Smooth the gain curve to prevent audio pops
        smoothing_samples = int(sample_rate * 0.05)  # 50ms smoothing window
        if smoothing_samples > 1:
            bgm_gain = np.convolve(bgm_gain, np.ones(smoothing_samples) / smoothing_samples, mode='same')

        # Combine FX at 100% and dynamic BGM
        mixed = (fx_audio * self.config.fx_volume) + (bgm_audio * bgm_gain)

        # Soft limiter / normalization to avoid clipping
        max_peak = np.max(np.abs(mixed))
        if max_peak > 0.98:
            mixed = mixed * (0.98 / max_peak)

        return mixed.astype(np.float32)

    def export_mixed_wav(self, mixed_audio: np.ndarray, sample_rate: int, output_wav_path: str):
        """
        Writes float audio array to 16-bit PCM WAV.
        """
        audio_int16 = (np.clip(mixed_audio, -1.0, 1.0) * 32767.0).astype(np.int16)
        wavfile.write(output_wav_path, sample_rate, audio_int16)
