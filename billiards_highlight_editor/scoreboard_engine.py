"""
Scoreboard Engine:
Handles OCR parsing / JSON metadata sync and renders high-definition Minimalist Dark Frosted Glass
scoreboard graphic overlays with animated score transitions, 'HILL-HILL' badge, and 'FINAL' badge.
"""

import json
import re
from typing import List, Optional, Tuple, Dict, Any
from PIL import Image, ImageDraw, ImageFont

from billiards_highlight_editor.config import ScoreboardConfig
from billiards_highlight_editor.models import ScoreboardState, MatchState, MatchMetadata


def parse_timestamp_str(ts_str: str) -> float:
    """
    Parses timestamp string like '02:45.00', '1:23', '01:05:12' into seconds.
    """
    parts = ts_str.strip().split(":")
    if len(parts) == 2:
        minutes = float(parts[0])
        seconds = float(parts[1])
        return minutes * 60.0 + seconds
    elif len(parts) == 3:
        hours = float(parts[0])
        minutes = float(parts[1])
        seconds = float(parts[2])
        return hours * 3600.0 + minutes * 60.0 + seconds
    else:
        return float(ts_str)


class ScoreboardEngine:
    def __init__(self, config: Optional[ScoreboardConfig] = None):
        self.config = config or ScoreboardConfig()
        self._font_cache = {}

    def parse_score_metadata_json(self, json_path_or_str: str) -> List[ScoreboardState]:
        """
        Parses score events from a JSON file or JSON string matching Spec 5.3:
        [
          {
            "timestamp": "02:45.00",
            "player_1_score": 5,
            "player_2_score": 4,
            "state": "GAME_POINT"
          }
        ]
        """
        try:
            with open(json_path_or_str, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            data = json.loads(json_path_or_str)

        states: List[ScoreboardState] = []
        for item in data:
            ts_sec = parse_timestamp_str(item.get("timestamp", "00:00.00"))
            p1 = int(item.get("player_1_score", 0))
            p2 = int(item.get("player_2_score", 0))
            
            raw_state = item.get("state", "NORMAL").upper()
            if "HILL" in raw_state:
                st = MatchState.HILL_HILL
            elif "FINAL" in raw_state:
                st = MatchState.FINAL
            elif "POINT" in raw_state or "GAME" in raw_state:
                st = MatchState.GAME_POINT
            else:
                st = MatchState.NORMAL

            annotation = item.get("annotation", "")
            b_start = item.get("break_start")
            b_impact = item.get("break_impact")
            b_end = item.get("break_end")
            r_start = item.get("runout_start")
            r_end = item.get("runout_end")
            r_file = item.get("runout_file", "")

            states.append(ScoreboardState(
                timestamp_sec=ts_sec,
                player_1_score=p1,
                player_2_score=p2,
                state=st,
                annotation=annotation,
                break_start_sec=parse_timestamp_str(b_start) if b_start else None,
                break_impact_sec=parse_timestamp_str(b_impact) if b_impact else None,
                break_end_sec=parse_timestamp_str(b_end) if b_end else None,
                runout_start_sec=parse_timestamp_str(r_start) if r_start else None,
                runout_end_sec=parse_timestamp_str(r_end) if r_end else None,
                runout_file=r_file
            ))

        states.sort(key=lambda s: s.timestamp_sec)
        return states

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

    def render_scoreboard_overlay(
        self,
        frame_width: int,
        frame_height: int,
        player_1_name: str,
        player_2_name: str,
        score_1: int,
        score_2: int,
        state: MatchState = MatchState.NORMAL,
        race_to: int = 7,
        alpha_in: float = 1.0,
        rack_label: str = ""
    ) -> Image.Image:
        """
        Renders a transparent RGBA image of size (frame_width, frame_height)
        containing the Minimalist Dark Frosted Glass Scoreboard at the 5% margin,
        with current rack indicator and status badges.
        """
        overlay = Image.new("RGBA", (frame_width, frame_height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        # Scale factor relative to standard 1080p
        scale = frame_width / 1920.0
        margin_x = int(frame_width * self.config.safe_margin_pct)
        margin_y = int(frame_height * self.config.safe_margin_pct)

        board_w = int(480 * scale)
        board_h = int(106 * scale)
        radius = int(self.config.corner_radius_px * scale)

        pos_x = margin_x
        pos_y = margin_y
        if self.config.position == "bottom_left":
            pos_y = frame_height - margin_y - board_h

        # Frosted glass background: dark 70% opacity
        bg_alpha = int(195 * alpha_in)
        bg_color = (14, 16, 22, bg_alpha)
        
        # Border: 1px subtle white or pulsing amber if Hill-Hill
        if state == MatchState.HILL_HILL:
            border_color = (255, 180, 0, int(230 * alpha_in))
            border_width = max(2, int(2 * scale))
        elif state == MatchState.FINAL:
            border_color = (0, 230, 118, int(230 * alpha_in))
            border_width = max(2, int(2 * scale))
        else:
            border_color = (255, 255, 255, int(90 * alpha_in))
            border_width = max(1, int(1 * scale))

        # Draw rounded rectangle container
        draw.rounded_rectangle(
            [pos_x, pos_y, pos_x + board_w, pos_y + board_h],
            radius=radius,
            fill=bg_color,
            outline=border_color,
            width=border_width
        )

        # Fonts
        font_name = self._get_font(int(16 * scale))
        font_score = self._get_font(int(24 * scale))
        font_tag = self._get_font(int(11 * scale))

        # Row 1: Player 1
        row1_y = pos_y + int(12 * scale)
        draw.text((pos_x + int(18 * scale), row1_y), player_1_name[:26].upper(), font=font_name, fill=(245, 245, 245, int(240 * alpha_in)))
        draw.text((pos_x + board_w - int(50 * scale), row1_y), str(score_1), font=font_score, fill=(255, 215, 0, int(255 * alpha_in)))

        # Dividing thin line
        div_y = pos_y + int(53 * scale)
        draw.line([pos_x + int(14 * scale), div_y, pos_x + board_w - int(14 * scale), div_y], fill=(255, 255, 255, int(45 * alpha_in)), width=1)

        # Row 2: Player 2
        row2_y = pos_y + int(62 * scale)
        draw.text((pos_x + int(18 * scale), row2_y), player_2_name[:26].upper(), font=font_name, fill=(245, 245, 245, int(240 * alpha_in)))
        draw.text((pos_x + board_w - int(50 * scale), row2_y), str(score_2), font=font_score, fill=(255, 215, 0, int(255 * alpha_in)))

        # Top Left Badge: Race info
        race_tag = f"RACE TO {race_to}"
        bbox_race = draw.textbbox((0, 0), race_tag, font=font_tag)
        rw = (bbox_race[2] - bbox_race[0]) + int(14 * scale)
        rh = int(18 * scale)
        rx = pos_x + int(16 * scale)
        ry = pos_y - rh // 2
        draw.rounded_rectangle([rx, ry, rx + rw, ry + rh], radius=int(3 * scale), fill=(40, 45, 60, int(220 * alpha_in)))
        draw.text((rx + int(7 * scale), ry + int(2 * scale)), race_tag, font=font_tag, fill=(220, 220, 220, 255))

        # Top Right Badge: Rack / Match State
        if state == MatchState.FINAL:
            tag_text = "CHUNG CUỘC"
            tag_bg = (0, 180, 80, int(230 * alpha_in))
            tag_color = (255, 255, 255, 255)
        elif state == MatchState.HILL_HILL:
            tag_text = "HILL - HILL"
            tag_bg = (240, 140, 0, int(240 * alpha_in))
            tag_color = (0, 0, 0, 255)
        elif rack_label:
            tag_text = rack_label.upper()
            tag_bg = (25, 90, 170, int(230 * alpha_in))
            tag_color = (255, 255, 255, 255)
        else:
            tag_text = "LIVE"
            tag_bg = (50, 55, 70, int(200 * alpha_in))
            tag_color = (255, 255, 255, 255)

        bbox_tag = draw.textbbox((0, 0), tag_text, font=font_tag)
        tw = (bbox_tag[2] - bbox_tag[0]) + int(16 * scale)
        th = int(18 * scale)
        tx = pos_x + board_w - tw - int(16 * scale)
        ty = pos_y - th // 2
        draw.rounded_rectangle([tx, ty, tx + tw, ty + th], radius=int(3 * scale), fill=tag_bg)
        draw.text((tx + int(8 * scale), ty + int(2 * scale)), tag_text, font=font_tag, fill=tag_color)

        return overlay
