"""
Swiss Split Minimal v2.1 (Ultra-Clean Edition)
UX/UI Refinements:
- Stripped 100% redundant text: Removed all shirt color labels, corner tags, and secondary role clutter.
- Pure Hero Focus: 'CHUNG CHOO' vs 'KHƯƠNG LIỀU' in bold 76pt athletic typography.
- Architectural breathing space: Maximum negative space, balanced Golden Ratio layout.
- Laser hairline divider in Champagne Gold with multi-ring VS medallion.
- Ultra-clean header capsule and sleek minimal footer.
"""

import os
from PIL import Image, ImageDraw, ImageFont

FONT_BOLD = r"C:\Windows\Fonts\segoeuib.ttf" if os.path.exists(r"C:\Windows\Fonts\segoeuib.ttf") else r"C:\Windows\Fonts\arialbd.ttf"
FONT_SEMIBOLD = r"C:\Windows\Fonts\seguisb.ttf" if os.path.exists(r"C:\Windows\Fonts\seguisb.ttf") else r"C:\Windows\Fonts\arialbd.ttf"
FONT_REGULAR = r"C:\Windows\Fonts\segoeui.ttf" if os.path.exists(r"C:\Windows\Fonts\segoeui.ttf") else r"C:\Windows\Fonts\arial.ttf"

P1_NAME = "CHUNG CHOO"
P2_NAME = "KHƯƠNG LIỀU"
TOURNAMENT = "GIAO LƯU CLB POOL 9-BALL"
RACE_TO = 7


def create_swiss_split_pro(out_path):
    W, H = 1920, 1080
    img = Image.new("RGB", (W, H), (10, 12, 16))
    draw = ImageDraw.Draw(img)

    # 1. Dual-toned solid background split
    # Left Half: Deep Obsidian Navy Slate
    for x in range(W // 2):
        ratio = x / (W / 2)
        r = int(12 + 4 * ratio)
        g = int(16 + 5 * ratio)
        b = int(24 + 8 * ratio)
        draw.line([(x, 0), (x, H)], fill=(r, g, b))

    # Right Half: Deep Warm Charcoal Obsidian
    for x in range(W // 2, W):
        ratio = (x - W / 2) / (W / 2)
        r = int(16 - 5 * ratio)
        g = int(17 - 5 * ratio)
        b = int(20 - 6 * ratio)
        draw.line([(x, 0), (x, H)], fill=(r, g, b))

    # 2. Typography fonts
    font_header_tag = ImageFont.truetype(FONT_BOLD, 13)
    font_header_main = ImageFont.truetype(FONT_BOLD, 15)
    font_name = ImageFont.truetype(FONT_BOLD, 74)
    font_vs = ImageFont.truetype(FONT_BOLD, 30)
    font_footer = ImageFont.truetype(FONT_BOLD, 13)

    divider_x = W // 2

    # 3. Laser Hairline Divider (Metallic Champagne Gold #E5C158)
    draw.line([(divider_x - 1, 150), (divider_x - 1, H - 150)], fill=(65, 55, 28), width=3)
    draw.line([(divider_x, 140), (divider_x, H - 140)], fill=(229, 193, 88), width=1)

    # 4. Architectural Header Capsule (Top Center)
    cap_y = 80
    cap_w, cap_h = 580, 46
    cap_x0 = (W - cap_w) // 2
    draw.rounded_rectangle([cap_x0, cap_y, cap_x0 + cap_w, cap_y + cap_h], radius=23, fill=(18, 22, 32), outline=(229, 193, 88), width=1)

    # Left pill tag: "POOL 9-BALL"
    tag_w = 125
    draw.rounded_rectangle([cap_x0 + 7, cap_y + 7, cap_x0 + 7 + tag_w, cap_y + cap_h - 7], radius=16, fill=(229, 193, 88))
    draw.text((cap_x0 + 20, cap_y + 15), "POOL 9-BALL", font=font_header_tag, fill=(12, 14, 20))

    # Middle text: RACE TO 7
    race_txt = f"RACE TO {RACE_TO}"
    draw.text((cap_x0 + 160, cap_y + 14), race_txt, font=font_header_main, fill=(255, 255, 255))

    # Dot separator
    draw.ellipse([cap_x0 + 270, cap_y + 21, cap_x0 + 275, cap_y + 26], fill=(130, 150, 180))

    # Right text: TOURNAMENT
    tour_txt = TOURNAMENT.upper()
    draw.text((cap_x0 + 295, cap_y + 15), tour_txt, font=font_header_tag, fill=(185, 200, 225))

    # 5. Pure Hero Player Names (Vertically & Horizontally Balanced)
    p_center_y = 540

    # Player 1 (Left Half - Right Aligned toward divider)
    p1_right_edge = divider_x - 110
    nw1 = draw.textlength(P1_NAME, font=font_name)
    draw.text((p1_right_edge - nw1, p_center_y - 45), P1_NAME, font=font_name, fill=(255, 255, 255))
    # Elegant minimalist accent bar below name
    draw.rounded_rectangle([p1_right_edge - 160, p_center_y + 45, p1_right_edge, p_center_y + 49], radius=2, fill=(30, 144, 255))

    # Player 2 (Right Half - Left Aligned from divider)
    p2_left_edge = divider_x + 110
    draw.text((p2_left_edge, p_center_y - 45), P2_NAME, font=font_name, fill=(255, 255, 255))
    # Elegant minimalist accent bar below name
    draw.rounded_rectangle([p2_left_edge, p_center_y + 45, p2_left_edge + 160, p_center_y + 49], radius=2, fill=(229, 193, 88))

    # 6. Center "VS" Multi-ring Medallion
    vs_cx, vs_cy = divider_x, p_center_y + 2
    vs_r_outer = 50
    vs_r_inner = 42

    # Outer gold ring
    draw.ellipse([vs_cx - vs_r_outer, vs_cy - vs_r_outer, vs_cx + vs_r_outer, vs_cy + vs_r_outer], fill=(14, 18, 26), outline=(229, 193, 88), width=2)
    # Inner inset ring
    draw.ellipse([vs_cx - vs_r_inner, vs_cy - vs_r_inner, vs_cx + vs_r_inner, vs_cy + vs_r_inner], fill=(20, 24, 34), outline=(255, 255, 255), width=1)

    # VS text
    vsw = draw.textlength("VS", font=font_vs)
    draw.text((vs_cx - vsw / 2, vs_cy - 19), "VS", font=font_vs, fill=(229, 193, 88))

    # 7. Bottom Minimal Anchor HUD (Footer)
    bot_y = H - 90
    bot_txt = "FULL MATCH CONDENSED  •  ZERO DEAD TIME"
    tw_b = draw.textlength(bot_txt, font=font_footer)
    draw.text(((W - tw_b) / 2, bot_y), bot_txt, font=font_footer, fill=(120, 135, 160))

    img.save(out_path, "PNG")
    return out_path


if __name__ == "__main__":
    import sys
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')

    out_p = r"d:\Works\auto_edit_video\templates\intros\template_3_swiss_split_pro.png"
    create_swiss_split_pro(out_p)
    print(f"[OK] Generated Swiss Split Ultra-Clean Edition at: {out_p}")
