"""
Swiss Split Pro (Human-Centric & User-Friendly Edition)
Implements Swiss Modern Design upgraded with Human-Centered UX/UI:
1. Warm Ambient Glow (Removes sterile coldness, adds cinematic visual comfort & depth)
2. Tangible Sports Elements: 3D 9-Ball Icon, Active Cue Ball Turn Indicator, Gold Trophy Icon
3. Ergonomic Legibility: 8pt grid, rounded pill contours, high-contrast scores for 6-inch mobile screens
4. Human-Centric Microcopy: Warm Vietnamese copywriting, YouTube Subscribe & Bell CTA button
5. 100% Symmetrical Balance & Zero Visual Clutter.

Generates:
1. templates/swiss_style/template_3_intro_card.png
2. templates/swiss_style/template_3_scoreboard_preview.png
3. templates/swiss_style/template_3_outro_card.png
4. templates/swiss_style/intro_style3_pro.mp4
5. templates/swiss_style/outro_style3_pro.mp4
"""

import os
import subprocess
from PIL import Image, ImageDraw, ImageFont
import imageio_ffmpeg

FFMPEG_EXE = imageio_ffmpeg.get_ffmpeg_exe()

FONT_BOLD = r"C:\Windows\Fonts\segoeuib.ttf" if os.path.exists(r"C:\Windows\Fonts\segoeuib.ttf") else r"C:\Windows\Fonts\arialbd.ttf"
FONT_SEMIBOLD = r"C:\Windows\Fonts\seguisb.ttf" if os.path.exists(r"C:\Windows\Fonts\seguisb.ttf") else r"C:\Windows\Fonts\arialbd.ttf"
FONT_REGULAR = r"C:\Windows\Fonts\segoeui.ttf" if os.path.exists(r"C:\Windows\Fonts\segoeui.ttf") else r"C:\Windows\Fonts\arial.ttf"

P1_NAME = "CHUNG CHOO"
P2_NAME = "KHƯƠNG LIỀU"
TOURNAMENT = "GIAO LƯU CLB POOL 9-BALL"
RACE_TO = 7


def draw_swiss_background(draw, W, H):
    """
    Renders pure 50/50 Swiss solid split background.
    Left: Deep Obsidian Slate (#0C1018 -> #141A26)
    Right: Deep Charcoal (#0A0C10 -> #121318)
    """
    mid_x = W // 2
    for x in range(mid_x):
        ratio = x / float(mid_x)
        r = int(12 + 4 * ratio)
        g = int(16 + 5 * ratio)
        b = int(24 + 8 * ratio)
        draw.line([(x, 0), (x, H)], fill=(r, g, b))

    for x in range(mid_x, W):
        ratio = (x - mid_x) / float(mid_x)
        r = int(16 - 5 * ratio)
        g = int(17 - 5 * ratio)
        b = int(20 - 6 * ratio)
        draw.line([(x, 0), (x, H)], fill=(r, g, b))


def apply_ambient_glows(img, W, H, p1_color=(30, 144, 255), p2_color=(229, 193, 88)):
    """
    Applies subtle, cinematic ambient glow behind P1, P2 and center medallion.
    Removes sterile brutalism and gives warm, comfortable visual depth.
    """
    glow_overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow_overlay)

    # P1 Soft Blue Glow (Left)
    for i in range(25, 0, -1):
        frac = i / 25.0
        rx = int(320 * frac)
        ry = int(180 * frac)
        alpha = int(26 * (1.0 - frac**1.5))
        gd.ellipse([540 - rx, 540 - ry, 540 + rx, 540 + ry], fill=(p1_color[0], p1_color[1], p1_color[2], alpha))

    # P2 Soft Gold Glow (Right)
    for i in range(25, 0, -1):
        frac = i / 25.0
        rx = int(320 * frac)
        ry = int(180 * frac)
        alpha = int(26 * (1.0 - frac**1.5))
        gd.ellipse([1380 - rx, 540 - ry, 1380 + rx, 540 + ry], fill=(p2_color[0], p2_color[1], p2_color[2], alpha))

    # Center Warm Halo
    for i in range(20, 0, -1):
        frac = i / 20.0
        r_val = int(110 * frac)
        alpha = int(22 * (1.0 - frac**1.5))
        gd.ellipse([960 - r_val, 542 - r_val, 960 + r_val, 542 + r_val], fill=(229, 193, 88, alpha))

    return Image.alpha_composite(img.convert("RGBA"), glow_overlay).convert("RGB")


def draw_9ball_icon(draw, cx, cy, r):
    """
    Renders an authentic, tangible 3D 9-Ball Pool Icon.
    """
    # Outer yellow sphere
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(245, 185, 45))
    # Wide white stripe
    stripe_h = max(2, int(r * 0.95))
    draw.rectangle([cx - r, cy - stripe_h // 2, cx + r, cy + stripe_h // 2], fill=(255, 255, 255))
    # Number circle
    nr = max(2, int(r * 0.46))
    draw.ellipse([cx - nr, cy - nr, cx + nr, cy + nr], fill=(255, 255, 255))
    # Number 9 representation (bold dark dot/pill)
    draw.ellipse([cx - 2, cy - 2, cx + 2, cy + 2], fill=(25, 25, 30))
    # Specular 3D light reflection (top-left)
    hl_r = max(1, int(r * 0.22))
    hl_x = cx - int(r * 0.38)
    hl_y = cy - int(r * 0.38)
    draw.ellipse([hl_x - hl_r, hl_y - hl_r, hl_x + hl_r, hl_y + hl_r], fill=(255, 255, 255))


def draw_cue_ball_indicator(draw, cx, cy, r=7, active=True):
    """
    Draws a glowing pearl cue-ball (bi cái) indicator for active striker / turn.
    """
    if active:
        # Glow halo
        draw.ellipse([cx - r - 4, cy - r - 4, cx + r + 4, cy + r + 4], fill=(255, 255, 255, 60))
        draw.ellipse([cx - r - 2, cy - r - 2, cx + r + 2, cy + r + 2], fill=(255, 255, 255, 120))
        # Solid pearl ball
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(250, 252, 255, 255))
        # Specular highlight
        draw.ellipse([cx - 3, cy - 3, cx, cy], fill=(255, 255, 255, 255))
    else:
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(70, 80, 100, 180), outline=(100, 120, 150, 150), width=1)


def draw_gold_trophy(draw, cx, cy, r=16, color=(245, 205, 75)):
    """
    Renders an elegant championship gold trophy icon.
    """
    # Outer handles
    draw.ellipse([cx - int(r * 1.35), cy - int(r * 0.8), cx + int(r * 1.35), cy + int(r * 0.2)], outline=color, width=2)
    # Cup body
    draw.chord([cx - r, cy - r, cx + r, cy + int(r * 0.25)], start=0, end=180, fill=color)
    draw.rectangle([cx - r, cy - r, cx + r, cy - int(r * 0.3)], fill=color)
    # Cup stem
    draw.rectangle([cx - max(1, int(r * 0.2)), cy + int(r * 0.25), cx + max(1, int(r * 0.2)), cy + int(r * 0.7)], fill=color)
    # Cup base
    draw.rounded_rectangle([cx - int(r * 0.75), cy + int(r * 0.65), cx + int(r * 0.75), cy + int(r * 0.95)], radius=3, fill=color)


def render_intro_card(out_path):
    W, H = 1920, 1080
    base_img = Image.new("RGB", (W, H), (10, 12, 16))
    draw_base = ImageDraw.Draw(base_img)
    draw_swiss_background(draw_base, W, H)

    # Apply Human-Centered Soft Ambient Glows
    img = apply_ambient_glows(base_img, W, H)
    draw = ImageDraw.Draw(img)

    divider_x = W // 2

    # Fonts
    font_tag = ImageFont.truetype(FONT_BOLD, 13)
    font_header_mid = ImageFont.truetype(FONT_BOLD, 15)
    font_name = ImageFont.truetype(FONT_BOLD, 72)
    font_vs = ImageFont.truetype(FONT_BOLD, 32)
    font_foot = ImageFont.truetype(FONT_SEMIBOLD, 15)
    font_badge = ImageFont.truetype(FONT_SEMIBOLD, 12)

    # 1. Metallic Champagne Gold Laser Hairline Divider
    draw.line([(divider_x - 1, 150), (divider_x - 1, H - 150)], fill=(65, 55, 28), width=3)
    draw.line([(divider_x, 140), (divider_x, H - 140)], fill=(229, 193, 88), width=1)

    # 2. Symmetrical Architectural Top Capsule
    cap_y = 80
    cap_w, cap_h = 640, 48
    cap_x0 = (W - cap_w) // 2
    draw.rounded_rectangle([cap_x0, cap_y, cap_x0 + cap_w, cap_y + cap_h], radius=24, fill=(18, 22, 32), outline=(229, 193, 88), width=1)

    # Left pill tag: [9-Ball] "POOL 9-BALL"
    draw.rounded_rectangle([cap_x0 + 7, cap_y + 7, cap_x0 + 145, cap_y + cap_h - 7], radius=17, fill=(229, 193, 88))
    draw_9ball_icon(draw, cap_x0 + 26, cap_y + 24, 10)
    draw.text((cap_x0 + 44, cap_y + 16), "POOL 9-BALL", font=font_tag, fill=(12, 14, 20))

    # Center: "CHẠM 7  •  RACE TO 7" (Bilingual & User-Friendly)
    race_t = f"CHẠM {RACE_TO}  •  RACE TO {RACE_TO}"
    rw = draw.textlength(race_t, font=font_header_mid)
    draw.text((cap_x0 + 165, cap_y + 15), race_t, font=font_header_mid, fill=(255, 255, 255))

    # Divider Dot
    draw.ellipse([cap_x0 + 382, cap_y + 22, cap_x0 + 387, cap_y + 27], fill=(130, 150, 180))

    # Right: TOURNAMENT
    tour_t = TOURNAMENT.upper()
    draw.text((cap_x0 + 406, cap_y + 16), tour_t, font=font_tag, fill=(195, 210, 235))

    # 3. Main Player Names (Symmetrical with FULL-WIDTH Underlines & Soft Rounding)
    p_center_y = 540

    # P1 (Left - Right Aligned)
    p1_right = divider_x - 110
    nw1 = draw.textlength(P1_NAME, font=font_name)
    p1_left = p1_right - nw1
    draw.text((p1_left, p_center_y - 45), P1_NAME, font=font_name, fill=(255, 255, 255))

    # FULL-WIDTH Electric Blue underline (6px thickness, rounded pill bar)
    draw.rounded_rectangle([p1_left, p_center_y + 45, p1_right, p_center_y + 51], radius=3, fill=(30, 144, 255))

    # P2 (Right - Left Aligned)
    p2_left = divider_x + 110
    nw2 = draw.textlength(P2_NAME, font=font_name)
    p2_right = p2_left + nw2
    draw.text((p2_left, p_center_y - 45), P2_NAME, font=font_name, fill=(255, 255, 255))

    # FULL-WIDTH Champagne Gold underline (6px thickness, rounded pill bar)
    draw.rounded_rectangle([p2_left, p_center_y + 45, p2_right, p_center_y + 51], radius=3, fill=(229, 193, 88))

    # 4. Center VS Multi-Ring Medallion
    vs_cx, vs_cy = divider_x, p_center_y + 2
    draw.ellipse([vs_cx - 52, vs_cy - 52, vs_cx + 52, vs_cy + 52], fill=(14, 18, 26), outline=(229, 193, 88), width=2)
    draw.ellipse([vs_cx - 44, vs_cy - 44, vs_cx + 44, vs_cy + 44], fill=(22, 26, 36), outline=(255, 255, 255), width=1)
    vsw = draw.textlength("VS", font=font_vs)
    draw.text((vs_cx - vsw / 2, vs_cy - 20), "VS", font=font_vs, fill=(229, 193, 88))

    # 5. Bottom Human-Centric Subtitle (Warm, engaging, no technical jargon)
    bot_y = H - 95
    bot_t = "TRẬN ĐẤU RÚT GỌN  •  THEO DÕI TRỌN VẸN TỪNG CÚ ĐÁNH"
    bw = draw.textlength(bot_t, font=font_foot)
    bot_x = (W - bw) / 2
    draw.text((bot_x, bot_y), bot_t, font=font_foot, fill=(180, 195, 220))

    # Subtle Quality Badge
    q_badge = "1080p 60FPS"
    qw = draw.textlength(q_badge, font=font_badge)
    qx = bot_x + bw + 20
    draw.rounded_rectangle([qx, bot_y - 2, qx + qw + 16, bot_y + 20], radius=4, fill=(24, 30, 42), outline=(30, 144, 255), width=1)
    draw.text((qx + 8, bot_y + 1), q_badge, font=font_badge, fill=(30, 144, 255))

    img.save(out_path, "PNG")
    return out_path


def render_scoreboard_hud(s1, s2, out_path, rack_label="VÁN 10"):
    """
    Renders Swiss Ultra-Clean & Mobile-Friendly Scoreboard HUD at 1920x1080 (transparent RGBA).
    Features:
    - 600x88px container with comfortable 16px corner radius
    - Authentic 9-Ball Icon in the top header
    - High-Contrast Symmetrical Score Clash for mobile screens
    - Cue Ball Turn indicator for instant 0.1s glanceability
    """
    canvas = Image.new("RGBA", (1920, 1080), (0, 0, 0, 0))
    W, H = 600, 88
    card = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(card)

    font_pill = ImageFont.truetype(FONT_BOLD, 11)
    font_name = ImageFont.truetype(FONT_BOLD, 18)
    font_score = ImageFont.truetype(FONT_BOLD, 30)

    # 1. Frosted Obsidian Outer Container (Comfortable 16px rounding)
    draw.rounded_rectangle([0, 0, W - 1, H - 1], radius=16, fill=(14, 18, 26, 235), outline=(229, 193, 88, 220), width=1)

    # 2. Symmetrical Top Bar Spanning Full Width
    # Left: [9-Ball] POOL 9-BALL (Gold Pill)
    draw.rounded_rectangle([14, 6, 130, 26], radius=5, fill=(229, 193, 88, 255))
    draw_9ball_icon(draw, 27, 16, 7)
    draw.text((40, 9), "POOL 9-BALL", font=font_pill, fill=(12, 14, 20, 255))

    # Center: CHẠM 7  •  RACE TO 7
    race_lbl = f"RACE TO {RACE_TO}"
    rw = draw.textlength(race_lbl, font=font_pill)
    draw.text(((W - rw) / 2, 9), race_lbl, font=font_pill, fill=(220, 230, 245, 255))

    # Right: RACK / STATUS (Dark Frosted Gold Border Pill)
    rack_txt = rack_label.upper()
    rkw = draw.textlength(rack_txt, font=font_pill)
    rx1 = W - 14
    rx0 = int(rx1 - rkw - 22)
    draw.rounded_rectangle([rx0, 6, rx1, 26], radius=5, fill=(24, 28, 40, 255), outline=(229, 193, 88, 200), width=1)
    draw.text((rx0 + 11, 9), rack_txt, font=font_pill, fill=(229, 193, 88, 255))

    # Top/Bottom Horizontal Hairline Divider
    draw.line([(14, 31), (W - 14, 31)], fill=(45, 55, 75, 180), width=1)

    # 3. Center Vertical Divider
    draw.line([(W // 2, 35), (W // 2, 81)], fill=(229, 193, 88, 180), width=1)

    # 4. Symmetrical Head-to-Head Clash Layout:
    score_box_w = 48
    p1_area_x0 = 14
    p1_area_x1 = (W // 2) - 8

    # Left (P1): [Blue Pip] (gap) [Cue Ball Indicator] (gap) [Name] ... [Score 1]
    draw.rounded_rectangle([p1_area_x0, 44, p1_area_x0 + 5, 72], radius=2, fill=(30, 144, 255, 255))
    # Glowing Pearl Cue Ball indicator for P1
    draw_cue_ball_indicator(draw, p1_area_x0 + 20, 58, r=5, active=True)
    # P1 Name with comfortable padding
    draw.text((p1_area_x0 + 38, 47), P1_NAME, font=font_name, fill=(255, 255, 255, 255))

    # P1 Score Box (Right-aligned to divider)
    sc1_x0 = p1_area_x1 - score_box_w
    draw.rounded_rectangle([sc1_x0, 38, sc1_x0 + score_box_w, 78], radius=8, fill=(18, 24, 36, 255), outline=(30, 144, 255, 220), width=1)
    s1_t = str(s1)
    sw1 = draw.textlength(s1_t, font=font_score)
    draw.text((sc1_x0 + (score_box_w - sw1) / 2, 41), s1_t, font=font_score, fill=(255, 255, 255, 255))

    # Right (P2): [Score 2] ... [Name] [Gold Pip]
    p2_area_x0 = (W // 2) + 8
    p2_area_x1 = W - 14

    # P2 Score Box (Left-aligned to divider)
    sc2_x0 = p2_area_x0
    draw.rounded_rectangle([sc2_x0, 38, sc2_x0 + score_box_w, 78], radius=8, fill=(26, 28, 36, 255), outline=(229, 193, 88, 220), width=1)
    s2_t = str(s2)
    sw2 = draw.textlength(s2_t, font=font_score)
    draw.text((sc2_x0 + (score_box_w - sw2) / 2, 41), s2_t, font=font_score, fill=(229, 193, 88, 255))

    # P2 Gold Pip (Far Right)
    draw.rounded_rectangle([p2_area_x1 - 5, 44, p2_area_x1, 72], radius=2, fill=(229, 193, 88, 255))
    # P2 Name (Left-aligned after score box)
    draw.text((sc2_x0 + score_box_w + 14, 47), P2_NAME, font=font_name, fill=(255, 255, 255, 255))

    # Paste at broadcast margin
    canvas.paste(card, (50, 40), card)
    canvas.save(out_path, "PNG")
    return out_path


def render_outro_card(winner_name, runner_up_name, s_winner, s_runner, out_path):
    W, H = 1920, 1080
    base_img = Image.new("RGB", (W, H), (10, 12, 16))
    draw_base = ImageDraw.Draw(base_img)
    draw_swiss_background(draw_base, W, H)

    # Apply Human-Centered Soft Ambient Glows
    img = apply_ambient_glows(base_img, W, H)
    draw = ImageDraw.Draw(img)

    divider_x = W // 2

    font_header_tag = ImageFont.truetype(FONT_BOLD, 13)
    font_header_main = ImageFont.truetype(FONT_BOLD, 15)
    font_status_pill = ImageFont.truetype(FONT_BOLD, 14)
    font_name = ImageFont.truetype(FONT_BOLD, 72)
    font_score = ImageFont.truetype(FONT_BOLD, 40)
    font_clash = ImageFont.truetype(FONT_BOLD, 48)
    font_thank = ImageFont.truetype(FONT_BOLD, 25)
    font_cta = ImageFont.truetype(FONT_BOLD, 15)

    # 1. Metallic Gold Laser Hairline Divider
    draw.line([(divider_x - 1, 150), (divider_x - 1, H - 150)], fill=(65, 55, 28), width=3)
    draw.line([(divider_x, 140), (divider_x, H - 140)], fill=(229, 193, 88), width=1)

    # 2. Architectural Top Capsule
    cap_y = 80
    cap_w, cap_h = 640, 48
    cap_x0 = (W - cap_w) // 2
    draw.rounded_rectangle([cap_x0, cap_y, cap_x0 + cap_w, cap_y + cap_h], radius=24, fill=(18, 22, 32), outline=(229, 193, 88), width=1)

    draw.rounded_rectangle([cap_x0 + 7, cap_y + 7, cap_x0 + 160, cap_y + cap_h - 7], radius=17, fill=(229, 193, 88))
    draw.text((cap_x0 + 20, cap_y + 16), "CHAMPIONSHIP", font=font_header_tag, fill=(12, 14, 20))

    res_txt = "KẾT QUẢ CHUNG CUỘC"
    draw.text((cap_x0 + 185, cap_y + 15), res_txt, font=font_header_main, fill=(255, 255, 255))
    draw.ellipse([cap_x0 + 395, cap_y + 22, cap_x0 + 400, cap_y + 27], fill=(130, 150, 180))
    draw.text((cap_x0 + 422, cap_y + 15), f"CHẠM {RACE_TO}  •  RACE TO {RACE_TO}", font=font_header_tag, fill=(195, 210, 235))

    # 3. Duel Layout
    p_center_y = 480

    # Runner-up (Left - Right Aligned)
    p1_right = divider_x - 120
    nw1 = draw.textlength(runner_up_name, font=font_name)
    p1_left = p1_right - nw1

    # Badge: Á QUÂN (Silver Sapphire Badge)
    r_badge_txt = "Á QUÂN  •  FINALIST"
    bw1 = draw.textlength(r_badge_txt, font=font_status_pill)
    b1_x0 = p1_right - bw1 - 28
    b1_y0 = p_center_y - 120
    draw.rounded_rectangle([b1_x0, b1_y0, p1_right, b1_y0 + 34], radius=17, fill=(20, 36, 62), outline=(30, 144, 255), width=1)
    # Silver medal dot
    draw.ellipse([b1_x0 + 12, b1_y0 + 12, b1_x0 + 22, b1_y0 + 22], fill=(160, 200, 240))
    draw.text((b1_x0 + 30, b1_y0 + 9), r_badge_txt, font=font_status_pill, fill=(170, 220, 255))

    # Name
    draw.text((p1_left, p_center_y - 65), runner_up_name, font=font_name, fill=(255, 255, 255))
    # FULL-WIDTH Underline matching name (6px thickness, rounded pill bar)
    draw.rounded_rectangle([p1_left, p_center_y + 30, p1_right, p_center_y + 36], radius=3, fill=(30, 144, 255))

    # Score Text
    sc1_txt = f"{s_runner} VÁN THẮNG"
    sw1 = draw.textlength(sc1_txt, font=font_score)
    draw.text((p1_right - sw1, p_center_y + 55), sc1_txt, font=font_score, fill=(150, 185, 225))

    # Champion (Right - Left Aligned)
    p2_left = divider_x + 120
    nw2 = draw.textlength(winner_name, font=font_name)
    p2_right = p2_left + nw2

    # Badge: VÔ ĐỊCH (Championship Gold Trophy Badge)
    w_badge_txt = "VÔ ĐỊCH  •  CHAMPION"
    bw2 = draw.textlength(w_badge_txt, font=font_status_pill)
    b2_x1 = p2_left + bw2 + 36
    b2_y0 = p_center_y - 120
    draw.rounded_rectangle([p2_left, b2_y0, b2_x1, b2_y0 + 34], radius=17, fill=(34, 36, 44), outline=(229, 193, 88), width=1)
    # Gold Trophy Icon
    draw_gold_trophy(draw, p2_left + 18, b2_y0 + 17, r=9, color=(245, 205, 75))
    draw.text((p2_left + 36, b2_y0 + 9), w_badge_txt, font=font_status_pill, fill=(250, 230, 170))

    # Name
    draw.text((p2_left, p_center_y - 65), winner_name, font=font_name, fill=(255, 255, 255))
    # FULL-WIDTH Underline matching name (6px thickness, rounded pill bar)
    draw.rounded_rectangle([p2_left, p_center_y + 30, p2_right, p_center_y + 36], radius=3, fill=(229, 193, 88))

    # Score Text
    sc2_txt = f"{s_winner} VÁN THẮNG"
    draw.text((p2_left, p_center_y + 55), sc2_txt, font=font_score, fill=(229, 193, 88))

    # 4. Center Final Clash Score Pill
    score_clash_t = f"{s_runner} - {s_winner}"
    med_w, med_h = 196, 88
    med_x0 = divider_x - (med_w // 2)
    med_y0 = p_center_y - 44
    draw.rounded_rectangle([med_x0, med_y0, med_x0 + med_w, med_y0 + med_h], radius=44, fill=(14, 18, 26), outline=(229, 193, 88), width=2)
    draw.rounded_rectangle([med_x0 + 4, med_y0 + 4, med_x0 + med_w - 4, med_y0 + med_h - 4], radius=40, fill=(22, 26, 36), outline=(255, 255, 255), width=1)
    sc_tw = draw.textlength(score_clash_t, font=font_clash)
    draw.text((divider_x - sc_tw / 2, med_y0 + 14), score_clash_t, font=font_clash, fill=(255, 255, 255))

    # 5. Human-Centered Thank You & High-Conversion YouTube CTA Button
    ty_y = 730
    ty_t = "CẢM ƠN QUÝ KHÁN GIẢ ĐÃ ĐỒNG HÀNH & CỔ VŨ HAI CƠ THỦ"
    tw_ty = draw.textlength(ty_t, font=font_thank)
    draw.text(((W - tw_ty) / 2, ty_y), ty_t, font=font_thank, fill=(255, 255, 255))

    # YouTube Subscribe & Play CTA Button
    cta_t = "ĐĂNG KÝ KÊNH ĐỂ THEO DÕI CÁC TRẬN ĐẤU TIẾP THEO"
    tw_cta = draw.textlength(cta_t, font=font_cta)
    cta_w = int(tw_cta + 70)
    cta_h = 44
    cta_x0 = (W - cta_w) // 2
    cta_y0 = H - 105

    # Red YouTube-inspired friendly pill button
    draw.rounded_rectangle([cta_x0, cta_y0, cta_x0 + cta_w, cta_y0 + cta_h], radius=22, fill=(195, 35, 35), outline=(255, 80, 80), width=1)
    
    # Crisp white YouTube Play Icon (Triangle)
    play_cx = cta_x0 + 26
    play_cy = cta_y0 + 22
    draw.polygon([
        (play_cx - 5, play_cy - 7),
        (play_cx - 5, play_cy + 7),
        (play_cx + 7, play_cy)
    ], fill=(255, 255, 255))
    
    draw.text((cta_x0 + 44, cta_y0 + 12), cta_t, font=font_cta, fill=(255, 255, 255))

    img.save(out_path, "PNG")
    return out_path


def render_video_clip(png_path, mp4_path, duration=4.0):
    fade_out = max(0.0, duration - 0.5)
    cmd = [
        FFMPEG_EXE, "-y",
        "-loop", "1", "-i", png_path,
        "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
        "-t", str(duration),
        "-vf", f"fade=t=in:st=0:d=0.4,fade=t=out:st={fade_out:.2f}:d=0.4,fps=60",
        "-c:v", "h264_nvenc", "-preset", "p4", "-cq", "23",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        "-shortest",
        mp4_path
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=True)


def main():
    target_dir = os.path.abspath(r"d:\Works\auto_edit_video\templates\swiss_style")
    os.makedirs(target_dir, exist_ok=True)

    intro_p = os.path.join(target_dir, "template_3_intro_card.png")
    sb_p = os.path.join(target_dir, "template_3_scoreboard_preview.png")
    outro_p = os.path.join(target_dir, "template_3_outro_card.png")

    intro_mp4 = os.path.join(target_dir, "intro_style3_pro.mp4")
    outro_mp4 = os.path.join(target_dir, "outro_style3_pro.mp4")

    print("[*] 1/3 Rendering Swiss Split Master Intro Card (User-Friendly Edition)...")
    render_intro_card(intro_p)

    print("[*] 2/3 Rendering Swiss Ultra-Clean Scoreboard HUD (Head-to-head clash + Cue ball)...")
    render_scoreboard_hud(3, 7, sb_p, "VÁN 10")

    print("[*] 3/3 Rendering Swiss Split Master Outro Card (Celebration + CTA Button)...")
    render_outro_card(P2_NAME, P1_NAME, 7, 3, outro_p)

    print("[*] Rendering Intro MP4 (NVENC 60fps)...")
    render_video_clip(intro_p, intro_mp4, duration=4.0)

    print("[*] Rendering Outro MP4 (NVENC 60fps)...")
    render_video_clip(outro_p, outro_mp4, duration=5.0)

    print("[OK] Swiss Master Suite (User-Friendly) rendered successfully!")


if __name__ == "__main__":
    import sys
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    main()
