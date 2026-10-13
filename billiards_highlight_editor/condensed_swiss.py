"""
Swiss Split Ultra-Clean scoreboard HUD for the Full Match Condensed renderer.

Geometry and colours follow templates/swiss_style/SWISS_STYLE_GUIDE.md (section 3.2) and
scripts/make_swiss_assets.render_scoreboard_hud: a 590x84 card pinned at (50, 40) on a transparent
1920x1080 canvas, two tiers (POOL 9-BALL | RACE TO N | VAN X, then [pip] P1 [S1] | [S2] P2 [pip]).

Why not call render_scoreboard_hud / IntroManager.generate_scoreboard_png directly: both ignore the player
names and race_to arguments (they draw the module constants "CHUNG CHOO", "KHUONG LIEU", RACE_TO = 7),
so they cannot render a real match. This module draws the same card with real names, shrinks long names
to fit and returns a PIL image the caller saves.
"""

import os
from typing import Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

try:  # reuse the template's font choice (Segoe UI Bold -> Arial Bold)
    from scripts.make_swiss_assets import FONT_BOLD
except Exception:  # scripts/ is not importable when the CWD is not the repo root
    FONT_BOLD = (r"C:\Windows\Fonts\segoeuib.ttf" if os.path.exists(r"C:\Windows\Fonts\segoeuib.ttf")
                 else r"C:\Windows\Fonts\arialbd.ttf")

CARD_W, CARD_H = 590, 84
CARD_POS = (50, 40)
REF_W = 1920                      # the template is designed on a 1920-wide canvas
SS = 2                            # supersampling factor for smooth rounded corners

GOLD = (229, 193, 88)
BLUE = (30, 144, 255)
WHITE = (255, 255, 255)

_font_cache = {}


def _font(size: float) -> ImageFont.FreeTypeFont:
    key = round(size * 4)
    if key not in _font_cache:
        try:
            _font_cache[key] = ImageFont.truetype(FONT_BOLD, size)
        except OSError:
            _font_cache[key] = ImageFont.load_default(size)
    return _font_cache[key]


def _fit(draw: ImageDraw.ImageDraw, text: str, max_w: float, size: float, min_size: float):
    """Largest font <= size that fits max_w; below min_size the text is cut with an ellipsis."""
    s = size
    while s >= min_size:
        f = _font(s)
        if draw.textlength(text, font=f) <= max_w:
            return text, f
        s -= 0.5 * SS
    f = _font(min_size)
    while len(text) > 1 and draw.textlength(text + "…", font=f) > max_w:
        text = text[:-1]
    return text.rstrip() + "…", f


def rack_label_for(rack: int, score: Tuple[int, int], race_to: int,
                   start_score: Optional[Tuple[int, int]] = None) -> str:
    """Right-hand pill of the top tier: 'FINAL' once a player has reached race_to, else 'VÁN {X}'.
    With start_score (the score when the rack began) the situation label of the 9-ball broadcast style is used while the rack is played:
    'HILL-HILL' when both players are one rack from winning, 'MATCH POINT' when only one is."""
    if max(score) >= race_to:
        return "FINAL"
    if start_score is not None and race_to >= 2:
        a, b = start_score
        if a == b == race_to - 1:
            return "HILL-HILL"
        if max(a, b) == race_to - 1:
            return "MATCH POINT"
    return f"VÁN {rack}"


def render_swiss_scoreboard(
    width: int,
    height: int,
    p1: str,
    p2: str,
    s1: int,
    s2: int,
    race_to: int,
    rack_label: str = "",
    game: str = "POOL 9-BALL",
) -> Image.Image:
    """Full-frame transparent RGBA canvas (width x height) with the Swiss HUD at the same spot every call."""
    k = SS
    W, H = CARD_W * k, CARD_H * k
    card = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(card)

    def box(x0, y0, x1, y1, **kw):
        d.rounded_rectangle([x0 * k, y0 * k, x1 * k, y1 * k], **kw)

    def line(x0, y0, x1, y1, fill):
        d.line([(x0 * k, y0 * k), (x1 * k, y1 * k)], fill=fill, width=k)

    f_pill = _font(11 * k)
    f_score = _font(28 * k)

    # container: frosted obsidian, alpha 235 (~92%), gold hairline
    box(0, 0, CARD_W - 1, CARD_H - 1, radius=14 * k, fill=(14, 18, 26, 235), outline=GOLD + (220,), width=k)

    # tier 1: game tag | race to | rack pill
    box(14, 6, 115, 24, radius=4 * k, fill=GOLD + (255,))
    d.text((64.5 * k, 15 * k), game.upper(), font=f_pill, fill=(12, 14, 20, 255), anchor="mm")
    d.text((CARD_W / 2 * k, 15 * k), f"RACE TO {race_to}", font=f_pill, fill=(210, 220, 235, 255), anchor="mm")
    label = (rack_label or "").upper()
    if label:
        lw = d.textlength(label, font=f_pill) / k
        rx0 = CARD_W - 14 - lw - 20
        box(rx0, 6, CARD_W - 14, 24, radius=4 * k, fill=(24, 28, 40, 255), outline=GOLD + (200,), width=k)
        d.text(((rx0 + CARD_W - 14) / 2 * k, 15 * k), label, font=f_pill, fill=GOLD + (255,), anchor="mm")
    line(14, 29, CARD_W - 14, 29, (45, 55, 75, 180))

    # tier 2: centre divider, score boxes facing each other
    mid = CARD_W // 2
    line(mid, 33, mid, 77, GOLD + (180,))
    sb_w = 46
    sc1_x0 = mid - 8 - sb_w
    sc2_x0 = mid + 8
    box(sc1_x0, 36, sc1_x0 + sb_w, 74, radius=6 * k, fill=(18, 24, 34, 255), outline=BLUE + (200,), width=k)
    box(sc2_x0, 36, sc2_x0 + sb_w, 74, radius=6 * k, fill=(24, 26, 32, 255), outline=GOLD + (200,), width=k)
    cy = 55 * k
    d.text(((sc1_x0 + sb_w / 2) * k, cy), str(s1), font=f_score, fill=WHITE + (255,), anchor="mm")
    d.text(((sc2_x0 + sb_w / 2) * k, cy), str(s2), font=f_score, fill=GOLD + (255,), anchor="mm")

    # pips and names. P1: pip then name from the left. P2: name right after its score box, pip at the far right.
    box(14, 42, 19, 68, radius=2 * k, fill=BLUE + (255,))
    box(CARD_W - 19, 42, CARD_W - 14, 68, radius=2 * k, fill=GOLD + (255,))
    n1_x0, n1_x1 = 28, sc1_x0 - 10
    n2_x0, n2_x1 = sc2_x0 + sb_w + 12, CARD_W - 19 - 8
    t1, f1 = _fit(d, p1.upper(), (n1_x1 - n1_x0) * k, 18 * k, 11 * k)
    t2, f2 = _fit(d, p2.upper(), (n2_x1 - n2_x0) * k, 18 * k, 11 * k)
    d.text((n1_x0 * k, cy), t1, font=f1, fill=WHITE + (255,), anchor="lm")
    d.text((n2_x0 * k, cy), t2, font=f2, fill=WHITE + (255,), anchor="lm")

    card = card.resize((CARD_W, CARD_H), Image.LANCZOS)
    scale = width / float(REF_W)
    if abs(scale - 1.0) > 1e-6:
        card = card.resize((max(1, round(CARD_W * scale)), max(1, round(CARD_H * scale))), Image.LANCZOS)
    canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    canvas.paste(card, (round(CARD_POS[0] * scale), round(CARD_POS[1] * scale)))
    return canvas
