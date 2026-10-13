# Billiards AI Highlight Editor Agent

Hệ thống AI Agent tự động phân tích và dựng highlight video thi đấu Billiards (Pool / Snooker / Carom) theo đặc tả kỹ thuật trong [billiards_ai_editor_agent_spec.md](file:///d:/ChungPX3/Works/auto_edit_video/billiards_ai_editor_agent_spec.md).

---

## 🌟 Tính Năng Nổi Bật Đã Triển Khai

1. **The Explosive Hook (0:00 – 0:08):**
   * Tự động bắt đầu bằng **Cú Phá Bi (Break Shot)** trong 3 giây đầu tiên.
   * Dò tìm đỉnh âm thanh va chạm bi (Audio Peak Detection `> -3dB`, bộ lọc dải tần **2kHz – 6kHz**).
   * Hiệu ứng rung khung hình **Camera Shake 3%** kết hợp âm va đập (*Crack!*).
   * Kinetic Typography trượt vào hiển thị thông tin giải đấu và 2 cơ thủ.

2. **Quy Tắc 3 Nhịp Của Cú Đánh (The 3-Beat Shot Sequence):**
   * **Beat 1 - Vào thế (Tension 1.0s – 1.5s):** Hạ người, đặt cầu tay, nhấp cơ.
   * **Beat 2 - Ra ngọn (Impact 100% real-time):** Khoảnh khắc tác động bi cái.
   * **Beat 3 - Đường bi & Kết quả (Resolution 1.5s – 3.0s):** Bi chạy và rơi lỗ. Tự động áp dụng **Slow-motion 50%** cho các tình huống siêu phẩm (Jump shot, Masse, A-băng).

3. **Loại Bỏ Hoàn Toàn Dead Time (Thời Gian Chết):**
   * Đi bộ quanh bàn / Ngắm góc > 2.5s: Cắt bỏ.
   * Bôi lơ, gom và xếp bi: Cắt bỏ 100%.
   * Theo dõi vận tốc bi trên mặt bàn (`velocity = 0` + 0.5s đệm) để tự ngắt shot.

4. **Bảng Tỷ Số Minimalist Dark Frosted Glass:**
   * Nền đen kính mờ 70%, viền trắng mảnh 1px, bo góc 4px, cách lề an toàn 5%.
   * Chỉ nhảy số sau khi bi quyết định rơi hẳn xuống đáy lỗ.
   * Huy hiệu **`HILL-HILL`** nhấp nháy viền vàng khi chạm điểm ván quyết định.
   * Huy hiệu **`FINAL`** khi kết thúc trận đấu.

5. **Quy Chuẩn Hòa Trộn Âm Thanh (Audio Mixing):**
   * FX (tiếng bi, tiếng lơ, pocket): **100% (Ưu tiên #1)**.
   * BGM (Lo-fi / Phonk / Chillstep): **25% – 35%**.
   * Audio Ducking: Tự động hạ BGM xuống **15%** khi ra ngọn hoặc có tiếng va chạm.
   * **Climax Mute:** Ngắt nhạc nền đúng **1.0 giây** trước cú đánh quyết định để tập trung vào tiếng gõ bi.

6. **Hỗ Trợ Đa Định Dạng:**
   * **Horizontal (16:9 YouTube):** 1920x1080 (3 – 6 phút).
   * **Vertical (9:16 Shorts / Reels / TikTok):** 1080x1920 (45 – 60 giây) với hiệu ứng Blurred Background + Center Focus chuẩn quốc tế.

---

## 🚀 Hướng Dẫn Sử Dụng

### 1. Khởi chạy Giao diện Web (Streamlit Web Dashboard)
Để xem trước bảng tỷ số trực tiếp, điều chỉnh thông số nhịp cắt và dựng video trực quan:
```powershell
streamlit run billiards_highlight_editor/ui_app.py
```

### 2. Sử dụng qua Command-Line Interface (CLI)

**Dựng video ngang YouTube (16:9):**
```powershell
python -m billiards_highlight_editor.cli -i "duong_dan_video.mp4" -o "highlight.mp4" --p1 "Shane Van Boening" --p2 "Francisco Sanchez" --race-to 7
```

**Dựng video dọc Shorts / TikTok (9:16):**
```powershell
python -m billiards_highlight_editor.cli -i "duong_dan_video.mp4" -o "shorts.mp4" -f vertical --p1 "Shane Van Boening" --p2 "Francisco Sanchez"
```

**Đồng bộ tỷ số với file JSON:**
```powershell
python -m billiards_highlight_editor.cli -i "duong_dan_video.mp4" -s "scores.json" -m "background_music.mp3"
```

---

## 📁 Cấu Trúc Mã Nguồn

* [`config.py`](file:///d:/ChungPX3/Works/auto_edit_video/billiards_highlight_editor/config.py): Thông số cấu hình chuẩn theo Spec (âm thanh, ngưỡng cắt, đồ họa).
* [`models.py`](file:///d:/ChungPX3/Works/auto_edit_video/billiards_highlight_editor/models.py): Data models (ShotEvent, ShotBeat, ScoreboardState, TimelinePhase).
* [`audio_analyzer.py`](file:///d:/ChungPX3/Works/auto_edit_video/billiards_highlight_editor/audio_analyzer.py): Bộ lọc Bandpass 2-6kHz & dò tìm Break Shot Peak > -3dB.
* [`motion_tracker.py`](file:///d:/ChungPX3/Works/auto_edit_video/billiards_highlight_editor/motion_tracker.py): Nhận diện mặt bàn bida HSV & theo dõi vận tốc bi.
* [`shot_detector.py`](file:///d:/ChungPX3/Works/auto_edit_video/billiards_highlight_editor/shot_detector.py): Đóng gói 3-Beat Shot Sequence & lọc Dead Time 2.5s.
* [`scoreboard_engine.py`](file:///d:/ChungPX3/Works/auto_edit_video/billiards_highlight_editor/scoreboard_engine.py): Render Scoreboard Dark Frosted Glass & nhận diện trạng thái Hill-Hill / Final.
* [`audio_mixer.py`](file:///d:/ChungPX3/Works/auto_edit_video/billiards_highlight_editor/audio_mixer.py): Hòa âm FX 100%, BGM 25-35%, Ducking 15% và 1s lặng trước cú then chốt.
* [`video_effects.py`](file:///d:/ChungPX3/Works/auto_edit_video/billiards_highlight_editor/video_effects.py): Camera Shake 3%, Kinetic Typography Intro và Outro CTA.
* [`video_renderer.py`](file:///d:/ChungPX3/Works/auto_edit_video/billiards_highlight_editor/video_renderer.py): FFmpeg rendering engine hỗ trợ cả 16:9 và 9:16 Shorts.
* [`pipeline.py`](file:///d:/ChungPX3/Works/auto_edit_video/billiards_highlight_editor/pipeline.py): BilliardsHighlightAgent - Bộ điều phối toàn diện.
* [`ui_app.py`](file:///d:/ChungPX3/Works/auto_edit_video/billiards_highlight_editor/ui_app.py): Giao diện web Streamlit.
* [`tests/`](file:///d:/ChungPX3/Works/auto_edit_video/billiards_highlight_editor/tests): Bộ 10 bài test tự động cho toàn bộ hệ thống.
