"""
Template script for Full Match Condensed Billiards Editing (YouTube 16:9).
Executes:
1. Audio Peak Strike Detection (In-point: peak - 2.0s)
2. Optical Flow Motion End Detection (v = 0 or pocket drop + 1.0s)
3. Fixed Dark Frosted Scoreboard Overlay (flips only on 9-ball pot)
4. Hardware Accelerated NVENC Concatenation
5. YouTube Chapters Export
"""

import os
import sys
import subprocess
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import imageio_ffmpeg

FFMPEG_EXE = imageio_ffmpeg.get_ffmpeg_exe()

# Font config
FONT_BOLD = r"C:\Windows\Fonts\arialbd.ttf"
FONT_REGULAR = r"C:\Windows\Fonts\arial.ttf"


def generate_condensed_scoreboard(p1_name, p2_name, s1, s2, race_to, out_png_path, active_rack=""):
    """
    Renders a fixed TV broadcast Dark Frosted Glass Scoreboard card at (1920x1080).
    Fixed position: top-left (x=50, y=40).
    """
    canvas = Image.new("RGBA", (1920, 1080), (0, 0, 0, 0))
    W, H = 580, 84
    card = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(card)

    font_title = ImageFont.truetype(FONT_BOLD, 12) if os.path.exists(FONT_BOLD) else None
    font_name = ImageFont.truetype(FONT_BOLD, 18) if os.path.exists(FONT_BOLD) else None
    font_score = ImageFont.truetype(FONT_BOLD, 26) if os.path.exists(FONT_BOLD) else None

    # Dark Frosted background
    draw.rounded_rectangle([0, 0, W - 1, H - 1], radius=10, fill=(15, 20, 30, 230), outline=(218, 165, 32, 220), width=2)

    # Top Tag
    tag_text = f"CONDENSED 9-BALL • RACE TO {race_to}"
    if active_rack:
        tag_text += f" • {active_rack.upper()}"
    draw.rounded_rectangle([12, 6, 260, 24], radius=4, fill=(218, 165, 32, 255))
    draw.text((18, 8), tag_text, font=font_title, fill=(10, 15, 25, 255))

    # P1 Section
    draw.rounded_rectangle([12, 30, 280, 74], radius=6, fill=(25, 35, 55, 255))
    draw.text((22, 42), p1_name, font=font_name, fill=(255, 255, 255, 255))
    draw.rounded_rectangle([225, 30, 280, 74], radius=6, fill=(18, 22, 32, 255), outline=(60, 80, 120, 255), width=1)
    s1_txt = str(s1)
    tw1 = draw.textlength(s1_txt, font=font_score) if font_score else 20
    draw.text((252 - tw1 / 2, 38), s1_txt, font=font_score, fill=(255, 215, 0, 255))

    # P2 Section
    draw.rounded_rectangle([295, 30, 568, 74], radius=6, fill=(35, 35, 45, 255))
    draw.text((305, 42), p2_name, font=font_name, fill=(255, 255, 255, 255))
    draw.rounded_rectangle([513, 30, 568, 74], radius=6, fill=(18, 22, 32, 255), outline=(90, 90, 100, 255), width=1)
    s2_txt = str(s2)
    tw2 = draw.textlength(s2_txt, font=font_score) if font_score else 20
    draw.text((540 - tw2 / 2, 38), s2_txt, font=font_score, fill=(255, 215, 0, 255))

    # Paste at fixed corner
    canvas.paste(card, (50, 40), card)
    canvas.save(out_png_path, "PNG")
    return out_png_path


def render_condensed_match(project_dir, raw_videos, shots_timeline, match_info):
    """
    Renders full match condensed video from a defined shots timeline.
    shots_timeline is a list of dicts:
    [
        {
            "vid": "raw/1012.mp4",
            "strike_t": 18.8,
            "start": 16.8,       # strike_t - 2.0s
            "end": 24.5,         # velocity = 0 (+0.5s) or pot (+1.0s)
            "rack": 1,
            "s_before": (0, 0),
            "s_after": (0, 0),
            "is_win": False,
            "win_t_offset": None,
            "desc": "Rack 1 - Break Shot"
        },
        ...
    ]
    """
    output_dir = os.path.join(project_dir, "output")
    temp_dir = os.path.join(project_dir, "temp", "condensed_clips")
    assets_dir = os.path.join(project_dir, "assets")
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(temp_dir, exist_ok=True)
    os.makedirs(assets_dir, exist_ok=True)

    p1 = match_info.get("p1", "Player 1")
    p2 = match_info.get("p2", "Player 2")
    race_to = match_info.get("race_to", 7)

    clip_paths = []
    youtube_chapters = [
        {"ts": "00:00", "title": f"Khai mạc trận đấu: {p1} vs {p2} (Race to {race_to})"}
    ]

    current_accumulated_time = 0.0
    seen_racks = set()

    print(f"[*] Rendering {len(shots_timeline)} Condensed Shots with GPU NVENC...")

    for idx, shot in enumerate(shots_timeline):
        clip_name = f"condensed_shot_{idx:04d}.mp4"
        clip_path = os.path.join(temp_dir, clip_name)
        clip_paths.append(clip_path)

        dur = shot["end"] - shot["start"]
        rack_num = shot.get("rack", 1)
        s_b = shot.get("s_before", (0, 0))
        s_a = shot.get("s_after", s_b)
        is_win = shot.get("is_win", False)
        win_offset = shot.get("win_t_offset", None)

        # Track chapters
        if rack_num not in seen_racks:
            seen_racks.add(rack_num)
            m = int(current_accumulated_time // 60)
            s = int(current_accumulated_time % 60)
            youtube_chapters.append({
                "ts": f"{m:02d}:{s:02d}",
                "title": f"Ván {rack_num} ({s_b[0]} - {s_b[1]}): Khởi đầu ván đấu"
            })

        if is_win:
            win_exact_t = current_accumulated_time + (win_offset if win_offset else (dur - 1.0))
            m = int(win_exact_t // 60)
            s = int(win_exact_t % 60)
            youtube_chapters.append({
                "ts": f"{m:02d}:{s:02d}",
                "title": f"Ván {rack_num} ({s_a[0]} - {s_a[1]}): Cú ăn bi 9 chốt hạ ván"
            })

        current_accumulated_time += dur

        # Generate scoreboard
        sb_before_png = os.path.join(assets_dir, f"sb_{s_b[0]}_{s_b[1]}.png")
        if not os.path.exists(sb_before_png):
            generate_condensed_scoreboard(p1, p2, s_b[0], s_b[1], race_to, sb_before_png, f"Ván {rack_num}")

        vid_src = shot["vid"]
        if not os.path.isabs(vid_src):
            vid_src = os.path.join(project_dir, vid_src)

        if is_win and s_a != s_b and win_offset:
            sb_after_png = os.path.join(assets_dir, f"sb_{s_a[0]}_{s_a[1]}.png")
            if not os.path.exists(sb_after_png):
                generate_condensed_scoreboard(p1, p2, s_a[0], s_a[1], race_to, sb_after_png, f"Ván {rack_num}")

            filter_c = (
                f"[0:v]scale=1920:1080[v0]; "
                f"[1:v]scale=1920:1080[sb1]; "
                f"[2:v]scale=1920:1080[sb2]; "
                f"[v0][sb1]overlay=0:0:enable='lt(t,{win_offset:.3f})'[v1]; "
                f"[v1][sb2]overlay=0:0:enable='gte(t,{win_offset:.3f})'[vout]"
            )
            cmd = [
                FFMPEG_EXE, "-y",
                "-ss", f"{shot['start']:.3f}",
                "-to", f"{shot['end']:.3f}",
                "-i", vid_src,
                "-loop", "1", "-i", sb_before_png,
                "-loop", "1", "-i", sb_after_png,
                "-filter_complex", filter_c,
                "-map", "[vout]",
                "-map", "0:a?",
                "-c:v", "h264_nvenc", "-preset", "p4", "-cq", "23",
                "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "192k",
                "-shortest",
                clip_path
            ]
        else:
            filter_c = (
                f"[0:v]scale=1920:1080[v0]; "
                f"[1:v]scale=1920:1080[sb]; "
                f"[v0][sb]overlay=0:0[vout]"
            )
            cmd = [
                FFMPEG_EXE, "-y",
                "-ss", f"{shot['start']:.3f}",
                "-to", f"{shot['end']:.3f}",
                "-i", vid_src,
                "-loop", "1", "-i", sb_before_png,
                "-filter_complex", filter_c,
                "-map", "[vout]",
                "-map", "0:a?",
                "-c:v", "h264_nvenc", "-preset", "p4", "-cq", "23",
                "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "192k",
                "-shortest",
                clip_path
            ]

        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=True)
        if (idx + 1) % 5 == 0 or idx == len(shots_timeline) - 1:
            print(f"  • Processed {idx+1}/{len(shots_timeline)} clips")

    # Fast Concat
    concat_list = os.path.join(temp_dir, "concat_list.txt")
    with open(concat_list, "w", encoding="utf-8") as f:
        for cp in clip_paths:
            f.write(f"file '{os.path.abspath(cp).replace('\\', '/')}'\n")

    master_path = os.path.join(output_dir, f"Full_Match_Condensed_{p1}_vs_{p2}_Master.mp4")
    print(f"[*] Concatenating master video into: {master_path}")
    concat_cmd = [
        FFMPEG_EXE, "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", concat_list,
        "-c", "copy",
        master_path
    ]
    subprocess.run(concat_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=True)

    # Export YouTube Chapters
    chapters_path = os.path.join(output_dir, "YouTube_Chapters.txt")
    with open(chapters_path, "w", encoding="utf-8") as f:
        f.write(f"=== YOUTUBE CHAPTERS: {p1} vs {p2} (Race to {race_to}) ===\n\n")
        for ch in youtube_chapters:
            f.write(f"{ch['ts']} - {ch['title']}\n")

    print(f"[✓] Render completed successfully: {master_path}")
    print(f"[✓] YouTube chapters generated: {chapters_path}")

    # Clean up temp
    try:
        for f in os.listdir(temp_dir):
            os.remove(os.path.join(temp_dir, f))
        os.rmdir(temp_dir)
    except Exception:
        pass

    return master_path
