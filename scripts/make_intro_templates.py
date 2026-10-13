"""
Generate 4 Modern Minimalist Intro Templates for Billiards YouTube 16:9 (1920x1080).
Styles:
1. Broadcast Clean (Matchroom / WNT International TV Style)
2. Cyber HUD Dark (Modern Angled Athletic / High Contrast)
3. Swiss Split Minimal (50/50 Split Screen Editorial)
4. Glassmorphism Floating (Translucent Frosted Glass Card)
"""

import os
import math
from PIL import Image, ImageDraw, ImageFont, ImageFilter

FONT_BOLD = r"C:\Windows\Fonts\segoeuib.ttf" if os.path.exists(r"C:\Windows\Fonts\segoeuib.ttf") else r"C:\Windows\Fonts\arialbd.ttf"
FONT_REGULAR = r"C:\Windows\Fonts\segoeui.ttf" if os.path.exists(r"C:\Windows\Fonts\segoeui.ttf") else r"C:\Windows\Fonts\arial.ttf"

P1_NAME = "CHUNG CHOO"
P2_NAME = "KHƯƠNG LIỀU"
TOURNAMENT = "GIAO LƯU CLB POOL 9-BALL"
RACE_TO = 7


def create_template_1_broadcast_clean(out_path):
    """
    Template 1: Broadcast Clean (TV Sports Official Style)
    Clean dark slate navy, gold accents, balanced player cards, circular VS badge.
    """
    W, H = 1920, 1080
    img = Image.new("RGBA", (W, H), (12, 16, 24, 255))
    draw = ImageDraw.Draw(img)

    # Subtle horizontal gradient overlay
    for y in range(H):
        alpha = int(255 - (y / H) * 40)
        draw.line([(0, y), (W, y)], fill=(10 + int(y * 8 / H), 14 + int(y * 10 / H), 22 + int(y * 15 / H), 255))

    font_title = ImageFont.truetype(FONT_BOLD, 22)
    font_category = ImageFont.truetype(FONT_BOLD, 16)
    font_name = ImageFont.truetype(FONT_BOLD, 46)
    font_role = ImageFont.truetype(FONT_REGULAR, 18)
    font_vs = ImageFont.truetype(FONT_BOLD, 30)
    font_sub = ImageFont.truetype(FONT_REGULAR, 18)

    # Top Tag Banner: RACE TO 7
    top_y = 260
    tag_w, tag_h = 420, 42
    draw.rounded_rectangle([(W - tag_w) // 2, top_y, (W + tag_w) // 2, top_y + tag_h], radius=8, fill=(218, 165, 32, 255))
    tag_txt = f"POOL 9-BALL • RACE TO {RACE_TO}"
    tw = draw.textlength(tag_txt, font=font_category)
    draw.text(((W - tw) / 2, top_y + 10), tag_txt, font=font_category, fill=(10, 14, 22, 255))

    # Tournament Title
    tour_y = top_y + 60
    tw_tour = draw.textlength(TOURNAMENT, font=font_title)
    draw.text(((W - tw_tour) / 2, tour_y), TOURNAMENT, font=font_title, fill=(200, 210, 230, 255))

    # Decorative thin rule under tournament title
    line_w = 600
    draw.line([(W - line_w) // 2, tour_y + 40, (W + line_w) // 2, tour_y + 40], fill=(60, 75, 105, 180), width=1)

    # Center Player Cards
    card_y = 430
    card_w, card_h = 580, 200

    # P1 Card (Left)
    p1_x = (W // 2) - card_w - 70
    draw.rounded_rectangle([p1_x, card_y, p1_x + card_w, card_y + card_h], radius=16, fill=(18, 25, 38, 240), outline=(50, 70, 105, 200), width=2)
    # Jersey indicator bar
    draw.rounded_rectangle([p1_x + 20, card_y + 30, p1_x + 28, card_y + card_h - 30], radius=4, fill=(30, 144, 255, 255))
    draw.text((p1_x + 45, card_y + 45), "PLAYER 1", font=font_role, fill=(120, 150, 190, 255))
    draw.text((p1_x + 45, card_y + 80), P1_NAME, font=font_name, fill=(255, 255, 255, 255))
    draw.text((p1_x + 45, card_y + 145), "Áo Xanh Dương • Cơ Thủ", font=font_role, fill=(160, 175, 200, 255))

    # P2 Card (Right)
    p2_x = (W // 2) + 70
    draw.rounded_rectangle([p2_x, card_y, p2_x + card_w, card_y + card_h], radius=16, fill=(18, 25, 38, 240), outline=(50, 70, 105, 200), width=2)
    # Jersey indicator bar
    draw.rounded_rectangle([p2_x + 20, card_y + 30, p2_x + 28, card_y + card_h - 30], radius=4, fill=(100, 100, 110, 255))
    draw.text((p2_x + 45, card_y + 45), "PLAYER 2", font=font_role, fill=(120, 150, 190, 255))
    draw.text((p2_x + 45, card_y + 80), P2_NAME, font=font_name, fill=(255, 255, 255, 255))
    draw.text((p2_x + 45, card_y + 145), "Áo Đen • Cơ Thủ", font=font_role, fill=(160, 175, 200, 255))

    # Center VS Badge
    vs_cx, vs_cy = W // 2, card_y + (card_h // 2)
    vs_r = 52
    draw.ellipse([vs_cx - vs_r, vs_cy - vs_r, vs_cx + vs_r, vs_cy + vs_r], fill=(22, 28, 42, 255), outline=(218, 165, 32, 255), width=3)
    vs_tw = draw.textlength("VS", font=font_vs)
    draw.text((vs_cx - vs_tw / 2, vs_cy - 20), "VS", font=font_vs, fill=(255, 215, 0, 255))

    # Bottom Pill
    bot_y = 740
    bot_txt = "FULL MATCH CONDENSED • TỰ ĐỘNG CẮT THỜI GIAN CHẾT • YOUTUBE 16:9"
    tw_bot = draw.textlength(bot_txt, font=font_sub)
    draw.text(((W - tw_bot) / 2, bot_y), bot_txt, font=font_sub, fill=(130, 150, 180, 220))

    img.save(out_path, "PNG")
    return out_path


def create_template_2_cyber_hud(out_path):
    """
    Template 2: Cyber HUD Dark (Modern Angled Athletic / High Contrast)
    Dark carbon surface, neon cyan & electric amber, angled cut corner boxes, athletic typography.
    """
    W, H = 1920, 1080
    img = Image.new("RGBA", (W, H), (14, 16, 20, 255))
    draw = ImageDraw.Draw(img)

    # Grid background lines
    for x in range(0, W, 80):
        draw.line([(x, 0), (x, H)], fill=(22, 26, 34, 120), width=1)
    for y in range(0, H, 80):
        draw.line([(0, y), (W, y)], fill=(22, 26, 34, 120), width=1)

    # Vignette shadow
    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    s_draw = ImageDraw.Draw(shadow)
    s_draw.rectangle([0, 0, W, H], fill=(10, 12, 16, 160))
    img = Image.alpha_composite(img, shadow)
    draw = ImageDraw.Draw(img)

    font_badge = ImageFont.truetype(FONT_BOLD, 15)
    font_name = ImageFont.truetype(FONT_BOLD, 52)
    font_vs = ImageFont.truetype(FONT_BOLD, 36)
    font_stat = ImageFont.truetype(FONT_BOLD, 16)
    font_sub = ImageFont.truetype(FONT_REGULAR, 18)

    # Top Cyber Tag
    tag_y = 230
    tag_w, tag_h = 480, 44
    draw.rectangle([(W - tag_w) // 2, tag_y, (W + tag_w) // 2, tag_y + tag_h], fill=(0, 0, 0, 200), outline=(0, 242, 254, 255), width=2)
    tag_txt = f"// CONDENSED MATCH  |  RACE TO {RACE_TO}"
    tw = draw.textlength(tag_txt, font=font_badge)
    draw.text(((W - tw) / 2, tag_y + 12), tag_txt, font=font_badge, fill=(0, 242, 254, 255))

    # Tournament Line
    tw_tour = draw.textlength(TOURNAMENT.upper(), font=font_stat)
    draw.text(((W - tw_tour) / 2, tag_y + 65), TOURNAMENT.upper(), font=font_stat, fill=(160, 175, 195, 255))

    # Center Angled Cards
    box_w, box_h = 560, 220
    box_y = 410

    # Left Box (Cyan Accent)
    b1_x = (W // 2) - box_w - 70
    draw.rectangle([b1_x, box_y, b1_x + box_w, box_y + box_h], fill=(18, 22, 30, 240), outline=(0, 242, 254, 180), width=2)
    # Top corner cyan notch
    draw.polygon([(b1_x, box_y), (b1_x + 40, box_y), (b1_x, box_y + 40)], fill=(0, 242, 254, 255))
    draw.text((b1_x + 50, box_y + 25), "CORNER 01  [BLUE]", font=font_stat, fill=(0, 242, 254, 255))
    draw.text((b1_x + 50, box_y + 65), P1_NAME, font=font_name, fill=(255, 255, 255, 255))
    draw.line([(b1_x + 50, box_y + 145), (b1_x + box_w - 50, box_y + 145)], fill=(40, 55, 75, 255), width=1)
    draw.text((b1_x + 50, box_y + 165), "AI AUTO-STRIKE TRACKING ACTIVE", font=font_stat, fill=(120, 140, 170, 255))

    # Right Box (Amber Accent)
    b2_x = (W // 2) + 70
    draw.rectangle([b2_x, box_y, b2_x + box_w, box_y + box_h], fill=(18, 22, 30, 240), outline=(255, 184, 0, 180), width=2)
    # Top right corner amber notch
    draw.polygon([(b2_x + box_w, box_y), (b2_x + box_w - 40, box_y), (b2_x + box_w, box_y + 40)], fill=(255, 184, 0, 255))
    draw.text((b2_x + 50, box_y + 25), "CORNER 02  [BLACK]", font=font_stat, fill=(255, 184, 0, 255))
    draw.text((b2_x + 50, box_y + 65), P2_NAME, font=font_name, fill=(255, 255, 255, 255))
    draw.line([(b2_x + 50, box_y + 145), (b2_x + box_w - 50, box_y + 145)], fill=(65, 55, 35, 255), width=1)
    draw.text((b2_x + 50, box_y + 165), "AI AUTO-STRIKE TRACKING ACTIVE", font=font_stat, fill=(170, 150, 120, 255))

    # Center VS Rhombus
    vs_cx, vs_cy = W // 2, box_y + (box_h // 2)
    rhombus_r = 55
    draw.polygon([
        (vs_cx, vs_cy - rhombus_r),
        (vs_cx + rhombus_r, vs_cy),
        (vs_cx, vs_cy + rhombus_r),
        (vs_cx - rhombus_r, vs_cy)
    ], fill=(12, 14, 18, 255), outline=(255, 70, 70, 255), width=3)
    vs_tw = draw.textlength("VS", font=font_vs)
    draw.text((vs_cx - vs_tw / 2, vs_cy - 24), "VS", font=font_vs, fill=(255, 255, 255, 255))

    # Bottom HUD status
    bot_y = 740
    bot_txt = "AUDIO PEAK TRIGGER (-2.0s)  •  OPTICAL FLOW END TRIGGER  •  GPU NVENC ACCELERATION"
    tw_b = draw.textlength(bot_txt, font=font_sub)
    draw.text(((W - tw_b) / 2, bot_y), bot_txt, font=font_sub, fill=(100, 120, 150, 255))

    img.save(out_path, "PNG")
    return out_path


def create_template_3_swiss_split(out_path):
    """
    Template 3: Swiss Split Minimal (50/50 Editorial Split Screen)
    Pure editorial aesthetic, bold split screen, huge typography, gold hairline divider.
    """
    W, H = 1920, 1080
    img = Image.new("RGBA", (W, H), (14, 16, 20, 255))
    draw = ImageDraw.Draw(img)

    # Left half: Slate Graphite
    draw.rectangle([0, 0, W // 2, H], fill=(18, 22, 30, 255))
    # Right half: Charcoal Obsidian
    draw.rectangle([W // 2, 0, W, H], fill=(10, 12, 16, 255))

    # 1px Gold hairline divider in the exact middle
    draw.line([(W // 2, 120), (W // 2, H - 120)], fill=(212, 175, 55, 200), width=2)

    font_top = ImageFont.truetype(FONT_BOLD, 16)
    font_huge_name = ImageFont.truetype(FONT_BOLD, 64)
    font_sub_name = ImageFont.truetype(FONT_REGULAR, 20)
    font_vs = ImageFont.truetype(FONT_BOLD, 22)
    font_foot = ImageFont.truetype(FONT_REGULAR, 15)

    # Top Minimal Header
    top_txt = f"POOL 9-BALL  •  RACE TO {RACE_TO}  •  {TOURNAMENT.upper()}"
    tw_top = draw.textlength(top_txt, font=font_top)
    draw.text(((W - tw_top) / 2, 80), top_txt, font=font_top, fill=(190, 200, 215, 255))

    # Left Player: Chung Choo (Right-aligned to divider)
    p1_first = "CHUNG"
    p1_last = "CHOO"
    tw1_f = draw.textlength(p1_first, font=font_huge_name)
    tw1_l = draw.textlength(p1_last, font=font_huge_name)
    p1_x = (W // 2) - 90

    draw.text((p1_x - tw1_f, 400), p1_first, font=font_huge_name, fill=(255, 255, 255, 255))
    draw.text((p1_x - tw1_l, 480), p1_last, font=font_huge_name, fill=(70, 160, 255, 255))
    sub1 = "Áo Xanh Dương  /  Cơ Thủ 1"
    tw_s1 = draw.textlength(sub1, font=font_sub_name)
    draw.text((p1_x - tw_s1, 580), sub1, font=font_sub_name, fill=(140, 160, 185, 255))

    # Right Player: Khương Liều (Left-aligned from divider)
    p2_first = "KHƯƠNG"
    p2_last = "LIỀU"
    p2_x = (W // 2) + 90

    draw.text((p2_x, 400), p2_first, font=font_huge_name, fill=(255, 255, 255, 255))
    draw.text((p2_x, 480), p2_last, font=font_huge_name, fill=(220, 220, 225, 255))
    sub2 = "Áo Đen  /  Cơ Thủ 2"
    draw.text((p2_x, 580), sub2, font=font_sub_name, fill=(150, 155, 165, 255))

    # Center VS Minimal Circle badge intersecting hairline
    vs_cx, vs_cy = W // 2, 490
    vs_r = 38
    draw.ellipse([vs_cx - vs_r, vs_cy - vs_r, vs_cx + vs_r, vs_cy + vs_r], fill=(14, 16, 22, 255), outline=(212, 175, 55, 255), width=2)
    vs_tw = draw.textlength("VS", font=font_vs)
    draw.text((vs_cx - vs_tw / 2, vs_cy - 14), "VS", font=font_vs, fill=(212, 175, 55, 255))

    # Bottom Footnote
    foot_txt = "FULL MATCH CONDENSED  •  YOUTUBE 16:9  •  ZERO DEAD TIME"
    tw_foot = draw.textlength(foot_txt, font=font_foot)
    draw.text(((W - tw_foot) / 2, 940), foot_txt, font=font_foot, fill=(110, 120, 135, 255))

    img.save(out_path, "PNG")
    return out_path


def create_template_4_glassmorphism(out_path):
    """
    Template 4: Glassmorphism Floating (Translucent Frosted Card HUD)
    Floating center card with 24px rounded corners, blur feel, gradient 1px border, 9-ball emblem.
    """
    W, H = 1920, 1080
    img = Image.new("RGBA", (W, H), (10, 14, 20, 255))
    draw = ImageDraw.Draw(img)

    # Ambient light glow circles in background
    glow_blue = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gb_draw = ImageDraw.Draw(glow_blue)
    gb_draw.ellipse([250, 250, 750, 750], fill=(20, 80, 160, 60))
    glow_gold = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gg_draw = ImageDraw.Draw(glow_gold)
    gg_draw.ellipse([1170, 250, 1670, 750], fill=(180, 130, 20, 50))

    img = Image.alpha_composite(img, glow_blue)
    img = Image.alpha_composite(img, glow_gold)

    # Center Frosted Glass Floating Card
    card_w, card_h = 1320, 540
    cx = (W - card_w) // 2
    cy = (H - card_h) // 2

    # Draw card on top
    glass_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gl_draw = ImageDraw.Draw(glass_layer)

    # Frosted glass body (translucent dark with subtle blue tint)
    gl_draw.rounded_rectangle([cx, cy, cx + card_w, cy + card_h], radius=28, fill=(16, 22, 34, 215), outline=(255, 255, 255, 55), width=2)
    # Inner subtle glow
    gl_draw.rounded_rectangle([cx + 2, cy + 2, cx + card_w - 2, cy + card_h - 2], radius=26, outline=(255, 255, 255, 20), width=1)

    img = Image.alpha_composite(img, glass_layer)
    draw = ImageDraw.Draw(img)

    font_badge = ImageFont.truetype(FONT_BOLD, 15)
    font_tour = ImageFont.truetype(FONT_BOLD, 22)
    font_name = ImageFont.truetype(FONT_BOLD, 48)
    font_outfit = ImageFont.truetype(FONT_REGULAR, 17)
    font_vs = ImageFont.truetype(FONT_BOLD, 28)
    font_foot = ImageFont.truetype(FONT_REGULAR, 16)

    # Floating Card Header
    head_y = cy + 45
    pill_w, pill_h = 320, 36
    draw.rounded_rectangle([(W - pill_w) // 2, head_y, (W + pill_w) // 2, head_y + pill_h], radius=18, fill=(218, 165, 32, 230))
    tag_t = f"POOL 9-BALL  •  RACE TO {RACE_TO}"
    tw = draw.textlength(tag_t, font=font_badge)
    draw.text(((W - tw) / 2, head_y + 8), tag_t, font=font_badge, fill=(12, 16, 24, 255))

    # Tournament Title
    tour_y = head_y + 55
    tw_tour = draw.textlength(TOURNAMENT, font=font_tour)
    draw.text(((W - tw_tour) / 2, tour_y), TOURNAMENT, font=font_tour, fill=(215, 225, 240, 255))

    # Divider line inside card
    div_y = tour_y + 40
    draw.line([cx + 80, div_y, cx + card_w - 80, div_y], fill=(60, 75, 100, 150), width=1)

    # Player 1 Section
    p1_cx = cx + (card_w // 4)
    tw1 = draw.textlength(P1_NAME, font=font_name)
    draw.text((p1_cx - tw1 / 2, div_y + 45), P1_NAME, font=font_name, fill=(255, 255, 255, 255))
    tw1_o = draw.textlength("Áo Xanh Dương  •  Cơ Thủ 1", font=font_outfit)
    draw.text((p1_cx - tw1_o / 2, div_y + 115), "Áo Xanh Dương  •  Cơ Thủ 1", font=font_outfit, fill=(90, 160, 255, 255))

    # Player 2 Section
    p2_cx = cx + (3 * card_w // 4)
    tw2 = draw.textlength(P2_NAME, font=font_name)
    draw.text((p2_cx - tw2 / 2, div_y + 45), P2_NAME, font=font_name, fill=(255, 255, 255, 255))
    tw2_o = draw.textlength("Áo Đen  •  Cơ Thủ 2", font=font_outfit)
    draw.text((p2_cx - tw2_o / 2, div_y + 115), "Áo Đen  •  Cơ Thủ 2", font=font_outfit, fill=(200, 205, 215, 255))

    # Center VS Orb inside card
    vs_cy = div_y + 80
    vs_r = 44
    draw.ellipse([W // 2 - vs_r, vs_cy - vs_r, W // 2 + vs_r, vs_cy + vs_r], fill=(24, 32, 50, 255), outline=(218, 165, 32, 230), width=2)
    vs_tw = draw.textlength("VS", font=font_vs)
    draw.text((W // 2 - vs_tw / 2, vs_cy - 18), "VS", font=font_vs, fill=(255, 215, 0, 255))

    # Bottom of Card
    card_bot_y = cy + card_h - 65
    bot_info = "FULL MATCH CONDENSED  •  ZERO DEAD TIME  •  YOUTUBE 16:9 MASTER"
    tw_b = draw.textlength(bot_info, font=font_foot)
    draw.text(((W - tw_b) / 2, card_bot_y), bot_info, font=font_foot, fill=(130, 145, 170, 220))

    img.save(out_path, "PNG")
    return out_path


def main():
    target_dir = os.path.abspath(r"d:\Works\auto_edit_video\templates\intros")
    os.makedirs(target_dir, exist_ok=True)

    t1 = os.path.join(target_dir, "template_1_broadcast_clean.png")
    t2 = os.path.join(target_dir, "template_2_cyber_hud.png")
    t3 = os.path.join(target_dir, "template_3_swiss_split.png")
    t4 = os.path.join(target_dir, "template_4_glassmorphism.png")

    print("[*] Generating Template 1: Broadcast Clean...")
    create_template_1_broadcast_clean(t1)

    print("[*] Generating Template 2: Cyber HUD Dark...")
    create_template_2_cyber_hud(t2)

    print("[*] Generating Template 3: Swiss Split Minimal...")
    create_template_3_swiss_split(t3)

    print("[*] Generating Template 4: Glassmorphism Floating...")
    create_template_4_glassmorphism(t4)

    print("[OK] All 4 Intro Templates generated successfully in:")
    print(f"    {target_dir}")


if __name__ == "__main__":
    import sys
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    main()
