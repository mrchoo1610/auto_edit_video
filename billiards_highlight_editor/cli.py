"""
Command-Line Interface for Automated Billiards Highlight Editor AI Agent.
"""

import os
import sys
import argparse
from typing import Optional

from billiards_highlight_editor.config import EditorConfig, VideoFormat
from billiards_highlight_editor.models import MatchMetadata
from billiards_highlight_editor.pipeline import BilliardsHighlightAgent

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')


def parse_args():
    parser = argparse.ArgumentParser(
        description="AI Agent for Automated Billiards Highlight Editing (Pool / Snooker / Carom)"
    )
    parser.add_argument("-i", "--input", required=True, help="Path to input full match video (MP4, MKV, etc.)")
    parser.add_argument("-i2", "--part2", default=None, help="Path to second part match video (e.g. 1012(1).mp4)")
    parser.add_argument("-o", "--output", default=None, help="Path to output highlight video MP4")
    parser.add_argument(
        "-f", "--format", choices=["horizontal", "vertical"], default="horizontal",
        help="Target video format: 'horizontal' (16:9 YouTube) or 'vertical' (9:16 Shorts/TikTok/Reels)"
    )
    parser.add_argument("-s", "--scores", default=None, help="Path to score sync JSON metadata file")
    parser.add_argument("-m", "--bgm", default=None, help="Path to background music audio file (MP3/WAV)")
    parser.add_argument("--p1", default="Chung Choo", help="Player 1 Name")
    parser.add_argument("--p2", default="Khương Liều", help="Player 2 Name")
    parser.add_argument("--tournament", default="Giao Lưu CLB", help="Tournament name")
    parser.add_argument("--round", default="Trận Giao Hữu", help="Round name")
    parser.add_argument("--race-to", type=int, default=3, help="Race to points (e.g. 3, 7, 9)")
    parser.add_argument(
        "--misses", choices=["none", "dramatic_only", "all"], default="dramatic_only",
        help="How to handle missed shots: 'none' (pure pot highlight), 'dramatic_only' (keep clutch/Hill-Hill misses), 'all' (keep all misses)"
    )
    return parser.parse_args()


def progress_logger(percentage: float, message: str):
    bar_len = 30
    filled = int(bar_len * percentage)
    bar = "█" * filled + "░" * (bar_len - filled)
    sys.stdout.write(f"\r[{bar}] {int(percentage * 100):3d}% | {message:<60}")
    sys.stdout.flush()
    if percentage >= 1.0:
        sys.stdout.write("\n")


def main():
    args = parse_args()
    if not os.path.exists(args.input):
        print(f"Error: Input video not found at '{args.input}'")
        sys.exit(1)

    output_path = args.output
    if not output_path:
        base, ext = os.path.splitext(args.input)
        suffix = "_shorts" if args.format == "vertical" else "_highlights"
        output_path = f"{base}{suffix}.mp4"

    config = EditorConfig()
    if args.format == "vertical":
        config.video_format = VideoFormat.VERTICAL_SHORTS
    else:
        config.video_format = VideoFormat.HORIZONTAL_YOUTUBE

    if args.misses == "none":
        config.trimming.include_routine_misses = False
        config.trimming.include_dramatic_clutch_misses = False
    elif args.misses == "all":
        config.trimming.include_routine_misses = True
        config.trimming.include_dramatic_clutch_misses = True
    else:  # dramatic_only
        config.trimming.include_routine_misses = False
        config.trimming.include_dramatic_clutch_misses = True

    meta = MatchMetadata(
        player_1_name=args.p1,
        player_2_name=args.p2,
        tournament_title=args.tournament,
        round_name=args.round,
        race_to=args.race_to
    )

    print("==================================================================")
    print("        BILLIARDS AI HIGHLIGHT EDITOR AGENT v1.0.0               ")
    print("==================================================================")
    print(f"Input:        {args.input}")
    print(f"Output:       {output_path}")
    print(f"Format:       {config.video_format.value}")
    print(f"Match:        {meta.player_1_name} vs {meta.player_2_name} (Race to {meta.race_to})")
    print(f"Tournament:   {meta.tournament_title} [{meta.round_name}]")
    print("------------------------------------------------------------------")

    agent = BilliardsHighlightAgent(config)

    print("\n[Stage 1/2] Analyzing video, detecting break shots & 3-beat rhythm...")
    script = agent.analyze_video(
        video_path=args.input,
        score_metadata_json=args.scores,
        match_metadata=meta,
        secondary_video_path=args.part2,
        progress_callback=progress_logger
    )

    print(f"\nConstructed timeline with {len(script.segments)} segments (Est. duration: {script.total_duration_sec:.1f}s)")
    for seg in script.segments:
        shot_desc = seg.shot_event.description if seg.shot_event else ""
        print(f"  • {seg.phase.value:<15} [{seg.source_start_sec:6.1f}s -> {seg.source_end_sec:6.1f}s] "
              f"Speed: {seg.playback_speed:.1f}x  {shot_desc}")

    print("\n[Stage 2/2] Exporting highlight video & compositing overlays...")
    agent.export_highlight(
        video_path=args.input,
        script=script,
        output_path=output_path,
        bgm_path=args.bgm,
        progress_callback=progress_logger
    )

    print("==================================================================")
    print(f"Highlight video generated successfully: {output_path}")
    print("==================================================================")


if __name__ == "__main__":
    main()
