"""
Swiss Split intro / outro cards for the Full Match Condensed renderer.

Geometry, colours, fonts, the 50/50 obsidian/charcoal split, the champagne laser line, the ambient glows and the
top capsule follow templates/swiss_style/SWISS_STYLE_GUIDE.md (sections 3.1 and 3.3) and
scripts/make_swiss_assets.render_intro_card / render_outro_card.

Why not call those functions (or IntroManager) directly: they ignore the player names and race_to arguments and
always draw the module constants "CHUNG CHOO" / "KHUONG LIEU" with race to 7. Here every text is a parameter, long
names shrink (then get an ellipsis) so they never leave the card, and the winner label only appears once somebody
reached race_to.

The cards are solid RGB stills; fades are done by FFmpeg (card_clip_command), not per-frame Python.
"""

from typing import List, Optional, Sequence

import numpy as np
from PIL import Image, ImageDraw

from billiards_highlight_editor.condensed_swiss import BLUE, GOLD, WHITE, _fit, _font

REF_W, REF_H = 1920, 1080          # the template is designed on a 1920x1080 canvas
MID = REF_W // 2
MUTED = (130, 150, 180)
SOFT = (195, 210, 235)
PANEL = (18, 22, 32)
INK = (12, 14, 20)
RED = (195, 35, 35)

NAME_PT = 72
NAME_MIN_PT = 34
NAME_GAP = 110                     # name block starts this far from the centre line
NAME_MAX_W = MID - NAME_GAP - 110  # 740 px: keeps >= 110 px of margin at the frame edge


# --------------------------------------------------------------------------- shared drawing

def _background() -> Image.Image:
    """50/50 Swiss split: left Obsidian Slate (#0C1018 -> #141A26), right Warm Charcoal (#0A0C10 -> #121318)."""
    x = np.arange(REF_W, dtype=np.float32)
    left = x < MID
    ratio = np.where(left, x / MID, (x - MID) / MID)
    ch = [np.where(left, a + da * ratio, b - db * ratio) for a, da, b, db in
          ((12, 4, 16, 5), (16, 5, 17, 5), (24, 8, 20, 6))]
    row = np.stack(ch, axis=-1).astype(np.uint8)                  # (W, 3)
    return Image.fromarray(np.broadcast_to(row[None], (REF_H, REF_W, 3)).copy(), "RGB")


def _glows(img: Image.Image, side_y: int, halo_y: int) -> Image.Image:
    """Soft ambient glow behind P1 (blue), P2 (gold) and the centre (warm halo), as in the template."""
    ov = Image.new("RGBA", img.size, (0, 0, 0, 0))
    gd = ImageDraw.Draw(ov)
    for cx, col in ((540, BLUE), (1380, GOLD)):
        for i in range(25, 0, -1):
            f = i / 25.0
            rx, ry, a = int(320 * f), int(180 * f), int(26 * (1.0 - f ** 1.5))
            gd.ellipse([cx - rx, side_y - ry, cx + rx, side_y + ry], fill=col + (a,))
    for i in range(20, 0, -1):
        f = i / 20.0
        r, a = int(110 * f), int(22 * (1.0 - f ** 1.5))
        gd.ellipse([MID - r, halo_y - r, MID + r, halo_y + r], fill=GOLD + (a,))
    return Image.alpha_composite(img.convert("RGBA"), ov).convert("RGB")


def _canvas(side_y: int, halo_y: int, line_end: int = REF_H - 140):
    img = _glows(_background(), side_y, halo_y)
    d = ImageDraw.Draw(img)
    # metallic champagne laser hairline
    d.line([(MID - 1, 150), (MID - 1, line_end - 10)], fill=(65, 55, 28), width=3)
    d.line([(MID, 140), (MID, line_end)], fill=GOLD, width=1)
    return img, d


def _ball9(d: ImageDraw.ImageDraw, cx: int, cy: int, r: int):
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(245, 185, 45))
    sh = max(2, int(r * 0.95))
    d.rectangle([cx - r + 1, cy - sh // 2, cx + r - 1, cy + sh // 2], fill=WHITE)
    nr = max(2, int(r * 0.46))
    d.ellipse([cx - nr, cy - nr, cx + nr, cy + nr], fill=WHITE)
    d.ellipse([cx - 2, cy - 2, cx + 2, cy + 2], fill=(25, 25, 30))


def _trophy(d: ImageDraw.ImageDraw, cx: int, cy: int, r: int, color=(245, 205, 75)):
    d.ellipse([cx - int(r * 1.35), cy - int(r * 0.8), cx + int(r * 1.35), cy + int(r * 0.2)], outline=color, width=2)
    d.chord([cx - r, cy - r, cx + r, cy + int(r * 0.25)], start=0, end=180, fill=color)
    d.rectangle([cx - r, cy - r, cx + r, cy - int(r * 0.3)], fill=color)
    d.rectangle([cx - max(1, int(r * 0.2)), cy + int(r * 0.25), cx + max(1, int(r * 0.2)), cy + int(r * 0.7)], fill=color)
    d.rounded_rectangle([cx - int(r * 0.75), cy + int(r * 0.65), cx + int(r * 0.75), cy + int(r * 0.95)],
                        radius=3, fill=color)


def _capsule(d: ImageDraw.ImageDraw, discipline: str, centre_text: str, right_text: str = ""):
    """Top capsule: [9-ball DISCIPLINE] pill, centre text, optional dot + right text. Width adapts to the content."""
    cy, h = 80 + 24, 48
    f_tag, f_mid = _font(15), _font(17)
    tag, f_tag = _fit(d, discipline.upper(), 280, 15, 11)
    pill_w = 44 + d.textlength(tag, font=f_tag) + 20
    centre_w = d.textlength(centre_text, font=f_mid)
    right, f_right = _fit(d, right_text.upper(), 520, 15, 11) if right_text else ("", f_tag)
    right_w = d.textlength(right, font=f_right) if right else 0.0
    group_w = centre_w + (28 + 5 + 28 + right_w if right else 0)
    rest_w = group_w + 2 * 28
    w = max(640.0, 7 + pill_w + rest_w + 7)
    x0 = (REF_W - w) / 2
    d.rounded_rectangle([x0, cy - h / 2, x0 + w, cy + h / 2], radius=24, fill=PANEL, outline=GOLD, width=1)
    d.rounded_rectangle([x0 + 7, cy - h / 2 + 7, x0 + 7 + pill_w, cy + h / 2 - 7], radius=17, fill=GOLD)
    _ball9(d, int(x0 + 7 + 22), cy, 10)
    d.text((x0 + 7 + 40, cy), tag, font=f_tag, fill=INK, anchor="lm")
    gx = x0 + 7 + pill_w + (w - 14 - pill_w - group_w) / 2
    d.text((gx, cy), centre_text, font=f_mid, fill=WHITE, anchor="lm")
    if right:
        dx = gx + centre_w + 28
        d.ellipse([dx, cy - 2, dx + 5, cy + 3], fill=MUTED)
        d.text((dx + 5 + 28, cy), right, font=f_right, fill=SOFT, anchor="lm")


def _name(d: ImageDraw.ImageDraw, text: str, side: int, cy: int, bar_color, fill=WHITE):
    """Player name (uppercase, shrunk to fit) hugging the centre line, with a capsule underline covering all of it.
    side 1: right-aligned to the left of the line, side 2: left-aligned to the right of it. Returns (x0, x1, font)."""
    t, f = _fit(d, text.upper(), NAME_MAX_W, NAME_PT, NAME_MIN_PT)
    w = d.textlength(t, font=f)
    x0 = MID - NAME_GAP - w if side == 1 else MID + NAME_GAP
    d.text((x0 if side == 2 else x0 + w, cy), t, font=f, fill=fill, anchor="lm" if side == 2 else "rm")
    bar_y = cy + int(f.size * 0.62)
    d.rounded_rectangle([x0, bar_y, x0 + w, bar_y + 6], radius=3, fill=bar_color)
    return x0, x0 + w, f


def _finish(img: Image.Image, width: int, height: int) -> Image.Image:
    if (width, height) != (REF_W, REF_H):
        img = img.resize((width, height), Image.LANCZOS)
    return img


# --------------------------------------------------------------------------- intro

def render_intro_card(
    p1: str,
    p2: str,
    race_to: int,
    discipline: str = "POOL 9-BALL",
    date_text: str = "",
    venue: str = "",
    width: int = REF_W,
    height: int = REF_H,
) -> Image.Image:
    """Solid RGB intro card: capsule [DISCIPLINE | RACE TO N | venue], P1 | VS | P2, optional date in the footer."""
    img, d = _canvas(540, 542)
    _capsule(d, discipline, f"RACE TO {race_to}", (venue or "").strip())
    cy = 540
    _name(d, p1, 1, cy, BLUE)
    _name(d, p2, 2, cy, GOLD)

    # centre VS medallion
    vy = cy + 2
    d.ellipse([MID - 52, vy - 52, MID + 52, vy + 52], fill=(14, 18, 26), outline=GOLD, width=2)
    d.ellipse([MID - 44, vy - 44, MID + 44, vy + 44], fill=(22, 26, 36), outline=WHITE, width=1)
    d.text((MID, vy), "VS", font=_font(32), fill=GOLD, anchor="mm")

    if (date_text or "").strip():              # only the date when given; no tagline or other filler text
        foot, f_foot = _fit(d, date_text.strip().upper(), 1500, 17, 11)
        d.text((MID, REF_H - 85), foot, font=f_foot, fill=(180, 195, 220), anchor="mm")
    return _finish(img, width, height)


# --------------------------------------------------------------------------- outro

def resolve_winner(s1: int, s2: int, race_to: int, winner: Optional[int] = None) -> Optional[int]:
    """1 or 2 once somebody reached race_to, else None (no CHAMPION label for an unfinished match)."""
    if max(s1, s2) < race_to:
        return None
    if winner in (1, 2):
        return winner
    return None if s1 == s2 else (1 if s1 > s2 else 2)


def _badge(d: ImageDraw.ImageDraw, side: int, text: str, y0: int, champion: bool):
    f = _font(20)
    tw = d.textlength(text, font=f)
    w = 18 + 34 + tw + 22
    h = 40
    edge = MID - NAME_GAP if side == 1 else MID + NAME_GAP
    x0 = edge - w if side == 1 else edge
    fill, outline, ink = ((34, 36, 44), GOLD, (250, 230, 170)) if champion else ((20, 36, 62), BLUE, (170, 220, 255))
    d.rounded_rectangle([x0, y0, x0 + w, y0 + h], radius=h // 2, fill=fill, outline=outline, width=1)
    cy = y0 + h // 2
    if champion:
        _trophy(d, int(x0 + 31), cy - 2, 11)
    else:
        d.ellipse([x0 + 22, cy - 6, x0 + 34, cy + 6], fill=(160, 200, 240))
    d.text((x0 + 18 + 34, cy), text, font=f, fill=ink, anchor="lm")


def render_outro_card(
    p1: str,
    p2: str,
    s1: int,
    s2: int,
    race_to: int,
    winner: Optional[int] = None,
    discipline: str = "POOL 9-BALL",
    width: int = REF_W,
    height: int = REF_H,
) -> Image.Image:
    """Solid RGB outro card: final score big in the middle, winner highlighted in champagne gold with a
    "VÔ ĐỊCH • CHAMPION" badge and the loser with "Á QUÂN • FINALIST" (only when race_to was reached)."""
    win = resolve_winner(s1, s2, race_to, winner)
    img, d = _canvas(330, 600, line_end=500)   # the laser line stops at the score pill
    _capsule(d, discipline, "KẾT QUẢ CHUNG CUỘC" if win else "TỶ SỐ", f"RACE TO {race_to}")

    ny = 340
    names = {1: p1, 2: p2}
    default_bar = {1: BLUE, 2: GOLD}
    for side in (1, 2):
        if win:
            is_win = side == win
            _name(d, names[side], side, ny, GOLD if is_win else BLUE, fill=GOLD if is_win else WHITE)
            _badge(d, side, "VÔ ĐỊCH  •  CHAMPION" if is_win else "Á QUÂN  •  FINALIST", 222, is_win)
        else:
            _name(d, names[side], side, ny, default_bar[side])

    # final score pill (covers the laser line)
    sy = 600
    f_sc = _font(150)
    a, dash, b = str(s1), " - ", str(s2)
    wa, wd, wb = (d.textlength(t, font=f_sc) for t in (a, dash, b))
    total = wa + wd + wb
    pw = max(440.0, total + 150)
    ph = 210
    d.rounded_rectangle([MID - pw / 2, sy - ph / 2, MID + pw / 2, sy + ph / 2], radius=ph // 2,
                        fill=(14, 18, 26), outline=GOLD, width=2)
    d.rounded_rectangle([MID - pw / 2 + 5, sy - ph / 2 + 5, MID + pw / 2 - 5, sy + ph / 2 - 5], radius=ph // 2 - 5,
                        fill=(22, 26, 36), outline=WHITE, width=1)
    x = MID - total / 2
    for t, wt, col in ((a, wa, GOLD if win == 1 else WHITE), (dash, wd, MUTED), (b, wb, GOLD if win == 2 else WHITE)):
        d.text((x, sy), t, font=f_sc, fill=col, anchor="lm")
        x += wt

    return _finish(img, width, height)


# --------------------------------------------------------------------------- video

def card_clip_command(
    ffmpeg: str,
    enc_args: Sequence[str],
    png_path: str,
    out_path: str,
    duration: float,
    cfg,
    fade_sec: float = 0.4,
) -> List[str]:
    """Still PNG -> mp4 with the exact stream layout of the normal clips (cfg.width x cfg.height, cfg.fps, yuv420p,
    same encoder args and -g, aac 48 kHz stereo silence) so the concat demuxer can join them with -c copy."""
    W, H = cfg.width, cfg.height
    fade = max(0.0, min(fade_sec, duration / 2.0))
    # RGB -> limited-range BT.709 explicitly (swscale would default to BT.601): same colours as the tagged clips
    vf = f"scale={W}:{H}:flags=lanczos:out_color_matrix=bt709:out_range=tv,format=yuv420p,setsar=1"
    if fade > 0:
        vf += f",fade=t=in:st=0:d={fade:.3f},fade=t=out:st={max(0.0, duration - fade):.3f}:d={fade:.3f}"
    vf += f",fps={cfg.fps}"
    return [ffmpeg, "-y", "-v", "error",
            "-loop", "1", "-framerate", str(cfg.fps), "-i", png_path,
            "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000",
            "-vf", vf, "-map", "0:v", "-map", "1:a", "-t", f"{duration:.3f}",
            *enc_args, "-g", str(cfg.fps * 2), "-pix_fmt", "yuv420p",
            "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv",
            "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2", out_path]
