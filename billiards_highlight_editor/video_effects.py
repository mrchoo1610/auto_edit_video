"""
Video Effects Module:
Implements:
1. Camera Shake (3% intensity on break shot impact).
2. Kinetic Typography Intro (Match info sliding in 0:04 - 0:06).
3. Outro CTA screen (0:03 - 0:05s).
"""

import math
import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFont
from typing import Tuple, Optional
from billiards_highlight_editor.models import MatchMetadata


class VideoEffects:
    def __init__(self):
        self._font_cache = {}

    def _get_font(self, size: int) -> ImageFont.ImageFont:
        if size in self._font_cache:
            return self._font_cache[size]

        font_paths = [
            "C:/Windows/Fonts/arialbd.ttf",
            "C:/Windows/Fonts/seguisb.ttf",
            "C:/Windows/Fonts/tahomabd.ttf",
            "C:/Windows/Fonts/arial.ttf"
        ]
        for fp in font_paths:
            try:
                font = ImageFont.truetype(fp, size)
                self._font_cache[size] = font
                return font
            except OSError:
                continue

        font = ImageFont.load_default()
        self._font_cache[size] = font
        return font

    def apply_camera_shake(
        self,
        frame: np.ndarray,
        intensity_pct: float = 0.0,
        seed_frame_idx: int = 0
    ) -> np.ndarray:
        """
        Subtle natural camera shake. Disabled by default (intensity=0) to maintain crisp, comfortable viewing.
        """
        if intensity_pct <= 0.005:
            return frame

        h, w = frame.shape[:2]
        max_dx = int(w * intensity_pct * 0.5)
        max_dy = int(h * intensity_pct * 0.5)

        dx = int(max_dx * math.sin(seed_frame_idx * 1.5))
        dy = int(max_dy * math.cos(seed_frame_idx * 1.8))

        M = np.float32([[1, 0, dx], [0, 1, dy]])
        shaken = cv2.warpAffine(frame, M, (w, h), borderMode=cv2.BORDER_REFLECT)
        return shaken

    def render_cinematic_intro_screen(
        self,
        frame_width: int,
        frame_height: int,
        metadata: MatchMetadata,
        progress: float
    ) -> Image.Image:
        """
        Renders a professional, broadcast-grade Intro Title Screen at the beginning of the video.
        Features dark frosted glass card, golden accents, bold typography, and smooth fade transitions.
        """
        overlay = Image.new("RGBA", (frame_width, frame_height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        scale = frame_width / 1920.0
        
        # Fade in over first 20%, hold, fade out in last 20%
        if progress < 0.20:
            alpha_norm = progress / 0.20
        elif progress > 0.80:
            alpha_norm = max(0.0, (1.0 - progress) / 0.20)
        else:
            alpha_norm = 1.0

        alpha = int(240 * alpha_norm)
        if alpha <= 0:
            return overlay

        # Dark overlay on background for cinematic look
        bg_dim = Image.new("RGBA", (frame_width, frame_height), (5, 5, 10, int(160 * alpha_norm)))
        overlay = Image.alpha_composite(overlay, bg_dim)
        draw = ImageDraw.Draw(overlay)

        # Centered Intro Card
        card_w = int(1000 * scale)
        card_h = int(420 * scale)
        cx = (frame_width - card_w) // 2
        cy = (frame_height - card_h) // 2

        # Card body
        draw.rounded_rectangle(
            [cx, cy, cx + card_w, cy + card_h],
            radius=int(12 * scale),
            fill=(15, 18, 26, alpha),
            outline=(255, 215, 0, int(180 * alpha_norm)),
            width=max(2, int(2 * scale))
        )

        font_header = self._get_font(int(20 * scale))
        font_p1 = self._get_font(int(36 * scale))
        font_vs = self._get_font(int(24 * scale))
        font_p2 = self._get_font(int(36 * scale))
        font_foot = self._get_font(int(18 * scale))

        # 1. Header
        header_text = f"{metadata.tournament_title.upper()} • {metadata.round_name.upper()}"
        bbox_h = draw.textbbox((0, 0), header_text, font=font_header)
        hw = bbox_h[2] - bbox_h[0]
        draw.text((cx + (card_w - hw) // 2, cy + int(35 * scale)), header_text, font=font_header, fill=(255, 215, 0, alpha))

        # Thin dividing line
        line_y = cy + int(80 * scale)
        draw.line([cx + int(50 * scale), line_y, cx + card_w - int(50 * scale), line_y], fill=(255, 255, 255, int(60 * alpha_norm)), width=1)

        # 2. Player 1
        p1_text = metadata.player_1_name.upper()
        bbox_p1 = draw.textbbox((0, 0), p1_text, font=font_p1)
        p1w = bbox_p1[2] - bbox_p1[0]
        draw.text((cx + (card_w - p1w) // 2, cy + int(115 * scale)), p1_text, font=font_p1, fill=(100, 200, 255, alpha))

        # 3. VS
        vs_text = "-   V E R S U S   -"
        bbox_vs = draw.textbbox((0, 0), vs_text, font=font_vs)
        vsw = bbox_vs[2] - bbox_vs[0]
        draw.text((cx + (card_w - vsw) // 2, cy + int(190 * scale)), vs_text, font=font_vs, fill=(255, 255, 255, int(220 * alpha_norm)))

        # 4. Player 2
        p2_text = metadata.player_2_name.upper()
        bbox_p2 = draw.textbbox((0, 0), p2_text, font=font_p2)
        p2w = bbox_p2[2] - bbox_p2[0]
        draw.text((cx + (card_w - p2w) // 2, cy + int(245 * scale)), p2_text, font=font_p2, fill=(240, 240, 240, alpha))

        # 5. Footer info
        foot_text = f"TRẬN THI ĐẤU GIAO LƯU RACE TO {metadata.race_to} • 9 POOL"
        bbox_f = draw.textbbox((0, 0), foot_text, font=font_foot)
        fw = bbox_f[2] - bbox_f[0]
        draw.text((cx + (card_w - fw) // 2, cy + int(345 * scale)), foot_text, font=font_foot, fill=(255, 204, 0, alpha))

        return overlay

    def render_rack_chapter_banner(
        self,
        frame_width: int,
        frame_height: int,
        banner_title: str,
        banner_subtitle: str,
        progress: float
    ) -> Image.Image:
        """
        Renders a broadcast-grade Rack Transition Chapter Banner at the start of each rack.
        Smoothly fades in and out to clarify match progress and current rack scores.
        """
        overlay = Image.new("RGBA", (frame_width, frame_height), (0, 0, 0, 0))
        if not banner_title:
            return overlay

        draw = ImageDraw.Draw(overlay)
        scale = frame_width / 1920.0

        if progress < 0.20:
            alpha_norm = progress / 0.20
        elif progress > 0.80:
            alpha_norm = max(0.0, (1.0 - progress) / 0.20)
        else:
            alpha_norm = 1.0

        alpha = int(230 * alpha_norm)
        if alpha <= 0:
            return overlay

        card_w = int(720 * scale)
        card_h = int(105 * scale)
        cx = (frame_width - card_w) // 2
        cy = int(frame_height * 0.72)

        # Frosted glass card with gold accent
        draw.rounded_rectangle(
            [cx, cy, cx + card_w, cy + card_h],
            radius=int(10 * scale),
            fill=(12, 16, 24, alpha),
            outline=(255, 204, 0, int(200 * alpha_norm)),
            width=max(2, int(2 * scale))
        )

        font_title = self._get_font(int(26 * scale))
        font_sub = self._get_font(int(16 * scale))

        # Title (e.g. VÁN 1 • TỶ SỐ: 0 - 0)
        bbox_t = draw.textbbox((0, 0), banner_title, font=font_title)
        tw = bbox_t[2] - bbox_t[0]
        draw.text(
            (cx + (card_w - tw) // 2, cy + int(18 * scale)),
            banner_title,
            font=font_title,
            fill=(255, 215, 0, alpha)
        )

        # Subtitle (e.g. KHỞI ĐỘNG KHỞI TAY, AI CŨNG TƯƠI CƯỜI)
        if banner_subtitle:
            bbox_s = draw.textbbox((0, 0), banner_subtitle, font=font_sub)
            sw = bbox_s[2] - bbox_s[0]
            draw.text(
                (cx + (card_w - sw) // 2, cy + int(60 * scale)),
                banner_subtitle,
                font=font_sub,
                fill=(240, 240, 240, alpha)
            )

        return overlay

    def render_action_badge(
        self,
        frame_width: int,
        frame_height: int,
        action_text: str
    ) -> Image.Image:
        """
        Renders a subtle, clean action label at the bottom right indicating the shot context.
        """
        overlay = Image.new("RGBA", (frame_width, frame_height), (0, 0, 0, 0))
        if not action_text:
            return overlay

        draw = ImageDraw.Draw(overlay)
        scale = frame_width / 1920.0

        font_act = self._get_font(int(14 * scale))
        bbox = draw.textbbox((0, 0), action_text, font=font_act)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]

        pad_x = int(14 * scale)
        pad_y = int(6 * scale)
        bw = tw + pad_x * 2
        bh = th + pad_y * 2

        bx = frame_width - bw - int(40 * scale)
        by = frame_height - bh - int(40 * scale)

        draw.rounded_rectangle(
            [bx, by, bx + bw, by + bh],
            radius=int(4 * scale),
            fill=(10, 14, 20, 190),
            outline=(255, 255, 255, 60),
            width=1
        )
        draw.text((bx + pad_x, by + pad_y), action_text, font=font_act, fill=(255, 215, 0, 230))
        return overlay

    def render_kinetic_typography_intro(
        self,
        frame_width: int,
        frame_height: int,
        metadata: MatchMetadata,
        progress: float  # 0.0 to 1.0 (e.g. over 0:04 to 0:06)
    ) -> Image.Image:
        """
        Spec 3 Phase 1: Kinetic Typography tối giản trượt vào hiển thị thông tin trận đấu
        (Tên cơ thủ, Vòng đấu, Giải đấu).
        """
        overlay = Image.new("RGBA", (frame_width, frame_height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        scale = frame_width / 1920.0
        
        # Slide in from left with smooth ease-out
        t = min(1.0, max(0.0, progress))
        # Ease out cubic: 1 - (1 - t)^3
        ease = 1.0 - math.pow(1.0 - t, 3)

        base_x = int(frame_width * 0.05 * ease)
        base_y = int(frame_height * 0.75)

        banner_w = int(720 * scale * ease)
        banner_h = int(140 * scale)

        # Translucent dark backing with accent bar
        alpha = int(210 * min(1.0, t * 1.5))
        draw.rounded_rectangle(
            [base_x, base_y, base_x + banner_w, base_y + banner_h],
            radius=int(6 * scale),
            fill=(15, 15, 20, alpha),
            outline=(255, 255, 255, int(60 * ease)),
            width=1
        )

        # Accent yellow bar on the left edge
        bar_w = int(6 * scale)
        draw.rectangle([base_x, base_y, base_x + bar_w, base_y + banner_h], fill=(255, 204, 0, alpha))

        if t > 0.15:
            text_alpha = int(255 * min(1.0, (t - 0.15) / 0.5))
            font_tourney = self._get_font(int(14 * scale))
            font_versus = self._get_font(int(24 * scale))
            font_disc = self._get_font(int(12 * scale))

            # Tournament & Round
            draw.text(
                (base_x + int(24 * scale), base_y + int(14 * scale)),
                f"{metadata.tournament_title.upper()} • {metadata.round_name.upper()}",
                font=font_tourney,
                fill=(200, 200, 200, text_alpha)
            )

            # Players VS
            vs_text = f"{metadata.player_1_name.upper()}  VS  {metadata.player_2_name.upper()}"
            draw.text(
                (base_x + int(24 * scale), base_y + int(46 * scale)),
                vs_text,
                font=font_versus,
                fill=(255, 255, 255, text_alpha)
            )

            # Discipline & Race
            draw.text(
                (base_x + int(24 * scale), base_y + int(98 * scale)),
                f"{metadata.game_discipline} | Race to {metadata.race_to}",
                font=font_disc,
                fill=(255, 204, 0, text_alpha)
            )

        return overlay

    def render_outro_cta(
        self,
        frame_width: int,
        frame_height: int,
        metadata: MatchMetadata,
        progress: float
    ) -> Image.Image:
        """
        Spec 3 Phase 4: Outro tối giản (3–5s) hiển thị nút Subscribe/Follow & Final status.
        """
        overlay = Image.new("RGBA", (frame_width, frame_height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        scale = frame_width / 1920.0
        alpha = int(230 * min(1.0, progress * 2.0))

        # Centered dark frosted card
        card_w = int(700 * scale)
        card_h = int(260 * scale)
        cx = (frame_width - card_w) // 2
        cy = (frame_height - card_h) // 2

        draw.rounded_rectangle(
            [cx, cy, cx + card_w, cy + card_h],
            radius=int(12 * scale),
            fill=(12, 12, 16, alpha),
            outline=(255, 255, 255, int(90 * min(1.0, progress))),
            width=2
        )

        font_title = self._get_font(int(26 * scale))
        font_sub = self._get_font(int(16 * scale))
        font_btn = self._get_font(int(18 * scale))

        # Title
        t_text = "TRẬN ĐẤU GIAO LƯU KẾT THÚC!"
        bbox_t = draw.textbbox((0, 0), t_text, font=font_title)
        tw = bbox_t[2] - bbox_t[0]
        draw.text((cx + (card_w - tw) // 2, cy + int(35 * scale)), t_text, font=font_title, fill=(255, 215, 0, alpha))

        # Match summary
        s_text = "CẢM ƠN 2 CƠ THỦ • HẸN GẶP LẠI TRẬN SAU!"
        bbox_s = draw.textbbox((0, 0), s_text, font=font_sub)
        sw = bbox_s[2] - bbox_s[0]
        draw.text(
            (cx + (card_w - sw) // 2, cy + int(95 * scale)),
            s_text,
            font=font_sub,
            fill=(220, 220, 220, alpha)
        )

        # Red CTA Subscribe button
        btn_w = int(280 * scale)
        btn_h = int(50 * scale)
        bx = cx + (card_w - btn_w) // 2
        by = cy + int(160 * scale)

        draw.rounded_rectangle([bx, by, bx + btn_w, by + btn_h], radius=int(6 * scale), fill=(220, 30, 60, alpha))
        btn_text = "ĐĂNG KÝ THEO DÕI"
        bbox_b = draw.textbbox((0, 0), btn_text, font=font_btn)
        bw = bbox_b[2] - bbox_b[0]
        draw.text((bx + (btn_w - bw) // 2, by + int(12 * scale)), btn_text, font=font_btn, fill=(255, 255, 255, alpha))

        return overlay
