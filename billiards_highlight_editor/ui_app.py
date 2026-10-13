"""
Interactive Streamlit Web Dashboard for Billiards AI Highlight Editor Agent.
Allows interactive configuration, shot detection review, live scoreboard preview, and video rendering.
"""

import os
import glob
import streamlit as st
from PIL import Image
import numpy as np

from billiards_highlight_editor.config import EditorConfig, VideoFormat, ShotType
from billiards_highlight_editor.models import MatchMetadata, ScoreboardState, MatchState
from billiards_highlight_editor.scoreboard_engine import ScoreboardEngine
from billiards_highlight_editor.pipeline import BilliardsHighlightAgent


def main():
    st.set_page_config(
        page_title="Billiards AI Highlight Editor",
        page_icon="🎱",
        layout="wide"
    )

    st.title("🎱 Billiards AI Highlight Editor Agent")
    st.caption("Automated Highlight Generation Pipeline (Pool / Snooker / Carom) based on AI Agent Spec")

    # Sidebar: Match Configuration
    st.sidebar.header("🏆 Match Metadata")
    p1 = st.sidebar.text_input("Player 1 Name", value="Shane Van Boening")
    p2 = st.sidebar.text_input("Player 2 Name", value="Francisco Sanchez Ruiz")
    tourney = st.sidebar.text_input("Tournament", value="World Pool Championship")
    round_name = st.sidebar.text_input("Round", value="Championship Final")
    race_to = st.sidebar.number_input("Race To", min_value=1, max_value=30, value=7)
    discipline = st.sidebar.selectbox("Discipline", ["9-Ball Pool", "10-Ball Pool", "8-Ball Pool", "Snooker", "Carom 3-Cushion"])

    metadata = MatchMetadata(
        player_1_name=p1,
        player_2_name=p2,
        tournament_title=tourney,
        round_name=round_name,
        race_to=race_to,
        game_discipline=discipline
    )

    st.sidebar.markdown("---")
    st.sidebar.header("📐 Output Video Format")
    format_choice = st.sidebar.radio(
        "Aspect Ratio",
        ["Horizontal (16:9 YouTube)", "Vertical (9:16 Shorts/Reels/TikTok)"]
    )
    is_vertical = "Vertical" in format_choice

    st.sidebar.markdown("---")
    st.sidebar.header("🎚️ Audio & Rhythm Tuning")
    fx_vol = st.sidebar.slider("FX Volume (Ball cracks)", 0.5, 1.5, 1.0, 0.05)
    bgm_vol = st.sidebar.slider("BGM Volume", 0.1, 0.6, 0.30, 0.05)
    st.sidebar.markdown("---")
    st.sidebar.header("🎯 Cú Bắn Trượt (Missed Shots)")
    miss_policy = st.sidebar.radio(
        "Chính sách xử lý bi trượt:",
        [
            "Lọc bỏ toàn bộ (Highlight sạch - Mãn nhãn)",
            "Chỉ giữ cú trượt kịch tính (Hill-Hill / Bước ngoặt)",
            "Giữ tất cả cú trượt"
        ],
        index=1
    )

    # Main Tabs
    tab_editor, tab_scoreboard, tab_spec = st.tabs(["🎬 Video Processing", "📊 Scoreboard Live Preview", "📋 Specification Summary"])

    with tab_spec:
        st.markdown("""
        ### Specification Architecture Checklist
        * **Explosive Hook (0:00 - 0:08):** Starts immediately with the Break Shot (audio peak > -3dB, 2kHz - 6kHz bandpass). Camera shake 3% + Crack sound.
        * **Dead Time Elimination:** Removes pauses > 2.5s, rack setup (100%), chalking (100% unless deciding rack), referee pauses.
        * **3-Beat Shot Sequence:** Beat 1 Tension (1.0-1.5s) -> Beat 2 Impact (100% speed) -> Beat 3 Resolution (1.5-3.0s, 50% slow-mo for masterpieces).
        * **Scoreboard Overlay:** Minimalist Dark Frosted Glass (70% opacity, 1px border, 4px rounded corner). Hill-Hill and Final badges.
        * **Audio Mixing:** FX 100%, BGM 25-35%, Ducking 15%, Climax 1s silence pause before clutch shot.
        """)

    with tab_scoreboard:
        st.subheader("Minimalist Dark Frosted Glass Scoreboard Preview")
        col_sb1, col_sb2 = st.columns([1, 2])
        with col_sb1:
            sb_p1_score = st.number_input("Player 1 Score", min_value=0, max_value=30, value=6)
            sb_p2_score = st.number_input("Player 2 Score", min_value=0, max_value=30, value=6)
            sb_state = st.selectbox("Match State", [MatchState.NORMAL.value, MatchState.GAME_POINT.value, MatchState.HILL_HILL.value, MatchState.FINAL.value], index=2)

        engine = ScoreboardEngine()
        img = engine.render_scoreboard_overlay(
            1920, 1080,
            player_1_name=p1,
            player_2_name=p2,
            score_1=sb_p1_score,
            score_2=sb_p2_score,
            state=MatchState(sb_state),
            race_to=race_to
        )

        with col_sb2:
            st.image(img, caption="Live Dark Frosted Glass Overlay (Full HD)", use_container_width=True)

    with tab_editor:
        st.subheader("Video File Selection")
        # Scan local files
        local_videos = glob.glob("*.mp4") + glob.glob("*.mkv") + glob.glob("*.crdownload")
        selected_file = st.selectbox("Select video file from workspace", local_videos if local_videos else ["No video files found"])

        custom_path = st.text_input("Or enter absolute video path:", value="")
        target_video = custom_path.strip() if custom_path.strip() else selected_file

        st.markdown("### Scoreboard Sync JSON (Optional)")
        sample_json = """[
  {"timestamp": "00:06.00", "player_1_score": 0, "player_2_score": 0, "state": "NORMAL"},
  {"timestamp": "00:45.00", "player_1_score": 1, "player_2_score": 0, "state": "NORMAL"},
  {"timestamp": "01:30.00", "player_1_score": 3, "player_2_score": 2, "state": "NORMAL"},
  {"timestamp": "02:45.00", "player_1_score": 6, "player_2_score": 6, "state": "HILL-HILL"},
  {"timestamp": "03:45.00", "player_1_score": 7, "player_2_score": 6, "state": "FINAL"}
]"""
        score_json_text = st.text_area("Scores JSON metadata (spec format)", value=sample_json, height=140)

        if st.button("🚀 Run AI Highlight Generation", type="primary"):
            if not os.path.exists(target_video):
                st.error(f"Cannot find video file: {target_video}")
                return

            config = EditorConfig()
            config.video_format = VideoFormat.VERTICAL_SHORTS if is_vertical else VideoFormat.HORIZONTAL_YOUTUBE
            config.audio.fx_volume = fx_vol
            config.audio.bgm_volume = bgm_vol
            config.audio.ducking_volume = 0.15

            if "Lọc bỏ toàn bộ" in miss_policy:
                config.trimming.include_routine_misses = False
                config.trimming.include_dramatic_clutch_misses = False
            elif "Giữ tất cả" in miss_policy:
                config.trimming.include_routine_misses = True
                config.trimming.include_dramatic_clutch_misses = True
            else:
                config.trimming.include_routine_misses = False
                config.trimming.include_dramatic_clutch_misses = True

            agent = BilliardsHighlightAgent(config)
            prog_bar = st.progress(0.0)
            status_text = st.empty()

            def ui_callback(pct, msg):
                prog_bar.progress(min(1.0, max(0.0, pct)))
                status_text.text(msg)

            out_dir = os.path.join(os.getcwd(), "output")
            os.makedirs(out_dir, exist_ok=True)
            base_name = os.path.splitext(os.path.basename(target_video))[0]
            fmt_str = "shorts" if is_vertical else "highlight"
            out_path = os.path.join(out_dir, f"{base_name}_{fmt_str}.mp4")

            try:
                with st.spinner("Analyzing audio transients, tracking motion & building timeline..."):
                    script = agent.analyze_video(
                        video_path=target_video,
                        score_metadata_json=score_json_text,
                        match_metadata=metadata,
                        progress_callback=ui_callback
                    )

                st.success(f"Timeline Generated! {len(script.segments)} segments, ~{script.total_duration_sec:.1f}s duration.")

                # Table of detected segments
                seg_rows = []
                for s in script.segments:
                    seg_rows.append({
                        "Phase": s.phase.value,
                        "Src Start (s)": s.source_start_sec,
                        "Src End (s)": s.source_end_sec,
                        "Speed": f"{s.playback_speed}x",
                        "Shake": s.has_camera_shake,
                        "Description": s.shot_event.description if s.shot_event else ""
                    })
                st.dataframe(seg_rows)

                with st.spinner("Rendering highlight video and compositing overlays..."):
                    agent.export_highlight(
                        video_path=target_video,
                        script=script,
                        output_path=out_path,
                        progress_callback=ui_callback
                    )

                st.balloons()
                st.success(f"Highlight video ready: {out_path}")
                if os.path.exists(out_path):
                    st.video(out_path)

            except Exception as e:
                st.error(f"Error during processing: {str(e)}")


if __name__ == "__main__":
    main()
