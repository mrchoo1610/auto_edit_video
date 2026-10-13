# Hướng Dẫn Quy Chuẩn Thiết Kế: Swiss Split Pro (Human-Centric & User-Friendly Edition)

Tài liệu này là **Quy chuẩn Thiết kế và Đặc tả Kỹ thuật (Design System & UX/UI Specification Guide)** dành riêng cho AI Agent khi tự động biên tập, sinh đồ họa và kết xuất video cho các trận đấu Billiards (Pool 9 bi, 10 bi, 8 bi, Snooker) theo phong cách **Swiss Split Pro** nâng cấp thân thiện với người dùng (Human-Centered Design).

---

## 1. Triết Lý Thiết Kế Thân Thiện Với Người Dùng (Human-Centered Philosophy)

Phong cách **Swiss Split Pro (User-Friendly Edition)** kết hợp hoàn hảo giữa **Chủ nghĩa Tối giản Thụy Sĩ (Swiss Minimalism)** và **Thiết kế Trải nghiệm Người xem YouTube (Viewer UX)**:

```mermaid
flowchart LR
    A["Swiss Minimalism (Tối giản)"] --> C["Swiss Split Pro\n(User-Friendly)"]
    B["Human-Centered UX (Ấm áp, Trực quan)"] --> C
    C --> D1["1. Soft Ambient Glow (Ánh sáng ấm)"]
    C --> D2["2. Tangible 9-Ball & Trophy Icons"]
    C --> D3["3. Active Cue Ball Turn Indicator"]
    C --> D4["4. Mobile Glanceability (0.1s - 0.5s)"]
    C --> D5["5. High-Conversion YouTube CTA"]
```

1. **Xóa Bỏ Sự Lạnh Lùng (Warmth Over Sterile Brutalism)**:
   - Swiss cổ điển thuần túy dễ gây cảm giác khô cứng và ảm đạm.
   - Bản nâng cấp bổ sung **Soft Ambient Glow** (quầng sáng tản mềm sapphire xanh dương phía P1, vàng sâm panh ấm phía P2) tạo chiều sâu điện ảnh (Cinematic Depth), giúp đôi mắt người xem dễ chịu, giảm căng thẳng thị giác (Eye Strain).
2. **Yếu Tố Thể Thao Trực Quan (Tangible Sports Motifs)**:
   - Biểu tượng **Quả Bi Số 9 (3D 9-Ball Icon)** vàng sọc trắng bóng bẩy tại nhãn thể thức.
   - Đèn báo **Bi Cái Trắng Ngà (Cue Ball Indicator `⚪`)** báo hiệu lượt đánh của cơ thủ.
   - Biểu tượng **Cúp Vàng Vô Địch (3D Gold Trophy)** tôn vinh người chiến thắng tại Outro.
3. **Tối Ưu Cho Màn Hình Điện Thoại (Mobile Glanceability)**:
   - Hơn 70% khán giả YouTube xem trên điện thoại thông minh (màn hình 6 inch).
   - Hộp số điểm nâng kích thước lên `48x40px` với độ tương phản cực cao, bo góc mềm mại `radius=8px` (hệ thống lưới 8pt).
4. **Ngôn Từ Tự Nhiên & Gần Gũi (Human-Centric Microcopy)**:
   - Loại bỏ các thuật ngữ máy móc khô cứng (*"ZERO DEAD TIME"*, *"YOUTUBE 16:9"*).
   - Thay bằng câu từ thể thao ấm áp: *"TRẬN ĐẤU RÚT GỌN • THEO DÕI TRỌN VẸN TỪNG CÚ ĐÁNH"*, nút CTA đăng ký kênh có biểu tượng chuông `🔔` quen thuộc của YouTube.

---

## 2. Hệ Thống Design Tokens (Bảng Mã Màu & Phông Chữ)

### 2.1. Bảng Màu Chuẩn (Color Tokens)

| Tên Token | Mã HEX | Giá trị RGB | Ý nghĩa & Ứng dụng |
| :--- | :--- | :--- | :--- |
| **Obsidian Slate (P1 Base)** | `#0C1018` $\to$ `#141A26` | `(12, 16, 24)` $\to$ `(20, 26, 38)` | Nền nửa trái (Phía Cơ thủ 1 / Á Quân) |
| **Warm Charcoal (P2 Base)** | `#0A0C10` $\to$ `#121318` | `(10, 12, 16)` $\to$ `(18, 19, 24)` | Nền nửa phải (Phía Cơ thủ 2 / Vô Địch) |
| **Electric Sapphire Blue** | `#1E90FF` | `(30, 144, 255)` | Quầng sáng glow, vạch capsule gạch chân P1 |
| **Champagne Gold** | `#E5C158` | `(229, 193, 88)` | Đường laser 1px, viền thẻ, huy hiệu VS, quầng sáng P2 |
| **Cue Ball Pearl White** | `#FAFCFF` | `(250, 252, 255)` | Đèn báo lượt đánh bi cái, text tên chính |
| **YouTube Berry Red** | `#C32323` | `(195, 35, 35)` | Nền nút bấm Đăng ký kênh YouTube |
| **Frosted Dark HUD** | `#0E121A` | `(14, 18, 26, 235)` | Nền kính mờ 92% của bảng điểm Scoreboard |

### 2.2. Phông Chữ (Typography)
- **Font Gia Đình**: `Segoe UI Bold` / `Segoe UI SemiBold` / `Arial Bold` (hỗ trợ 100% tiếng Việt UTF-8 chuẩn).
- **Tên cơ thủ Hero**: `72pt Bold`, in hoa (`UPPERCASE`), căn lề đối xứng hướng về tâm.
- **Vạch gạch chân**: Capsule bar bo tròn 2 đầu (dày 6px, `radius=3px`), phủ kín 100% chiều dài tên.
- **Tỷ số Scoreboard**: `30pt Bold`, căn giữa ô điểm tương phản cao.

---

## 3. Đặc Tả Kỹ Thuật 3 Thành Phần Đồ Họa Master

### 3.1. Thẻ Mở Màn Thân Thiện (Intro Card - `template_3_intro_card.png`)
- **Kích thước**: `1920x1080` (Solid RGB).
- **Nền**: Chia đôi 50/50 kết hợp **Soft Ambient Glow** (Xanh sapphire bên trái, Vàng champagne bên phải, Hào quang ấm quanh huy hiệu VS).
- **Top Capsule Header (640x48px, radius=24px)**:
  - Bên trái: Pill vàng `[ ➒ POOL 9-BALL ]` với icon quả bi số 9 vàng 3D nổi bật.
  - Ở giữa: `CHẠM 7  •  RACE TO 7` (Song ngữ thể thao thân thiện).
  - Bên phải: Dấu chấm phân cách + Tên giải đấu in hoa.
- **Khu vực Tên Đấu Thủ**:
  - P1 (Bên trái): Căn phải về tâm, vạch gạch chân capsule xanh sapphire bo tròn 2 đầu phủ trọn 100% tên.
  - P2 (Bên phải): Căn trái từ tâm, vạch gạch chân capsule vàng champagne bo tròn 2 đầu phủ trọn 100% tên.
- **Huy hiệu VS Trung Tâm**:
  - Medallion đường kính 104px mạ vàng 2 tầng, vòng phát quang dịu ở tâm điểm `x=960, y=542`.
- **Chân Thẻ (Human-Centric Microcopy)**:
  - Thông điệp: `TRẬN ĐẤU RÚT GỌN  •  THEO DÕI TRỌN VẸN TỪNG CÚ ĐÁNH`.
  - Tag chất lượng: Pill nhỏ `[ 1080p 60FPS ]` uy tín.

---

### 3.2. Bảng Tỷ Số Phát Sóng (Scoreboard HUD - `template_3_scoreboard_preview.png`)
- **Kích thước Canvas**: `1920x1080` (RGBA trong suốt hoàn toàn).
- **Vị trí ghim cố định**: Góc trên bên trái: `x=50, y=40`. Kích thước cụm HUD: `600x88px`, bo góc mềm mại `radius=16px`.
- **Tầng 1 (Top Bar - 26px)**:
  - Bên trái: Pill vàng `[ ➒ POOL 9-BALL ]` có icon bi số 9.
  - Ở giữa: `RACE TO {N}`.
  - Bên phải: Pill trạng thái `[ VÁN 10 ]` (Dark Frosted viền vàng).
- **Tầng 2 (Symmetrical Head-to-Head Clash & Lượt Đánh Bi Cái)**:
  $$\text{[Blue Pip]} \quad \mathbf{[⚪]} \quad \text{CHUNG CHOO} \quad \mathbf{[\, 3 \,]} \quad \Big| \quad \mathbf{[\, 7 \,]} \quad \text{KHƯƠNG LIỀU} \quad \text{[Gold Pip]}$$
  - **Đèn báo bi cái (`⚪ Cue Ball Dot`)**: Hiển thị bên cạnh tên cơ thủ đang nắm quyền thi đấu (active striker), giúp khán giả biết ngay ai đang đánh trong 0.1s.
  - **Hai ô điểm số `[ 3 ]` và `[ 7 ]` đối xứng quay mặt vào giữa**: Kích thước `48x40px`, bo góc `radius=8px`, font 30pt tương phản cực cao trên nền tối, nhìn rõ trên mọi thiết bị di động.
- **Quy tắc nhảy điểm**: Giữ nguyên điểm số tĩnh, **CHỈ NHẢY ĐIỂM KHI BI 9 RƠI LỖ (`win_t`)**.

---

### 3.3. Thẻ Vinh Danh Kết Thúc (Outro Card - `template_3_outro_card.png`)
- **Kích thước**: `1920x1080` (Solid RGB).
- **Tôn Vinh Tinh Thần Thể Thao (Sportsmanship & Equal Dignity)**:
  - Bên Á Quân (Trái): Pill `[ 🥈 Á QUÂN  •  FINALIST ]` màu xanh bạc sapphire tôn trọng sự nỗ lực.
  - Bên Vô Địch (Phải): Pill `[ 🏆 VÔ ĐỊCH  •  CHAMPION ]` có **Icon Cúp Vàng 3D** mạ vàng lấp lánh!
  - Tâm điểm: Viên thuốc điểm số chung cuộc `3 - 7` (196x88px) tỏa sáng rực rỡ.
- **Thông Điệp Tri Ân Khán Giả & Nút Kêu Gọi Hành Động (CTA Button)**:
  - Dòng 1: `CẢM ƠN QUÝ KHÁN GIẢ ĐÃ ĐỒNG HÀNH & CỔ VŨ HAI CƠ THỦ` (25pt Bold trắng sáng).
  - Dòng 2: Nút bấm YouTube thân thiện dạng Pill đỏ bo tròn 22px:
    `[ 🔔  BẤM ĐĂNG KÝ KÊNH ĐỂ THEO DÕI CÁC TRẬN ĐẤU TIẾP THEO ]`

---

## 4. Code Runbook & Python API

AI Agent có thể tự động sinh bộ đồ họa và video clip thông qua hai cách:

### Cách 1: Gọi script độc lập
```bash
python scripts/make_swiss_assets.py
```

### Cách 2: Tích hợp vào Pipeline qua `IntroManager`
```python
from billiards_highlight_editor.intro_manager import IntroManager

manager = IntroManager(default_style=3)

# 1. Tạo Intro Card PNG & Render Clip MP4
manager.generate_intro_card_png(
    style_id=3,
    out_png_path="projects/my_match/assets/intro.png",
    p1_name="CHUNG CHOO",
    p2_name="KHƯƠNG LIỀU",
    tournament="CLB POOL 9-BALL",
    race_to=7
)
manager.render_intro_clip_nvenc("projects/my_match/assets/intro.png", "projects/my_match/assets/intro.mp4")

# 2. Tạo Scoreboard HUD PNG
manager.generate_scoreboard_png(s1=3, s2=7, out_png_path="projects/my_match/assets/sb_3_7.png", rack_label="VÁN 10")

# 3. Tạo Outro Card PNG & Render Clip MP4
manager.generate_outro_card_png("KHƯƠNG LIỀU", "CHUNG CHOO", 7, 3, "projects/my_match/assets/outro.png")
manager.render_outro_clip_nvenc("projects/my_match/assets/outro.png", "projects/my_match/assets/outro.mp4")
```
