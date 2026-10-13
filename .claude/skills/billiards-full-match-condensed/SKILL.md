---
name: billiards-full-match-condensed
description: >-
  Cắt toàn bộ trận Pool 9 bi (video gốc 1–2 tiếng) thành bản "Full Match Condensed" cho YouTube 16:9 theo CÔNG THỨC CHỐT V5c:
  nhận diện bằng chuyển động trong lòng nỉ (không dùng âm thanh, vì tiếng bi to là của bàn khác), mỗi cú lấy 3 s trước và đến khi
  bi dừng hẳn + 2 s, giữ nguyên mọi cú kể cả cú trượt, `audit --restore` tự giữ lại các mối cắt làm đổi bàn, zoom 1.3x vào bàn,
  bảng tỷ số Swiss style cố định (nhảy điểm khi bi 9 rơi, nhãn MATCH POINT / HILL-HILL), fade ngắn tại mối cắt, intro và outro.
  Dùng khi người dùng muốn bản đầy đủ nhưng rút gọn, không phải highlight 60 giây/ván.
---

# Billiards Full Match Condensed

Mỗi trận là một project riêng `projects/YYYY-MM-DD_<P1>_vs_<P2>/` gồm `raw/ assets/ output/ temp/ analysis/ match_metadata.json`.
Không để file ở thư mục gốc. `analysis/` là cache, giữ lại để chỉnh ngưỡng mà không phân tích lại.

Code: `billiards_highlight_editor/condensed.py` (+ `condensed_swiss.py`, `condensed_cards.py`, `condensed_seo.py`). Đây là chế độ khác với
highlight 60 giây/ván: ở đây **giữ mọi cú chọc** (kể cả trượt và phòng thủ), chỉ cắt khoảng giữa các cú.

## CÔNG THỨC CHỐT: V5c (dùng cái này, bỏ qua quy trình âm thanh cũ ở các mục sau)

Người dùng chốt công thức này ngày 13/10/2026 sau khi so V3 (âm thanh), V4/V4b (âm thanh + công thức v2), V5/V5b/V5c (chuyển động). Trận mẫu race to 3: V5c = 32.6 phút, giảm 27.7 % so với 45.1 phút gốc.

| Phần | Giá trị V5c | Ghi chú |
|---|---|---|
| Nhận diện | **chỉ chuyển động trong lòng nỉ** (đa giác 4 góc), `plan --motion` | Không dùng âm thanh (tiếng chọc to là của bàn khác) |
| Bắt đầu hoạt động | `--move-energy 0.4` | % điểm ảnh nỉ đổi; cú nhẹ ở xa chỉ 0.4–0.7 %, ngưỡng 1.0 từng bỏ sót bi 7 |
| Còn hoạt động | `--move-low 0.2` | bi lăn chậm, người ngắm/đi trên bàn vẫn giữ clip |
| Hết hoạt động | `--move-gap 2.0` | bàn yên liên tục 2 s |
| Đệm | `--pre-roll 3 --tail 2 --merge-gap 0` | 3 s trước, 2 s sau, hai clip chồng nhau thì nối |
| Kiểm tra mối cắt | `audit --restore` | cắt nào làm bàn đổi ≥ 200 điểm ảnh thì giữ lại cả đoạn (tối đa 30 s) |
| Hình | `--zoom 1.3 --zoom-center cx,cy` | tâm = giữa cả bàn kể cả thành bàn (đo bằng `roi`) |
| Chuyển cảnh | mặc định: fade hình 0.15 s + fade tiếng 0.20 s | không room tone |
| Bảng điểm | Swiss, nhãn `MATCH POINT` / `HILL-HILL` / `FINAL`, tiếng click khi nhảy điểm | |
| Không dùng | `--drop-misses`, thuật toán âm thanh, `--shot-cap`, `--room-tone` | giữ mọi cú |

```bash
P=projects/<tên>   # cùng thư mục project: raw/ analysis/ output/ ...
# 0. đo vùng bàn và tâm zoom (xem mục Quy trình bước 0), mở analysis/roi_preview.jpg và zoom_preview.jpg
python -m billiards_highlight_editor.condensed roi --project $P --source raw/part1.mp4 --at 495 --table-roi X,Y,W,H --zoom 1.3 --zoom-center CX,CY
# 1. phân tích (lần đầu giải mã cả video ~5 phút/file, cache analysis/motion_felt_*.npy). --sources đúng thứ tự thời gian
python -m billiards_highlight_editor.condensed plan --project $P --sources raw/part1.mp4 raw/part2.mp4 --p1 "..." --p2 "..." --race-to N \
  --table-roi X,Y,W,H --motion --pre-roll 3 --tail 2 --merge-gap 0 --move-energy 0.4 --move-low 0.2 --move-gap 2.0 \
  --breaks "..." --wins "t/e,..." --winners P1,P2,...
# 2. mở analysis/contact_sheet.jpg xác nhận cú phá / bi 9 rơi từng ván (xem mục Tìm mốc)
# 3. kiểm tra mối cắt và tự giữ lại các mối bị cờ (chạy SAU plan/racks, TRƯỚC render)
python -m billiards_highlight_editor.condensed audit --project $P --handshake 1 --restore
# 4. render
python -m billiards_highlight_editor.condensed render --project $P --handshake 1 --zoom 1.3 --zoom-center CX,CY --out Condensed_RaceToN_<P1>_vs_<P2>.mp4
```

- **Thứ tự bắt buộc:** `plan`/`racks` dựng lại `clips.json` từ kết quả phát hiện và **xóa mọi `--restore` trước đó**; luôn chạy `audit --restore` lại sau chúng, rồi mới `render`. Bản sao `analysis/clips_before_restore.json` giữ trạng thái trước khi giữ lại.
- **`audit --restore` làm gì:** đóng mối cắt bị cờ bằng cách kéo dài clip trước đến đầu clip sau (hai clip liền nhau nên không fade); cắt giữa hai file thì giữ phần cuối file 1 và phần đầu file 2. Mối cắt dài hơn `--restore-max` (30 s) chỉ báo cáo. Mối cắt giữa hai ván (xếp bi cắt chủ ý) không bao giờ bị cờ.
- **Đa giác nỉ** mặc định suy từ `table_roi` (`FELT_REL`, đo trên camera của trận mẫu); camera khác phải kiểm lại bằng `roi` (khung xanh phải ôm đúng lòng nỉ) hoặc đặt `felt_polygon`.
- **Chưa kiểm chứng:** V5c mới được xem kỹ ở vài đoạn của race to 3 (cú bi 8 ở 357–384 s, cú bi 7 ở cuối file 1/đầu file 2); `audit` chỉ bắt các mối cắt làm đổi bàn, không bắt cú bị cắt mà bàn trước/sau giống nhau.

## Yêu cầu đã chốt từ người dùng

> Yêu cầu 2 và 3 (nhận diện cú bằng âm thanh, lùi -2.0 s) **đã được thay bởi yêu cầu 20** và công thức V5c ở trên (chuyển động trong lòng nỉ, 3 s trước / 2 s sau). Yêu cầu 13 (`--drop-misses`) đã bỏ.

Đây là những gì người dùng đã yêu cầu. Khi sửa hay mở rộng skill, không được làm mất các điểm này.

1. **Nền tảng YouTube, 16:9**, bản đầy đủ nhưng rút gọn (không phải highlight 60 giây/ván).
2. **Phát hiện cú chọc bằng âm thanh** (tiếng đầu cơ chạm bi hoặc bi chạm bi), **lùi N giây** trước điểm âm thanh để giữ nhịp ngắm
   (N = `pre_roll_sec`, mặc định **4.0 s**; trước đây -2.0 s bị cắt mất phần ngắm). Chỉnh bằng `--pre-roll`.
3. **Phát hiện kết thúc cú đánh bằng chuyển động hình ảnh**: khi vận tốc các bi về 0, hoặc khoảng 1 giây sau khi bi rơi lỗ.
   **Không được cắt cuối cú đánh**: phải giữ từ lúc ngắm, đến lúc bi chủ chạm bi mục tiêu, đến khi mọi bi dừng hẳn (xem yêu cầu 16).
4. **Nối các clip bằng FFmpeg, render GPU NVENC.**
5. **Bảng tỷ số giữ nguyên vị trí**, chỉ nhảy điểm khi bi số 9 rơi lỗ.
6. **Dùng template Swiss style** (`templates/swiss_style/`) cho bảng điểm và các thẻ đồ họa.
7. **Có intro và outro.**
8. **Phải bỏ các đoạn xếp bi thừa** (nhặt bi, xếp bi giữa hai ván) khỏi video. Người dùng đã phản hồi khi bản đầu còn sót đoạn này.
9. **Quy trình kiểm tra:** chạy thử race to 3 trước để người dùng xem, sau đó render đủ trận (race to 7, 10 ván, 3-7).
10. **Cách làm việc:** dùng subagent cho các việc độc lập để nhanh hơn; khi người dùng hỏi thời gian thì báo ước lượng (kèm lý do nếu có rủi ro kéo dài).
11. Mọi file của trận nằm trong thư mục project của trận đó.
12. **Tiêu đề và mô tả chuẩn SEO cho YouTube** được sinh tự động cùng video (xem mục "YouTube: tiêu đề, mô tả, thẻ").
13. ~~Bỏ cảnh bi mục tiêu bắn mãi không vào (`--drop-misses`).~~ **Không dùng nữa (người dùng bỏ yêu cầu này, 13/10/2026).** Sau khi xem bản render, người dùng thấy video bị cắt quá đà,
    nên **không chạy `--drop-misses`**, giữ mọi cú chọc kể cả cú trượt. Mã vẫn còn trong `condensed.py` nhưng không nằm trong quy trình.
14. **Mỗi lần thay đổi thuật toán, quy trình hay phát hiện lỗi mới đều phải ghi vào SKILL.md ngay** (kể cả cách đã thử và không dùng được) để lần sau không mắc lại.
    Khi thêm một lệnh/cờ mới, ghi luôn cách dùng và rủi ro đã biết.
15. **Không hiển thị chữ phụ/quảng bá** (khẩu hiệu, "bản rút gọn chỉ giữ các cú đánh", lời cảm ơn, nút đăng ký, câu giới thiệu bản dựng) trong video lẫn mô tả YouTube.
    Chỉ giữ thông tin thật: tên cơ thủ, race to, tỷ số, địa điểm/ngày nếu có, mục lục. Khi thêm đồ họa hay mô tả mới, không thêm câu chữ kiểu này.
16. **Giữ trọn mỗi cú đánh: ngắm bắn → bi chủ chạm bi mục tiêu → mọi bi dừng hẳn** (người dùng, 13/10/2026: bản render hay bị mất phần **cuối** cú đánh).
    Ưu tiên giữ dư hơn cắt thiếu: khi chỉnh ngưỡng, nghiêng về phía clip dài hơn.
18. **Zoom gần hơn vào bàn một khoảng hợp lý** (người dùng, 13/10/2026): bản render đầu để toàn cảnh, bàn nhỏ. Zoom tĩnh `zoom` = **1.3x** (camera cố định), cắt quanh tâm `table_roi`,
    chỉ áp khi render (phân tích `plan` vẫn trên toàn khung). Bảng tỷ số vẽ sau khi cắt nên không bị zoom. Chỉnh bằng `render --zoom N` (1 = tắt).
    **Bàn phải nằm giữa khung hình và còn nguyên cả bàn** (người dùng, 13/10/2026): tâm zoom là tâm của **cả bàn gồm thành bàn** (`--zoom-center cx,cy`), không phải tâm vùng nỉ `table_roi`
    (ROI chỉ ôm mặt nỉ nên lệch ~40 px). Kiểm tra bằng `roi --zoom 1.3 --zoom-center cx,cy` rồi mở `analysis/zoom_preview.jpg` (cùng bộ lọc ffmpeg với lúc render).
    Cách đo: vẽ lưới tọa độ lên một khung gốc, đọc mép trái/phải/trên/dưới của bàn, lấy trung điểm. Trận 1012.mp4: bàn x 560–1345, y 535–855 → tâm `952,690`.
    So thử trên 1012.mp4: 1.5x đã cắt cơ/tay của người đứng cạnh bàn, 1.3x còn đủ người và bàn lớn rõ rệt.
19. **Phong cách tổng hợp: condensed cả trận + nhịp phát sóng của công thức highlight** (`cong_thuc_cat_got_video_9_ball.md`, người dùng yêu cầu merge 13/10/2026).
    Lấy từ công thức những gì **không mâu thuẫn** với yêu cầu 2/3/15/16, bỏ phần còn lại (xem mục "Phong cách tổng hợp" bên dưới).
20. **Không dùng âm thanh để nhận diện cú đánh** (người dùng, 13/10/2026: *tiếng bi to là của bàn khác lọt vào video*). Dùng `plan --motion`: chỉ đo chuyển động **trong lòng nỉ**
    (không phải cả bàn), mỗi đoạn hoạt động lấy **3 s trước và 2 s sau** (`--pre-roll 3 --tail 2`), chuyển động lại trong khoảng đó thì nối liền. Chi tiết ở mục "Chế độ chuyển động".
17. **Chuyển cảnh không giật, tự nhiên** (người dùng, 13/10/2026): tại mỗi mối cắt thật giữa hai clip có fade hình ngắn (0.15 s) và fade tiếng (0.20 s) mỗi bên.
    Bảng tỷ số **không** bị fade (cố định, vẫn nằm yên khi hình mờ). Không fade ở chỗ hai clip liền nhau của cùng một nguồn.

## Thuật toán âm thanh (CŨ, không dùng nữa: tiếng bi to là của bàn khác; giữ làm tài liệu)

1. **Strike Trigger (âm thanh).** Lọc dải 1–8 kHz, lấy đỉnh trên noise floor cục bộ (+18 dB). Một đỉnh chỉ là cú chọc nếu
   **1.5s trước đó yên lặng**. Tiếng bi-bi, băng, lỗ sau đó thuộc cùng cú, không tạo clip mới.
2. **Lùi `pre_roll_sec` = 4.0s** trước cú chọc (cú phá: 4.5s để thấy đủ 9 bi hình thoi). Từng là 2.0s, bị mất phần ngắm.
3. **End Trigger (hình ảnh).** Chỉ đọc video quanh các cú ứng viên, 480p, 10 fps. Cú không thể kết thúc trước `min_run_sec` = **3.0s** sau cú chọc
   (để bi chủ chậm vẫn kịp chạm bi mục tiêu). Sau đó cú kết thúc khi mặt bàn yên (`still_energy` = **0.25**) liên tục ≥ `min_still_sec` = **1.0s**
   **và** không có tiếng mới; cộng `tail_sec` = **1.5s** đệm. Trần 25s. Cú không có chuyển động bi (chạm cơ, đặt bi) bị loại.
   Giá trị cũ (0.8s / 0.5s / 0.35 / 1.0s) bị nghi làm cắt cuối cú đánh khi bi lăn chậm [chưa đo được].
4. **Gộp** hai clip cách nhau <1.5s (một lượt run-out thành một đoạn liền).
5. **Ván và bảng điểm.** Cú phá và thời điểm bi 9 rơi (`win_t`) **do người xem ảnh xác nhận** (xem mục Giới hạn). Người thắng từng ván cũng do
   người dùng xác nhận. Bảng điểm nhảy đúng tại `win_t` bằng hai overlay PNG đổi nhau theo `enable='lt(t,..)'/'gte(t,..)'`.
6. **Bỏ xếp bi.** Clip cuối của mỗi ván bị cắt tại điểm `e` (lúc người chơi bắt đầu đặt bi lại lên bàn), mọi clip sau đó của ván đó bị bỏ.
   Ván sau bắt đầu từ cú phá (lùi 4.5 s) nên đoạn nhặt bi và xếp bi không còn trong video.
7. **Render.** Mỗi clip một lệnh FFmpeg (GPU nếu có) kèm overlay bảng điểm PNG, ép stereo, **fade hình 0.15 s + fade tiếng 0.20 s tại mỗi mối cắt thật** (`join_video_fade_sec`, `join_audio_fade_sec`; hình chỉ mờ phần video dưới bảng điểm, cạnh liền mạch chỉ fade tiếng 30 ms chống tiếng lách tách), rồi nối bằng
   concat `-c copy` và chuẩn hóa âm lượng -14 LUFS. Xuất `chapters.txt` cho phần mô tả YouTube.

### Đồ họa Swiss style

- **Bảng điểm** (mặc định) theo template **Swiss Split Ultra-Clean** (`templates/swiss_style/SWISS_STYLE_GUIDE.md`, code vẽ ở `condensed_swiss.py`):
  thẻ 590x84 ghim góc trên trái (50,40), tầng trên `POOL 9-BALL | RACE TO N | VÁN X` (hiện `FINAL` khi có người chạm race-to),
  tầng dưới `[pip xanh] P1 [S1] | [S2] P2 [pip vàng]`. Tên in hoa, tự thu nhỏ chữ nếu quá dài. `--style classic` quay về bảng điểm cũ.
- **Intro/outro mặc định BẬT** (`condensed_cards.py`, nền chia đôi 50/50, đường laser vàng, xanh sapphire / vàng champagne `#E5C158`).
  Intro 4 s: tên 2 cơ thủ, `RACE TO N`, `POOL 9-BALL`, thêm địa điểm nếu có `--venue`.
  Outro 6 s: tỷ số chung cuộc lớn, người thắng tô vàng kèm nhãn `VÔ ĐỊCH • CHAMPION`, người thua `Á QUÂN • FINALIST`.
  Tỷ số và người thắng lấy từ ván cuối được giữ trong `racks.json`; nếu chưa ai chạm race-to thì chỉ hiện tỷ số.
  Thẻ chỉ có thông tin thật (tên, race to, ngày nếu có, tỷ số): **không có khẩu hiệu dưới intro, lời cảm ơn hay nút đăng ký ở outro** (yêu cầu 15).
  Thẻ vẽ bằng tên/race-to thật của project (không dùng `IntroManager`, vì nó vẽ cứng tên cố định). Fade 0.4 s, âm im lặng, mã hóa cùng
  thông số với clip thường để nối được bằng concat `-c copy`. Ảnh thẻ lưu ở `assets/intro_card_condensed.png`, `assets/outro_card_condensed.png`.

## Quy trình (bản âm thanh cũ; quy trình chốt ở mục "CÔNG THỨC CHỐT: V5c" phía trên)

```bash
# 0. Kiểm tra vùng mặt bàn. Nếu báo FALLBACK (không tự nhận ra nỉ, hay gặp với nỉ xám/xanh nhạt) → đo x,y,w,h trên ảnh gốc
python -m billiards_highlight_editor.condensed roi --project projects/<tên> --source raw/part1.mp4 --at 15 --table-roi 620,520,740,290 --zoom 1.3 --zoom-center 952,690
#    mở analysis/roi_preview.jpg: khung đỏ phải ôm mặt nỉ, càng ít nền/người càng tốt
#    mở analysis/zoom_preview.jpg: cả bàn phải nằm giữa khung hình, không bị cắt (chỉnh --zoom-center nếu lệch)

# 1. Phân tích. --sources theo ĐÚNG thứ tự thời gian (không dùng sắp xếp tên: "1012(1).mp4" đứng trước "1012.mp4")
python -m billiards_highlight_editor.condensed plan --project projects/<tên> --sources raw/part1.mp4 raw/part2.mp4 --race-to 7 --table-roi 620,520,740,290

# 2. Xác định cú phá và lúc bi 9 rơi của từng ván (bằng ảnh, xem mục "Tìm mốc"), rồi áp dụng. `racks` luôn bắt đầu từ
#    analysis/clips_auto.json nên chạy lại bao nhiêu lần cũng được.
python -m billiards_highlight_editor.condensed racks --project projects/<tên> \
  --breaks "31.92,497.35,1069.8,1671.9,2211.1,1:81.2,1:674.56,1:1032.2,1:1643.3,1:2028.0" \
  --wins   "448.5/450,1032.5/1034,1638.5/1640,2160.5/2162,1:23.5/26,1:624.5/627,1:997.5/1000,1:1607.5/1610,1:1943.5/1946,1:2519/2521" \
  --winners P1,P1,P2,P2,P2,P2,P2,P2,P1,P2 --race-to 7
#    --breaks: giây (nguồn 0) hoặc "nguồn:giây". Cú phá nằm trong clip dài bắt đầu từ ván trước thì phần đầu được giữ cho ván trước
#              (clip tách đôi). Cú phá chưa có clip nào (bị bỏ sót) sẽ được dựng thêm.
#    --wins "t/e": t = bi 9 rơi (bảng điểm nhảy), e = cắt clip cuối của ván tại đó. Từ e đến cú phá ván sau bị bỏ hoàn toàn.
#                  Không có /e thì clip cuối kết thúc tại t + 1 s. Nếu clip phát hiện được kết thúc trước t thì được kéo dài đến e.
#    --winners: người thắng từng ván theo thứ tự. Ván sau khi chạm race-to (show match) tự bị loại.

# 3. Mở analysis/contact_sheet.jpg: mỗi ván 3 ô = [trước cú phá] [+3s sau cú phá] [sau mốc win_t]
#    Ô 1 phải thấy 9 bi hình thoi nguyên vẹn, ô 2 phải thấy bi đã bung, ô 3 phải thấy bàn gần như trống. Sai thì sửa mốc ở bước 2.

# 4. Render
python -m billiards_highlight_editor.condensed render --project projects/<tên> --handshake 1
```

Các cờ `render`: `--style classic` (bảng điểm cũ), `--venue "..."` (địa điểm trên intro), `--no-intro`, `--no-outro`, `--intro-sec N`, `--outro-sec N`
(0 = tắt), `--channel`, `--date`, `--tournament`, `--no-youtube`, `--handshake N`, `--out NAME` (giữ N giây sau cú cuối của trận, mặc định 20; đặt 0–1 nếu ván show đã bắt đầu xếp bi ngay), `--workers`, `--keep-temp`, `--no-score-sfx`, `--room-tone`, `--zoom N` (mặc định 1.3, 1 = tắt), `--zoom-center cx,cy` (lưu vào `clips.json`, lần render sau tự dùng lại), `--no-fade` (cắt cứng như cũ), `--fade-video N`, `--fade-audio N` (giây).

Kết quả: `output/Condensed_RaceTo<N>_<P1>_vs_<P2>_Full.mp4` + `output/chapters.txt` (đặt `--out` để đổi tên file, nên dùng tên không dấu).
`chapters.txt` chỉ có các chương `Ván N: P1 a - b P2`; intro nằm trong chương ván 1 (bắt đầu `0:00`) và outro trong chương ván cuối,
vì chương 4–6 giây ngắn hơn mức tối thiểu 10 giây mà YouTube được cho là yêu cầu [chưa kiểm chứng]. `separate_cards=True` trong `build_chapters`
thêm `0:00 Intro` và `Kết quả`. `temp/condensed_clips/` tự xóa sau render.

### Tìm mốc (cú phá, bi 9 rơi, bắt đầu xếp bi)

Hiện chưa có cách tự động đáng tin, nên xác định bằng ảnh. Cách đã dùng và cho kết quả đúng:

1. **Cú phá:** quét từng 2 giây, so khớp mẫu (`cv2.matchTemplate`, `TM_CCOEFF_NORMED`) giữa một frame có hình thoi nguyên vẹn và vùng chân bàn.
   Khoảng có điểm ≥0.6 là lúc rack đứng; cú phá là tiếng to đầu tiên ngay sau đó (tìm bằng `strike_candidates` trên đoạn âm thanh ngắn).
   Xác nhận: frame trước cú phá có hình thoi, frame sau 3 giây bi đã bung.
2. **Bắt đầu xếp bi:** xem frame mỗi 5 giây trong khoảng trước hình thoi của ván sau. Bàn còn 2 bi (bi chủ + bi 9), rồi bi 9 mất,
   rồi bi xuất hiện thành cụm trên bàn (người chơi đặt bi lại). Đó là mốc `e` (trừ 1–2 giây); `t` ≈ `e` - 3.
3. **Người thắng:** đối chiếu với bảng điểm vật lý trên tường trong video (đọc được bằng mắt, ví dụ 2-0, 2-3, 3-6).

## YouTube: tiêu đề, mô tả, thẻ

`render` ghi thêm hai file vào `output/` (tắt bằng `--no-youtube`); lệnh `seo` tạo lại cho project đã render mà không phải render lại:

```bash
python -m billiards_highlight_editor.condensed seo --project projects/<tên> --channel "Tên kênh" --venue "CLB ..." --tournament "Giao lưu ..." --date 2026-10-12
```

- `youtube_metadata.md`: tiêu đề (kèm số ký tự, bản không lộ kết quả, các phương án khác), mô tả, thẻ (kèm tổng ký tự), hashtag, danh sách cần kiểm tra.
- `youtube_description.txt`: mô tả thuần văn bản để dán thẳng vào YouTube Studio.
- Code: `billiards_highlight_editor/condensed_seo.py`. Chỉ dùng dữ kiện có thật (cơ thủ, race to, tỷ số, chương, thời lượng, ngày từ tên thư mục project,
  và `--venue/--channel/--tournament` nếu có). Thiếu dữ kiện thì bỏ dòng đó, không bịa; file md liệt kê phần còn thiếu.

Quy tắc SEO đã áp dụng (theo hiểu biết chung về YouTube, **chưa đối chiếu lại tài liệu chính thức**):

| Phần | Quy tắc |
|---|---|
| Tiêu đề | Từ khóa chính đứng đầu: `P1 vs P2 \| Pool 9 Bi Race to N (a-b) \| Full Rút Gọn`; ưu tiên ≤70 ký tự, tối đa 100. Có bản không ghi tỷ số cho người không muốn lộ kết quả |
| Mô tả | Câu đầu ≤150 ký tự mang từ khóa (cơ thủ, thể thức, kết quả) vì chỉ phần này hiện trước "Xem thêm"; sau đó thông tin trận (cơ thủ, thể thức, kết quả, và địa điểm/ngày/kênh nếu có), mục lục chương, hashtag ở cuối. **Không có câu giới thiệu hay kêu gọi đăng ký** |
| Mục lục | Dán nguyên `chapters.txt` (bắt đầu `0:00`, mỗi ván một dòng) |
| Hashtag | Tối đa 5, không dấu, không khoảng trắng; 3 cái đầu (`#Pool9Bi #Bida #Billiards`) hiện trên tiêu đề, sau đó tên hai cơ thủ |
| Thẻ | Tên hai cơ thủ và "P1 vs P2" trước, rồi từ khóa bida/pool 9 bi/race to N; tổng ≤500 ký tự |

Tiêu đề có tỷ số là lựa chọn mặc định để tăng khả năng tìm kiếm; dùng `title_no_score` nếu muốn tránh lộ kết quả.

## Lọc cú trượt (`--drop-misses`): KHÔNG DÙNG NỮA

**Người dùng đã bỏ yêu cầu 13 (13/10/2026): không chạy `--drop-misses` trong quy trình.** Phần dưới giữ lại làm tài liệu về những gì đã thử và đo được.
Khi chạy lại `racks` không kèm cờ này, mọi clip tự về `skip=false`.

Cách bật (không còn dùng) trên lệnh `racks` (chạy sau `--breaks/--wins/--winners`, chỉ xét các ván được `include`):

```bash
python -m billiards_highlight_editor.condensed racks --project projects/<tên> ... --drop-misses
# xem analysis/dropped_sheet.jpg (ảnh trước/sau của từng clip bị bỏ) và analysis/dropped_clips.json
```

- **Nguyên tắc: thận trọng, chỉ bỏ khi chắc chắn không có bi nào rời bàn.** Mỗi clip một cú (`n_strikes == 1`) được đếm bi trên mặt nỉ trước cú (5 mẫu cách 1.5 s)
  và sau cú (5 mẫu), lấy trung vị; bỏ chỉ khi **số bi tăng ≥1** (bi vào lỗ làm số bi giảm, nên số bi tăng nghĩa là không có bi nào vào lỗ).
  Số bi giảm, bằng nhau hoặc thiếu mẫu thì **giữ**.
- **Luôn giữ:** cú phá, run-out (clip ≥2 cú), clip chạm trần 25 s, clip cuối của ván, và mọi clip trong 45 s cuối trước `win_t` (đoạn chơi bi 9, `nine_window_sec`).
- Clip bị bỏ không bị xóa khỏi `clips.json`: chỉ đặt `skip=true` + `skip_reason`; `render` bỏ qua chúng (trừ clip chứa điểm nhảy bảng điểm và clip cuối ván).
  `racks` luôn đặt lại `skip=false` rồi tính lại, nên chạy lại không tích lũy.
- Bộ đếm bi: `count_balls` (so màu với nỉ cục bộ bằng median 51 px, blob 90–420 px, gần tròn). **Nhiễu ±1–2 bi**, nên chỉ dùng chênh lệch trung vị và ngưỡng `miss_diff_min=1`.
  Hệ quả: **recall thấp** (bỏ được ít cú trượt), đổi lại ít bỏ nhầm cú vào lỗ. Chưa đo độ chính xác trên nhiều trận.
- Ngưỡng nằm trong `CondensedConfig`: `miss_diff_min`, `miss_min_before`, `nine_window_sec`, `count_step_sec`, `count_samples`, `count_min_samples`, `count_occlusion_max`.
- **Cổng "người che bàn" đã tắt (`count_occlusion_max=1.0`).** Bản đầu đặt 0.12 và loại gần hết mọi frame: phần diện tích "khối lớn" trong vùng nỉ luôn ở mức 0.17–0.22
  (do bóng/rãnh nỉ), kể cả khi bàn trống, và còn thấp hơn (0.10) khi người đứng chắn phía trước, nên không dùng để phát hiện người được. Hậu quả: 0/63 clip đủ mẫu, bộ lọc bỏ 0 clip.
  Số liệu đếm lưu ở `analysis/ball_counts.json` để chỉnh ngưỡng mà không đếm lại.
- **Kết quả thử trên race to 3 của trận mẫu (5 ván, 24.0 phút):** đếm 63 clip, 53 đủ mẫu, bỏ **13 clip (2.5 phút)**, còn 21.5 phút; video 21.6 phút gồm intro/outro.
  Xem ảnh `dropped_sheet.jpg` thì phần lớn là cú bi không vào hoặc cảnh người đi lại; một số clip có số bi "tăng" 2–3 (3→6) là do bộ đếm nhiễu
  khi người che bàn lúc trước cú, nên **vẫn có nguy cơ bỏ nhầm**. Cần người xem lại ảnh các clip bị bỏ trước khi dùng cho bản chính thức.
- **Kết quả trên race to 7 của trận mẫu (10 ván):** bỏ **25 clip (5.1 phút)**, còn 41.2 phút chơi; video 41.4 phút (bản không lọc: 46.5 phút). Số clip bỏ theo ván:
  1:1, 2:3, 3:3, 4:3, 5:3, 6:6, 8:4, 10:2 (ván 7 và 9: 0). Đếm bi mất khoảng 6 phút, render 8.5 phút, tổng 12.3 phút. Lệnh: `racks ... --drop-misses` rồi
  `render --handshake 1 --out Condensed_RaceTo7_..._MissFilter.mp4` (không có `--no-youtube` nên `youtube_*` được ghi lại theo chương của bản lọc; `chapters.txt` cũ vẫn thuộc bản không lọc).
  Lệnh đã chạy: `racks ... --race-to 3 --winners P1,P1,P2,P2,P2 --drop-misses`, rồi `render --handshake 1 --no-youtube --out Condensed_RaceTo3_..._MissFilter.mp4`.

### Các cách đã thử cho yêu cầu 13 và KHÔNG dùng được (đừng thử lại)

| Cách | Vì sao thất bại (đo trên trận 1012 mp4) |
|---|---|
| **Nhận ra người đánh đổi lượt** (hướng 3: cú trượt thì lượt chuyển sang người kia) | Mô hình MobileNet-SSD thấy người, nhưng không biết ai đang ngắm: cơ thủ đánh ở đầu bàn xa bị thu nhỏ/không nhận ra, màu áo bị tối đi khi cúi, người đứng chờ cũng có khung chồng lên bàn. Nhãn "ai đánh" sai nhiều nên sẽ bỏ nhầm cú vào lỗ |
| **Nghe tiếng bi rơi lỗ** (dải 80–500 Hz sau cú đánh) | Năng lượng thấp tần bị nhạc/tiếng quán chi phối, không có dấu hiệu riêng cho cú vào lỗ |
| **Đếm bi trên bàn rồi tìm bước giảm** (nền trung vị cả file hoặc một frame bàn trống) | Nhiễu ±1–2 bi ngang với tín hiệu (1 bi); khung "lớn" (người) xuất hiện ở hầu hết frame với nền cố định nên không lọc được frame sạch |
| **So khớp theo kênh bão hòa trong vùng chân bàn** | Chỉ phân biệt được rack đứng ở một số ván; báo nhầm khi còn vài bi |

Đã cài sẵn để thử hướng 3, **không còn dùng trong quy trình**: `models/` (MobileNet-SSD `mobilenet_iter_73000.caffemodel` ~22 MB + `deploy.prototxt`),
`.venv_detect/` (OpenCV 4.14 + numpy riêng, vì **OpenCV 5.0 của dự án đã bỏ bộ đọc Caffe**: `readNetFromCaffe` báo "Caffe importer has been removed")
và `billiards_highlight_editor/shooter_probe.py`. Có thể xóa cả ba nếu cần dọn chỗ. Nếu sau này cần mô hình khác, dùng định dạng ONNX hoặc chạy trong `.venv_detect`.

## Chạy thử race to N mà không làm hỏng bản đầy đủ

`analysis/clips.json` và `analysis/racks.json` dùng chung cho mọi lần render của project. Chạy thử race to 3 bằng `racks --race-to 3 --winners ...` sẽ **ghi đè** chúng
(các ván sau khi chạm race-to bị `include=false`). Quy trình đúng:

1. Sao lưu `analysis/clips.json`, `analysis/racks.json`, `analysis/clips_auto.json` ra chỗ khác (ví dụ thư mục scratch).
2. Chạy `racks` với `--race-to 3 --winners <5 ván đầu>` (vẫn truyền đủ `--breaks` và `--wins` của cả 10 ván: số `--wins` phải bằng số ván phát hiện được).
3. Render bằng `--out <tên riêng> --no-youtube` để không ghi đè video và `youtube_*` của bản race to 7. Chapters tự lưu thành `<tên>_chapters.txt`
   khi có `--out` (`chapters.txt` chỉ dành cho lần render không có `--out`).
4. **Khôi phục ba file đã sao lưu** rồi chạy lại `racks` với `--race-to 7` trước khi render bản đầy đủ. Quên bước này thì bản đầy đủ sẽ chỉ có 5 ván.

## Chế độ chuyển động (`plan --motion`, không dùng âm thanh)

```bash
python -m billiards_highlight_editor.condensed roi  --project projects/<tên> --source raw/part1.mp4 --at 495 --table-roi 620,520,740,290   # khung xanh phải ôm đúng lòng nỉ
python -m billiards_highlight_editor.condensed plan --project projects/<tên> --sources raw/part1.mp4 raw/part2.mp4 --race-to N   --table-roi 620,520,740,290 --motion --pre-roll 3 --tail 2 --merge-gap 0 --move-energy 1.0 --move-low 0.2 --move-gap 2.0 --breaks ... --wins ... --winners ...
```

- **Vì sao bỏ âm thanh:** quán có nhiều bàn, tiếng chọc to (-12 dB) hóa ra là của bàn khác; cú thật của bàn mình lại chỉ cao hơn nền ~19 dB. Cổng âm thanh vừa nhận nhầm, vừa bỏ sót cú.
  Tôi (Claude) từng thêm ngoại lệ "tiếng to thì hạ ngưỡng chuyển động" — **sai**, vì tiếng to lại hay là bàn khác; đã gỡ. Kiểm tra "bi bật chuyển động sau tiếng chọc" (`has_ball_onset`) còn trong mã cho chế độ âm thanh.
- **Đo trong lòng nỉ, không phải cả bàn:** đa giác 4 góc (`felt_polygon`, mặc định suy từ `table_roi` bằng `FELT_REL`, nới ngoài mép nỉ vài px cho bi sát băng). Cả `table_roi` ăn vào thành gỗ, chân người, người đứng mép bàn.
  Đo 10 phút đầu `1012.mp4`: năng lượng median cả bàn 0.89 % → trong nỉ 0.10 %; tiếng bàn khác 0.00 %; cú bi 8 trung bình 1.34 % (tối đa 3.8).
- **Thuật toán** (`clips_from_motion`, hai ngưỡng, sửa 13/10/2026 theo yêu cầu *bi cái dừng hẳn, đợi 2 s mới tính là hết; có người hoạt động trên mặt bàn vẫn giữ*):
  một hoạt động **bắt đầu** khi có một lúc mạnh (`move_energy` = 1.0 %) nhưng **kéo dài chừng nào lòng nỉ còn thay đổi** (`move_low_energy` = 0.2 %: bi lăn chậm, người đi/cúi ngắm trên mặt bàn);
  chỉ **hết** khi lòng nỉ yên liên tục `move_gap_sec` = **2.0 s**. Clip = [bắt đầu − 3 s, lần chuyển động cuối + 2 s]; hai clip chồng nhau thì nối. Chuyển động không bao giờ đạt 1.0 % (người lướt qua mép) bị bỏ.
  Bản một ngưỡng cũ (V5, 1.0 cho cả bắt đầu và kết thúc) coi bi lăn chậm là đã dừng.
  Chuỗi thời gian (cache `analysis/motion_felt_<nguồn>_<giới hạn>.npy`, giải mã cả video mất ~5 phút) nên chỉnh ngưỡng sau đó nhanh.
- **Quét ngưỡng** (10 phút đầu): 0.5 → giữ 73 %; 1.0 → 64 %; 1.5 → 58 %; 2.0 → 54 %. Ngưỡng cao làm mất đoạn ngắm (ở 1.0 clip bi 8 bắt đầu 365 s dù người nằm ngắm từ 362 s: đúng quy tắc 3 s trước).
- **V5b (hai ngưỡng, yên 2 s), race to 3:** 105 clip, **31.0 phút, giảm 31.3 %** (V5 một ngưỡng: 26.0 phút, 42.4 %). Cảnh hoạt động được giữ vẫn 84 % như V5 (phần còn lại là xếp bi/trước cú phá, chủ ý cắt);
  thời gian giữ mà cách xa mọi hoạt động > 5 s tăng 1.0 → 2.4 phút (8 %) vì người đứng loanh quanh bàn. Clip bi 8 (nguồn 357.3–384.4 s) liền một mạch từ người vào đến bi dừng. Ngưỡng 0.1 chỉ thêm ~3 %, 0.3 gần như bằng 0.2.
- **Kết quả race to 3 (V5):** 133 clip, **26.0 phút, giảm 42.4 %** so với 45.1 phút gốc; clip bi 8 (nguồn 364.8–374.5 s) có đủ ngắm → đánh → bi vào lỗ.
- **Hạn chế:** năng lượng đo bằng số pixel đổi nên cánh tay/cây cơ thò vào nỉ cũng là "hoạt động" (giữ đoạn ngắm, chấp nhận); khi người ngắm rất lâu và đứng yên, chỗ nghỉ > 5 s bị cắt giữa lúc ngắm (V5: 363.0 → 364.8 s).
  Đa giác nỉ đo trên một camera (ROI `620,520,740,290`), camera khác phải đo lại. Chưa thử ngưỡng 1.0 ngoài 10 phút đầu và toàn trận.
- **`audit` — kiểm tra các mối cắt (13/10/2026):** `python -m billiards_highlight_editor.condensed audit --project projects/<tên> --handshake 1` so **ảnh tĩnh lòng nỉ** ngay trước và ngay sau mỗi mối cắt (cắt ≥ `audit_min_gap_sec` = 3 s hoặc giữa hai file),
  đếm điểm ảnh khác nhau (xám, làm mờ 5x5, ngưỡng 30, mở 5x5, chỉ trong đa giác nỉ). ≥ `audit_diff_px` = **200** thì cắt đó bị cờ (có thể một cú/bi vào lỗ đã bị cắt). Cắt giữa hai ván (đoạn xếp bi cắt chủ ý) được liệt kê nhưng không cờ.
  Ra `analysis/gap_audit.json` và `analysis/gap_audit_sheet.jpg` (ảnh trước/sau, kèm mốc thời gian trong video). Mặc định chỉ báo cáo; thêm `--restore` để tự giữ lại (xem công thức chốt V5c).
  Vì sao không đếm bi: bộ đếm bi cũ cho số bi *tăng* ở 13/72 mối cắt (không thể xảy ra), nhiễu ±1–2 bi.
  Thử trên V5b: cắt bi 7 đã biết (nguồn 1: 2673.7 s → nguồn 2: 19.8 s) bị cờ với 221 px (sát ngưỡng; ngưỡng 400 sẽ bỏ sót). V5b có ~15 cắt bị cờ, V5c (ngưỡng bắt đầu 0.4 %) còn 7.
  Chưa xác nhận từng cắt bị cờ là thật (người che bàn hoặc ánh sáng cũng có thể làm đổi vài trăm điểm ảnh); cần người xem `gap_audit_sheet.jpg`.
- **Thử theo dõi riêng từng bi** (phát hiện chấm tròn, đo dịch chuyển): đúng với cú chậm (342–344 s), **bỏ sót cú bi chạy nhanh** (371.5–376 s) vì bi nhòe không còn tròn. Chưa dùng.

## Phong cách tổng hợp (condensed + công thức highlight)

Công thức `cong_thuc_cat_got_video_9_ball.md` là để dựng **highlight 3–5 phút**, nên chỉ dùng phần tương thích:

| Từ công thức | Quyết định | Lý do |
|---|---|---|
| Bảng điểm trên trái, cách mép 50 px, **chỉ nhảy khi bi 9 rơi** | Đã có | Khớp yêu cầu 5 |
| Nhãn **`HILL-HILL` / `MATCH POINT`** | **Thêm** (`rack_label_for(..., start_score)`) | Nhãn theo tỷ số lúc **bắt đầu ván**, hiện suốt ván; chạm race-to thì `FINAL`; race to 1 không có hill |
| **Tiếng click nhẹ khi điểm nhảy** | **Thêm** (`score_sfx`, mức đỉnh 0.25; `--no-score-sfx` để tắt) | Trộn bằng `sine` + `adelay` đúng `switch_local`; ffmpeg `sine` có biên độ mặc định 0.125 nên phải nhân 8 |
| Giữ thêm biểu cảm ở cú chốt | Đã có (`tail_sec`, `--handshake`) | Không cần thêm |
| Vào cảnh khi đã đặt cầu tay (1–1.5 s) | **Bỏ** | Ngược yêu cầu 2/16 (giữ nhịp ngắm, pre-roll 4 s) |
| Cắt ngay khi bi rơi lỗ | **Bỏ** | Ngược yêu cầu 16 (giữ tới khi bi dừng) |
| 3–4.5 s/cú, tổng 3–5 phút, chia 4 hồi | **Bỏ** | Khác mục tiêu (giữ mọi cú, chạy theo thời gian trận) |
| Slow-motion cho cú nhảy/masse/mỏng | **Chưa làm** | Cần bộ phân loại loại cú, chưa có |
| Nhạc nền + ducking | **Chưa làm** | Chế độ condensed không có nhạc nền; không ai yêu cầu cho bản này |
| Outro kêu gọi Subscribe | **Bỏ** | Ngược yêu cầu 15 |

## Lịch sử thay đổi thuật toán

- **13/10/2026 — chống cắt quá đà (người dùng review bản render, thấy mất cuối cú đánh).** `pre_roll_sec` 2.0→4.0, `min_run_sec` 0.8→3.0, `min_still_sec` 0.5→1.0,
  `still_energy` 0.35→0.25 (0.15 đã thử, tệ hơn), `tail_sec` 1.0→1.5; thêm cờ `plan --min-run`, `--min-still`, `--merge-gap`; bỏ `--drop-misses` khỏi quy trình.
  **Thử 600 s đầu `1012.mp4` (race to 3, ROI `620,520,740,290`):**

  | Cấu hình | Số clip | Thời lượng | Clip chạm trần 25s | Clip dài nhất |
  |---|---|---|---|---|
  | A: cũ (2.0 / 1.0 / 0.8 / 0.5 / 0.35) | 24 | 6.3 phút | 2 | 40 s |
  | B: mới, energy 0.35 | 14 | 8.3 phút | 4 | 108 s |
  | C/E: mới, energy 0.25 | 14 | 8.4 phút | 4 | 108 s |
  | F: mới, energy 0.15 | 15 | 8.7 phút | 5 | 97 s |
  | D: như B, `--merge-gap 0` | 15 | 8.3 phút | 4 | 108 s |

  - Cắt ít đi rõ rệt (6.3→8.4 phút trên 10 phút nguồn), đúng ý yêu cầu 16. Nhưng **các cú bắn liên tiếp cách nhau chỉ ~4 s bị gộp thành một clip dài 80–108 s**,
    vì `pre_roll` 4 s + `tail` 1.5 s phủ kín khoảng trống giữa hai cú. `--merge-gap 0` không đổi kết quả (gộp do chồng lấn, không phải do ngưỡng gộp).
  - `still_energy` 0.15 (F) chỉ thêm clip chạm trần và không kết thúc cú chính xác hơn, nên mặc định là 0.25 (0.25 và 0.35 gần như giống nhau ở đoạn thử).
  - **Không kiểm tra được bằng mắt** là cuối cú đánh đã giữ đủ hay chưa; chỉ so số liệu thời lượng. Cần người xem lại bản render.
  - Hệ quả: bản đầy đủ sẽ dài hơn bản cũ (bản cũ của trận mẫu: 46.5 phút), con số "15–25 phút" nêu trong các mô tả trước đây không còn đạt.
- **13/10/2026 — chuyển cảnh (cách 1: fade ngắn gắn vào từng clip, giữ `concat -c copy`).** `RenderItem.join_in/join_out` đánh dấu mối cắt thật
  (`build_render_plan`: hai clip cùng nguồn cách nhau ≤0.05 s thì không phải mối cắt). Fade hình áp lên video **trước** khi chồng bảng điểm. Kiểm tra bằng ffmpeg thật:
  frame đầu clip đen hoàn toàn, sáng lại sau ~4 frame (0.15 s), điểm sáng bảng tỷ số gần như không đổi. **Chưa đánh giá bằng mắt trên bản render đầy đủ.**
  Đây là "dip to black" ngắn, không phải dissolve; nếu vẫn thấy giật, cách tiếp theo là `xfade` + `acrossfade` (phải re-encode phần nối, không dùng `-c copy`; chưa làm).
  Các trường mới dùng tên riêng (`join_*`) vì `audio_fade_sec` đã lưu 0.03 trong `clips.json` của project cũ.
- **13/10/2026 — zoom 1.3x vào bàn** (`zoom_crop`): `crop` ffmpeg đặt trước `scale` và overlay. Tâm = giữa `table_roi` (1012.mp4: x=990, y=665 trên khung 1920x1080),
  kẹp trong khung; nếu project không có `table_roi` thì cắt giữa khung. Nguồn 1080p phóng 1.3x nên hơi mềm hơn một chút [chưa đo]. Chưa xem bằng mắt trên bản render đầy đủ,
  chỉ so 1 khung ở 1.0 / 1.3 / 1.5. Người đứng sát mép trái/phải của khung có thể bị cắt một phần.
- **Project cũ giữ cấu hình đã lưu** trong `analysis/clips.json` (`config`), nên đổi mặc định không ảnh hưởng chúng. Muốn áp dụng phải chạy lại `plan`
  (hoặc truyền `--pre-roll/--tail/--min-run/--min-still/--still-energy` thủ công), rồi chạy lại `racks` và `render`.

## Bài học khi chạy (đã gặp)

- **`racks` không giữ tên cơ thủ nếu bạn không truyền lại**: nay đã sửa để lấy tên/race-to đã lưu trong `racks.json`, nhưng vẫn nên truyền `--p1/--p2` ở lần chạy đầu. Render đầu tiên từng ra "P1 / P2".
- **Cú phá nằm trong clip dài**: đã tự tách clip (phần đầu thuộc ván trước). Nếu bỏ qua, mất cảnh cuối của ván trước.
- **Mốc bi 9 rơi tính theo tiếng cuối của clip luôn trễ** (dính cảnh xếp bi): luôn dùng `--wins "t/e"`.
- **Ước lượng mốc theo mẫu 5 giây lệch 2–3 s**: ván 10 từng đặt bi 9 rơi ở 2528 s trong khi người chơi đã đặt bi lại từ 2522 s; mốc đúng 2519 s. Xem frame từng 1–2 s quanh mốc cuối.
- **Đoạn bắt tay sau cú cuối** (`--handshake`, mặc định 20 s) có thể dính cảnh xếp bi của ván show: đặt 0–1 khi người chơi xếp bi ngay.
- **Đường dẫn file ra có dấu tiếng Việt** gây rắc rối khi dán/đọc: dùng `--out` không dấu.
- **Bash trên Windows**: không truyền chuỗi nhiều dòng chứa `
` bằng heredoc không có dấu nháy; ghi script ra file rồi chạy. Với `Edit`, không dán `
` thành xuống dòng thật vào chuỗi Python.

## Chỉnh khi kết quả chưa đúng

| Triệu chứng | Cách xử lý |
|---|---|
| Nhiều clip chạm trần 25s (log báo `hit max_clip_sec`) | tăng `--still-energy` (mặc định 0.25), hoặc thu hẹp `--table-roi`. Hạ `still_energy` xuống 0.15 làm hiện tượng này nhiều hơn (đã đo, xem Lịch sử) |
| Clip cắt sớm / mất cuối cú đánh khi bi còn lăn chậm | giảm `--still-energy`, tăng `--min-still` (mặc định 1.0), `--min-run` (3.0), `--tail` (1.5) |
| Mất phần ngắm đầu cú | tăng `--pre-roll` (mặc định 4.0). Lùi sớm hơn thì khoảng trống giữa hai clip nhỏ đi nên nhiều cú bị gộp (video dài hơn) |
| Có clip toàn tiếng chạm cơ, không có cú đánh | tăng `--min-motion` (mặc định 1.0) |
| Thiếu hoặc thừa số ván | `--breaks` (chính xác nhất). `--break-percentile` chỉ chỉnh được phần tự động |
| Bảng điểm nhảy sớm/trễ, hoặc còn cảnh xếp bi cuối ván | sửa `t` / `e` trong `--wins`, chạy lại `racks` rồi `render` |
| Muốn thêm/bớt đệm | `--pre-roll`, `--tail` |

`--limit-sec 600` (hoặc `0,60` cho từng nguồn, 0 = cả file) chỉ phân tích một đoạn: dùng để hiệu chỉnh nhanh.
Ngưỡng `still_energy` / `min_motion_energy` mặc định được hiệu chỉnh trên **một** đoạn 1080p góc rộng, hãy xem `peak_motion` trong `clips.json` khi đổi camera.

## Giới hạn đã biết

- **Tự phát hiện cú phá chưa đáng tin, kể cả khi có `--rack-roi`.** Trên trận thật (20 cú được gắn nhãn phá) chỉ 1/20 có hình thoi
  nguyên vẹn trước cú đánh. `detect_racked_cluster` và tỉ lệ pixel khác nỉ đều báo nhầm khi người đứng gần hoặc còn vài bi ở chân bàn.
- **Chưa tự động tìm được lúc bi 9 rơi / bắt đầu xếp bi.** Đã thử đếm bi trên bàn bằng trừ nền (nền trung vị cả file, nền một frame bàn trống)
  và bằng màu bão hòa: đều nhiễu. Mốc ước lượng theo mẫu 5 giây có thể lệch 2–3 giây; kém chắc nhất là ván có bàn bị người che.
- **Mốc cũ trong báo cáo highlight không dùng làm chuẩn.** `Highlight_Report_*.md` ghi cú phá ván 1 ở 18.8s; frame thật cho thấy lúc đó
  rack mới đang được xếp, cú phá thật ở 31.9s. Video highlight Master cũ có thể lấy sai khoảnh khắc ở một số ván (chưa kiểm tra hết).
- Tiếng xếp bi cuối ván cũng có thể thành clip và làm `win_t` tự động bị trễ: luôn dùng `--wins "t/e"`.
- Một cú đang kéo dài vì người đi lại có thể nuốt cú kế tiếp; người đi lại trước bàn làm chuyển động không về 0 (clip chạm trần 25s).
- Không có banner thắng ván và nhạc nền (khác chế độ highlight). `IntroManager` / `scripts/make_swiss_assets.py` vẽ cứng tên
  "CHUNG CHOO / KHƯƠNG LIỀU" và race to 7 (bỏ qua tham số), nên intro/outro dùng `condensed_cards.py`.
- File xuất ~8 Mbps (NVENC, CQ 23, khoảng 2.8 GB cho 46 phút); muốn nhỏ hơn thì tăng `-cq` trong `pick_encoder_args`.
- Trận mẫu `2026-10-12_ChungChoo_vs_KhuongLieu_v2`: 2 file nguồn (`1012.mp4`, `1012(1).mp4`, mỗi file khoảng 44.7 phút), 10 ván, Chung Choo 3 - 7 Khương Liều,
  bản condensed 46.5 phút, render 8.5 phút trên GTX 1650. Lệnh ở bước 2 ở trên là các mốc thực tế của trận này.
