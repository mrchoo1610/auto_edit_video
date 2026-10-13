"""Tests for the Swiss intro / outro cards of the Full Match Condensed renderer."""

import unittest

import numpy as np

from billiards_highlight_editor import condensed_cards as cc
from billiards_highlight_editor.condensed import CondensedConfig

P1, P2 = "Chung Choo", "Khương Liều"
LONG1 = "Nguyễn Hoàng Thiên Phúc Anh Khôi Đặng Văn Mạnh"
LONG2 = "Trương Thị Quỳnh Như Hạnh Phúc Vô Cùng Lê Hoàng Phương"


def px(img):
    return np.asarray(img.convert("RGB")).astype(int)


def bright(a, x0, y0, x1, y1, lum=150, skip_laser=True):
    """Bright (text-like) pixels in a region; the 1px gold laser line at x=960 is ignored."""
    reg = a[y0:y1, x0:x1].copy()
    if skip_laser and x0 <= 962 < x1:
        reg[:, max(0, 957 - x0):962 - x0 + 1] = 0
    return int((reg.max(axis=2) > lum).sum())


def gold_mask(a, x0, y0, x1, y1):
    r = a[y0:y1, x0:x1]
    return (abs(r[..., 0] - 229) < 25) & (abs(r[..., 1] - 193) < 25) & (abs(r[..., 2] - 88) < 30)


class TestIntroCard(unittest.TestCase):
    def test_size_and_mode(self):
        img = cc.render_intro_card(P1, P2, 7)
        self.assertEqual(img.size, (1920, 1080))
        self.assertEqual(img.mode, "RGB")

    def test_custom_size(self):
        self.assertEqual(cc.render_intro_card(P1, P2, 7, width=1280, height=720).size, (1280, 720))

    def test_vietnamese_names_do_not_crash(self):
        for a, b in [("Khương Liều", "Nguyễn Văn Ánh"), ("ĐẶNG THỊ MỸ DUYÊN", "Lê Hoàng Phương"), (P1, P2)]:
            self.assertEqual(cc.render_intro_card(a, b, 9, venue="CLB Sài Gòn", date_text="12/10/2026").size,
                             (1920, 1080))

    def test_names_render_white_text_on_both_sides(self):
        a = px(cc.render_intro_card(P1, P2, 7))
        self.assertGreater(bright(a, 300, 480, 860, 600, 230), 500)       # P1 left of the centre line
        self.assertGreater(bright(a, 1060, 480, 1700, 600, 230), 500)     # P2 right of it

    def test_long_names_stay_inside_card_and_off_the_centre(self):
        a = px(cc.render_intro_card(LONG1, LONG2, 9, venue="Giải giao lưu CLB Pool 9-Ball Quận Một Thành phố Hồ Chí Minh"))
        self.assertEqual(bright(a, 0, 400, 100, 700, 120), 0)             # left margin untouched
        self.assertEqual(bright(a, 1820, 400, 1920, 700, 120), 0)         # right margin untouched
        self.assertEqual(bright(a, 856, 440, 902, 640, 200), 0)           # P1 does not cross into the VS medallion
        self.assertEqual(bright(a, 1018, 440, 1064, 640, 200), 0)         # P2 neither
        self.assertEqual(bright(a, 0, 60, 330, 150, 150), 0)              # capsule (with long venue) stays centred, in frame
        self.assertEqual(bright(a, 1590, 60, 1920, 150, 150), 0)

    def test_race_to_and_names_change_the_image(self):
        base = px(cc.render_intro_card(P1, P2, 7))
        self.assertFalse(np.array_equal(base, px(cc.render_intro_card(P1, P2, 9))))
        self.assertFalse(np.array_equal(base, px(cc.render_intro_card("An", "Bình", 7))))

    def test_venue_and_date_are_optional_and_visible(self):
        base = px(cc.render_intro_card(P1, P2, 7))
        venue = px(cc.render_intro_card(P1, P2, 7, venue="CLB Test"))
        date = px(cc.render_intro_card(P1, P2, 7, date_text="12/10/2026"))
        self.assertFalse(np.array_equal(base, venue))
        self.assertFalse(np.array_equal(base, date))
        self.assertTrue(np.array_equal(base, px(cc.render_intro_card(P1, P2, 7, venue="  ", date_text=""))))
        # the intro never shows a score or champion label: only the venue/date region differs
        self.assertEqual(int(np.abs(base[300:1000] - venue[300:1000]).sum()), 0)


class TestOutroCard(unittest.TestCase):
    def test_size_and_mode(self):
        img = cc.render_outro_card(P1, P2, 3, 7, 7, 2)
        self.assertEqual(img.size, (1920, 1080))
        self.assertEqual(img.mode, "RGB")

    def test_resolve_winner_only_when_race_to_reached(self):
        self.assertIsNone(cc.resolve_winner(4, 6, 7, 2))
        self.assertIsNone(cc.resolve_winner(6, 6, 7, None))
        self.assertEqual(cc.resolve_winner(3, 7, 7, 2), 2)
        self.assertEqual(cc.resolve_winner(7, 3, 7, 1), 1)
        self.assertEqual(cc.resolve_winner(7, 3, 7, None), 1)       # derived from the score when not given

    def test_winner_label_only_when_race_to_reached(self):
        final = px(cc.render_outro_card(P1, P2, 3, 7, 7, 2))
        unfinished = px(cc.render_outro_card(P1, P2, 3, 6, 7, 2))
        badge_zone = (300, 215, 1700, 270)                       # CHAMPION / FINALIST badges sit above the names
        self.assertGreater(bright(final, *badge_zone), 300)
        self.assertEqual(bright(unfinished, *badge_zone, lum=60), 0)

    def test_winner_name_is_champagne_gold_loser_white(self):
        right = px(cc.render_outro_card(P1, P2, 3, 7, 7, 2))      # P2 (right) wins
        left = px(cc.render_outro_card(P1, P2, 7, 3, 7, 1))       # P1 (left) wins
        L, R = (300, 300, 860, 370), (1060, 300, 1700, 370)
        self.assertGreater(int(gold_mask(right, *R).sum()), 800)
        self.assertLess(int(gold_mask(right, *L).sum()), 50)
        self.assertGreater(int(gold_mask(left, *L).sum()), 800)
        self.assertLess(int(gold_mask(left, *R).sum()), 50)
        self.assertGreater(bright(right, *L, lum=230), 500)       # loser name stays white

    def test_unfinished_match_shows_no_gold_names(self):
        a = px(cc.render_outro_card(P1, P2, 4, 6, 7, None))
        self.assertLess(int(gold_mask(a, 300, 300, 860, 370).sum()), 50)
        self.assertLess(int(gold_mask(a, 1060, 300, 1700, 370).sum()), 50)

    def test_different_scores_give_different_images(self):
        a = px(cc.render_outro_card(P1, P2, 3, 7, 7, 2))
        b = px(cc.render_outro_card(P1, P2, 5, 7, 7, 2))
        c = px(cc.render_outro_card(P1, P2, 7, 3, 7, 1))
        self.assertFalse(np.array_equal(a, b))
        self.assertFalse(np.array_equal(a, c))
        # the score pill region is where they differ for the same winner
        self.assertGreater(int(np.abs(a[500:700, 700:1220] - b[500:700, 700:1220]).sum()), 0)

    def test_two_digit_scores_fit_in_frame(self):
        a = px(cc.render_outro_card(P1, P2, 12, 15, 15, 2))
        self.assertEqual(bright(a, 0, 480, 600, 720, 120), 0)
        self.assertEqual(bright(a, 1320, 480, 1920, 720, 120), 0)
        self.assertGreater(bright(a, 700, 520, 1220, 700, 200), 1000)     # big score is drawn

    def test_vietnamese_and_long_names_stay_inside_card(self):
        for a_name, b_name in [("Khương Liều", "Nguyễn Văn Ánh"), (LONG1, LONG2)]:
            a = px(cc.render_outro_card(a_name, b_name, 9, 12, 12, 2))
            self.assertEqual(bright(a, 0, 215, 100, 420, 120), 0)
            self.assertEqual(bright(a, 1820, 215, 1920, 420, 120), 0)
            self.assertEqual(bright(a, 856, 215, 902, 420, 120), 0)           # nothing from P1 crosses the centre
            self.assertEqual(bright(a, 1018, 215, 1064, 420, 120), 0)


class TestCardClipCommand(unittest.TestCase):
    def test_stream_layout_matches_normal_clips(self):
        from billiards_highlight_editor import condensed as cd
        cfg = CondensedConfig()
        enc = ["-c:v", "h264_nvenc", "-preset", "p4"]
        card = cc.card_clip_command("ffmpeg", enc, "in.png", "out.mp4", 4.0, cfg)
        clip = cd.clip_command("ffmpeg", enc, cd.RenderItem(0, 0, 8, 1, (0, 0)), "s.mp4", "a.png", None, "o.mp4", cfg)

        def opt(cmd, flag):
            return cmd[cmd.index(flag) + 1]

        for flag in ("-g", "-pix_fmt", "-c:a", "-b:a", "-ar", "-ac", "-c:v", "-preset"):
            self.assertEqual(opt(card, flag), opt(clip, flag), flag)
        vf = opt(card, "-vf")
        self.assertIn(f"scale={cfg.width}:{cfg.height}", vf)
        self.assertIn(f"fps={cfg.fps}", vf)
        self.assertIn("format=yuv420p", vf)
        self.assertIn("fade=t=in:st=0:d=0.400", vf)
        self.assertIn("fade=t=out:st=3.600:d=0.400", vf)
        self.assertIn("anullsrc=channel_layout=stereo:sample_rate=48000", card)
        self.assertEqual(opt(card, "-t"), "4.000")
        self.assertEqual(card[-1], "out.mp4")

    def test_fade_is_capped_for_very_short_cards(self):
        vf_cmd = cc.card_clip_command("ffmpeg", [], "i.png", "o.mp4", 0.5, CondensedConfig())
        self.assertIn("fade=t=in:st=0:d=0.250", vf_cmd[vf_cmd.index("-vf") + 1])


if __name__ == "__main__":
    unittest.main()
