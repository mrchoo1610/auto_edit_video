---
name: billiards-full-racks
description: >-
  Dựng bản "Full Ván" Pool 9 bi cho YouTube 16:9: mỗi ván là một đoạn liền mạch, giữ nguyên toàn bộ nội dung từ cú phá bi đến lúc bi 9 cuối rơi, chỉ bỏ đoạn xếp bi
  giữa hai ván; các ván ghép lại thành một video với chuyển cảnh mờ dần mềm (0.5 s mỗi bên) giữa các ván. Trận race to 7 thành 10 đoạn ghép nối. Không dùng chuyển động
  hay âm thanh để cắt trong ván (không cắt đoạn đi lại). Dùng chung bảng tỷ số Swiss, zoom 1.3x, intro/outro với skill `billiards-full-match-condensed`.
  Dùng khi người dùng muốn giữ nguyên từng ván, không rút gọn từng cú.
---

# Billiards Full Ván (mỗi ván một đoạn liền, bỏ xếp bi)

Khác `billiards-full-match-condensed` (cắt sát từng cú): **không cắt gì bên trong một ván.** Video = intro + ván 1 + ván 2 + ... + outro.
Mỗi ván chạy từ `cú phá − 4.5 s` (thấy hình thoi 9 bi) đến mốc `e` (lúc bi 9 rơi xong, trước khi người chơi nhặt/xếp bi). Đoạn từ `e` đến cú phá kế tiếp bị bỏ.
Mọi thứ khác (project, `roi`, zoom, bảng tỷ số Swiss, intro/outro, tiếng click, SEO, tìm mốc) dùng lại của skill condensed: xem `.claude/skills/billiards-full-match-condensed/SKILL.md`, không lặp lại ở đây.

## Lệnh (code: `condensed.py`, cờ `plan --by-rack`)

```bash
P=projects/<tên>
# 0. đo vùng bàn và tâm zoom như condensed (roi)
# 1. dựng clip thẳng từ mốc, KHÔNG phân tích video (chạy vài giây)
python -m billiards_highlight_editor.condensed plan --project $P --by-rack --sources raw/part1.mp4 raw/part2.mp4 --p1 "..." --p2 "..." --race-to N \
  --table-roi X,Y,W,H \
  --breaks "31.92,497.35,...,1:81.2,..." --wins "448.5/450,1032.5/1034,...,1:23.5/26,..." --winners P1,P1,P2,...
# 2. mở analysis/contact_sheet.jpg xác nhận cú phá / bi 9 rơi từng ván (3 ô mỗi ván)
# 3. render (không cần audit: trong ván không có mối cắt nào)
python -m billiards_highlight_editor.condensed render --project $P --zoom 1.3 --zoom-center CX,CY --out Full_RaceToN_<P1>_vs_<P2>.mp4
```

- `--breaks`: giây cú phá của **từng ván**, `nguồn:giây` nếu không phải file 0. `--wins "t/e"`: `t` = bi 9 rơi (bảng điểm nhảy), `e` = nơi cắt cuối ván. Hai danh sách **phải cùng số ván**.
  Không có `/e` thì cuối ván = `t + tail` (1.5 s). Mốc phải xác định bằng ảnh (xem "Tìm mốc" của skill condensed); **không có cách tự động đáng tin**.
- Ván vắt qua hai file (race to 7 trận mẫu: ván 5, cú phá ở file 0 giây 2211, bi 9 rơi ở file 1 giây 23.5) được tự tách làm hai clip, mối nối giữa hai file có fade như mối giữa hai ván.
- `--break-pre-roll N` (mặc định 4.5 s): giữ N giây trước cú phá. `--fade-video N` / `--fade-audio N` (mặc định **0.5 s** mỗi bên, tức khoảng 1 s mờ rồi sáng lại giữa hai ván; condensed dùng 0.15/0.20).
  Chỉnh khi render bằng `render --fade-video/--fade-audio` hoặc `--no-fade`.
- `--by-rack` tự đặt `handshake = 0` (ván cuối đã kết thúc ở `e`). `racks`/`score` dùng như condensed (cần truyền lại `--breaks/--wins` nếu muốn dựng lại từ mốc).
- Chương YouTube: mỗi ván một chương (`0:00 Ván 1: ...`), đủ dài để hợp lệ.

> Trận mẫu race to 7: hai file nguồn và các project cũ đã bị xóa (13/10/2026), nên các lệnh và mốc dưới đây là ghi chép, không chạy lại được nếu không có file nguồn.

## Cách đặt mốc `t/e` của mỗi ván (người dùng yêu cầu 13/10/2026: bi cái phải dừng hẳn mới kết thúc)

Bản V1 cắt ở mốc cũ (bi 9 rơi + 1.5 s) và **cắt giữa lúc bi cái còn lăn** (ván 1: bi cái còn trôi đến lỗ góc ở 450.6 s, cắt ở 450.0 s). Quy tắc mới, đo bằng ảnh từng 0.25–0.5 s quanh cuối ván:

- `t` (bảng điểm nhảy) = lúc bi 9 vào lỗ. **Ván "miễn"** (bi 9 ở vị trí dễ nên đối thủ được miễn đánh, người dùng xác nhận 13/10/2026): bi 9 không vào lỗ, đặt `t` = lúc bi dừng hẳn.
- `e` (cắt hết ván) = `cue_stop + 1.0 s` (bi cái và mọi bi dừng hẳn hoặc bị tay chạm/nhặt, cộng 1 s). Nếu người chơi đã bắt đầu xếp bi trong lúc bi cái còn trôi chậm, `e` không muộn hơn `racking_start + 2 s` (ưu tiên giữ bi cái, chấp nhận lộ tối đa 2 s xếp bi; 3 s thì ván 4 và 6 lộ rõ cả bi đã đặt lên bàn).
- Đo mỗi ván bằng 3 mốc: `nine_pot_t`, `cue_stop_t`, `racking_start_t`. Bi cái hay trôi rất chậm (sub-pixel) rất lâu sau khi bi 9 rơi, nên so vị trí giữa các khung liên tiếp chứ không nhìn bằng mắt thường.
- **Mốc cũ trong SKILL condensed của trận mẫu race to 7 sai ở nhiều ván** (đo lại 13/10/2026): bi 9 rơi ván 2 = 1027.25 (cũ 1032.5), ván 4 = 2155.0 (cũ 2160.5), ván 6 = 627.3 (cũ 624.5), ván 7 = 975.0 (cũ 997.5, lệch 22 s). Bản condensed V5d dùng mốc cũ nên bảng điểm có thể nhảy sai lúc ở các ván này [chưa kiểm tra video V5d].

Mốc đã đo cho trận mẫu (`--wins`, nguồn:giây): `448.5/451.6, 1027.25/1036.5, 1640.5/1641.5 (miễn), 2155.0/2159.75, 1:23.5/24.6, 1:627.3/631.2, 1:975.0/979.5, 1:1607.3/1609.5, 1:1946.0/1947.0 (miễn), 1:2518.5/2519.5 (miễn)`.
Các mốc này do subagent đo từ ảnh (mỗi ván một agent) và tôi chỉ tự xem lại ván 1, 3 và bảng ảnh cuối clip của cả 10 ván; ván 2, 4–10 chưa có người xem lại kỹ. Cú phá (`--breaks`) xem trên contact sheet: ô đầu đều thấy rack nguyên, ô sau 3 s thấy bi bung.

## Dùng subagent để làm nhanh (người dùng yêu cầu 13/10/2026)

- **Đo mốc từng ván: một subagent một ván, chạy song song** (10 agent cho race to 7, mỗi agent 2–8 phút, tổng ~8 phút thay vì ~40 phút tuần tự). Giao việc bằng một đoạn mô tả đầy đủ: file nguồn và đường dẫn, lệnh tạo ảnh (`sheet2.py <nguồn> <t0> <bước> <n> <ra.jpg> <x0,y0,x1,y1>`: contact sheet cắt vùng bàn `520,500,1400,860`, có nhãn thời gian), mốc cũ nghi sai, và 3 mốc cần trả (`nine_pot_t`, `cue_stop_t`, `racking_start_t`) kèm độ tin cậy. Mỗi agent ghi ảnh ra tên riêng (`m<ván>_*.jpg`) để không đè nhau.
- **Điền đủ số liệu của từng ván trước khi gửi.** Lần đầu tôi gửi agent với chỗ trống chưa điền (`RACKNO`, `WINT`...) và phải dừng agent rồi gửi lại.
- **Không tin nguyên văn báo cáo agent.** Agent từng đọc sai vì ván miễn (ván 3, 9, 10: nói "không thấy bi 9 vào lỗ") và vì bi cái trôi sub-pixel (ván 4: dừng 2160.25, hình thì gần như đã dừng từ trước). Phải tự xem lại ít nhất bảng ảnh khung cuối mỗi ván (`e−1.5 s` và `e−0.1 s`, 10 ván một ảnh) và ván có số liệu bất thường, rồi mới áp mốc.
- **Render nhanh: `render --workers 3`** (ffmpeg chạy song song 3 clip trên cùng GPU NVENC; subagent **không** làm render nhanh hơn vì chỉ có một GPU, và chạy 10 clip trên một máy là việc của một tiến trình). Giới hạn số phiên NVENC của GPU chưa kiểm tra [GTX 1650]; nếu ffmpeg báo lỗi mở encoder thì giảm xuống 2.
- Việc nào độc lập và chậm thì giao agent (đo mốc, xem ảnh nhiều khung); việc nào là một lệnh vài giây (`plan --by-rack`, `racks`) thì tự làm.

## Số đo (trận mẫu race to 7, hai file 44.7 phút = 89.3 phút gốc, 10 ván, 3-7)

| | Giá trị |
|---|---|
| Mười ván liền mạch (chưa kể intro 4 s, outro 6 s) | **80.0 phút** (−10.4 % so với gốc) |
| Đoạn xếp bi bị bỏ giữa 9 ván | 6.2 phút (mỗi đoạn 27–78 s) |
| Đoạn trước cú phá ván 1 và sau ván cuối | 3.1 phút |
| Render thử 2 ván (16.1 phút) bằng NVENC GTX 1650 | 2 phút 55 s, 894 MB; render đủ 10 ván ước ~18 phút (suy từ đó, chưa chạy) |

Kiểm tra bằng mắt/đo: render thử race to 2 (hai ván đầu); độ sáng ảnh tại mối giữa hai ván giảm từ ~76 xuống ~9 (gần đen) rồi lên lại ~80 trong khoảng 1 s;
chương `7:07` khớp mốc nối (4 s intro + 422.6 s ván 1). **Chưa xem bằng mắt cả video**, chưa nghe lại tiếng ở mối nối, chưa render đủ 10 ván.

## Rủi ro đã biết

- Mốc sai là cắt sai: `e` sớm quá thì mất cảnh bi 9 rơi, muộn quá thì dính cảnh xếp bi. Luôn xem lại contact sheet và frame quanh `e` (1–2 s/khung).
- Ván vắt qua hai file: mối nối là điểm duy nhất bên trong ván có fade, và nếu hai file thật sự liền nhau thì mất khoảng 1 s ở đó [chưa kiểm tra file thật có liền hay không].
- Chuyển cảnh là "dip to black" (mờ xuống đen rồi sáng lên), không phải cross-dissolve giữa hai ván. Nếu muốn hòa trộn hai ván thì cần `xfade` + `acrossfade` (phải render lại phần nối, không dùng `concat -c copy`; chưa làm).
- Bảng điểm không bị mờ, chuyển ngay sang ván mới (nhãn `VÁN n`, `MATCH POINT`...) trong lúc hình đang đen.
- Không dùng chuyển động hay `audit`: ván liền nên không có mối cắt trong ván để kiểm tra.

## Lịch sử

- **13/10/2026 — V2: sửa mốc cuối ván.** Người dùng thấy ván 1 cắt khi bi cái chưa dừng và dặn bi cái phải dừng cả khi bi 9 vào lỗ; ba ván (3, 9, 10) là ván miễn (bi 9 ở vị trí dễ nên không đánh). Đo lại cả 10 ván bằng 10 subagent (xem mục "Cách đặt mốc" và "Dùng subagent"), thay mốc `--wins`, render lại bằng `--workers 3`. Tổng 79.7 phút (V1: 80.0). Kết quả render V2 chưa xem hết bằng mắt. Mốc ván 4 và 6 nghiêng về giữ bi cái hơn bỏ xếp bi (lộ tối đa 2 s xếp bi); nếu người dùng muốn cắt sớm hơn thì đổi `e`.

- **13/10/2026 — tạo skill.** Bản đầu (đề xuất cắt cả đoạn bàn yên 10 s, 67.4 phút) bị thay thế: người dùng muốn **giữ nguyên toàn ván, chỉ bỏ xếp bi, mười ván ghép với chuyển cảnh tự nhiên**.
  Thêm `plan --by-rack` (`clips_by_rack`, `cmd_plan_by_rack`), `--break-pre-roll`, `--fade-video/--fade-audio` cho `plan`, `config.rack_mode`; 5 test mới (`TestRackMode`). Cũng đo thử: `--move-gap 9999` với mốc xếp bi **không dùng được** (mỗi file thành 1 clip nên `--wins` báo "10 win times given for 2 racks"), nên mới thêm chế độ riêng.
