"""
Intro Manager for Billiards Video Editing (YouTube 16:9).
Provides 4 modern minimalist intro styles:
- Style 1: Broadcast Clean (TV standard, WNT / Matchroom)
- Style 2: Cyber HUD Dark (Esports / Angled athletic)
- Style 3: Swiss Split Minimal (50/50 split screen, bold typography)
- Style 4: Glassmorphism Floating (Translucent frosted acrylic HUD)

Supports generating 1920x1080 PNG cards and rendering 4-5s NVENC MP4 intro clips with fade effects.
"""

import os
import subprocess
from PIL import Image, ImageDraw, ImageFont
import imageio_ffmpeg

from scripts.make_intro_templates import (
    create_template_1_broadcast_clean,
    create_template_2_cyber_hud,
    create_template_4_glassmorphism,
)
from scripts.make_style3_pro import create_swiss_split_pro


class IntroManager:
    STYLES = {
        1: "Broadcast Clean (TV Standard)",
        2: "Cyber HUD Dark (Angled Esports)",
        3: "Swiss Split Minimal (50/50 Editorial)",
        4: "Glassmorphism Floating (Frosted Glass HUD)"
    }

    def __init__(self, default_style: int = 1):
        self.default_style = default_style
        self.ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()

    def generate_intro_card_png(
        self,
        style_id: int,
        out_png_path: str,
        p1_name: str = "CHUNG CHOO",
        p2_name: str = "KHƯƠNG LIỀU",
        tournament: str = "GIAO LƯU CLB POOL 9-BALL",
        race_to: int = 7
    ) -> str:
        """
        Renders the chosen 1920x1080 intro template card.
        """
        os.makedirs(os.path.dirname(os.path.abspath(out_png_path)), exist_ok=True)
        if style_id == 1:
            create_template_1_broadcast_clean(out_png_path)
        elif style_id == 2:
            create_template_2_cyber_hud(out_png_path)
        elif style_id == 3:
            from scripts.make_swiss_assets import render_intro_card
            render_intro_card(out_png_path)
        elif style_id == 4:
            create_template_4_glassmorphism(out_png_path)
        else:
            create_template_1_broadcast_clean(out_png_path)

        return out_png_path

    def render_intro_clip_nvenc(
        self,
        intro_png_path: str,
        out_mp4_path: str,
        duration_sec: float = 4.0,
        fps: int = 60
    ) -> str:
        """
        Renders a 4-5s MP4 intro clip using GPU NVENC hardware acceleration
        with a smooth 0.5s fade-in and 0.5s fade-out.
        """
        os.makedirs(os.path.dirname(os.path.abspath(out_mp4_path)), exist_ok=True)
        fade_out_start = max(0.0, duration_sec - 0.5)

        cmd = [
            self.ffmpeg_exe, "-y",
            "-loop", "1",
            "-i", intro_png_path,
            "-f", "lavfi",
            "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
            "-t", str(duration_sec),
            "-vf", f"fade=t=in:st=0:d=0.4,fade=t=out:st={fade_out_start:.2f}:d=0.4,fps={fps}",
            "-c:v", "h264_nvenc", "-preset", "p4", "-cq", "23",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k",
            "-shortest",
            out_mp4_path
        ]

        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=True)
        return out_mp4_path

    def generate_scoreboard_png(
        self,
        s1: int,
        s2: int,
        out_png_path: str,
        p1_name: str = "CHUNG CHOO",
        p2_name: str = "KHƯƠNG LIỀU",
        race_to: int = 7,
        rack_label: str = ""
    ) -> str:
        """
        Renders Swiss Ultra-Clean Scoreboard HUD at 1920x1080 (transparent RGBA).
        """
        from scripts.make_swiss_assets import render_scoreboard_hud
        return render_scoreboard_hud(s1, s2, out_png_path, rack_label or "VÁN 10")

    def generate_outro_card_png(
        self,
        winner_name: str,
        runner_up_name: str,
        s_winner: int,
        s_runner: int,
        out_png_path: str,
        race_to: int = 7
    ) -> str:
        """
        Renders Swiss Split Ultra-Clean Outro Championship Card (1920x1080 solid).
        """
        from scripts.make_swiss_assets import render_outro_card
        return render_outro_card(winner_name, runner_up_name, s_winner, s_runner, out_png_path)

    def render_outro_clip_nvenc(
        self,
        outro_png_path: str,
        out_mp4_path: str,
        duration_sec: float = 5.0,
        fps: int = 60
    ) -> str:
        """
        Renders a 5s MP4 outro clip with fade effects using GPU NVENC.
        """
        os.makedirs(os.path.dirname(os.path.abspath(out_mp4_path)), exist_ok=True)
        fade_out_start = max(0.0, duration_sec - 0.5)

        cmd = [
            self.ffmpeg_exe, "-y",
            "-loop", "1",
            "-i", outro_png_path,
            "-f", "lavfi",
            "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
            "-t", str(duration_sec),
            "-vf", f"fade=t=in:st=0:d=0.5,fade=t=out:st={fade_out_start:.2f}:d=0.5,fps={fps}",
            "-c:v", "h264_nvenc", "-preset", "p4", "-cq", "23",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k",
            "-shortest",
            out_mp4_path
        ]

        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=True)
        return out_mp4_path
