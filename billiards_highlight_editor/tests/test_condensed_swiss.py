"""Tests for the Swiss Split scoreboard HUD used by the Full Match Condensed renderer."""

import unittest

import numpy as np

from billiards_highlight_editor import condensed as cd
from billiards_highlight_editor.condensed_swiss import (
    CARD_H, CARD_POS, CARD_W, rack_label_for, render_swiss_scoreboard,
)

P1, P2 = "Chung Choo", "Khương Liều"


def hud(s1=0, s2=0, p1=P1, p2=P2, race_to=3, label="VÁN 1", w=1920, h=1080):
    return render_swiss_scoreboard(w, h, p1, p2, s1, s2, race_to, rack_label=label)


def region(img, x0, y0, x1, y1):
    return np.asarray(img)[y0:y1, x0:x1]


class TestSwissScoreboard(unittest.TestCase):
    def test_full_frame_rgba(self):
        img = hud()
        self.assertEqual(img.size, (1920, 1080))
        self.assertEqual(img.mode, "RGBA")
        a = np.asarray(img)[..., 3]
        ys, xs = np.nonzero(a)
        # nothing is drawn outside the 590x84 card pinned at (50, 40)
        self.assertGreaterEqual(xs.min(), CARD_POS[0])
        self.assertLessEqual(xs.max(), CARD_POS[0] + CARD_W)
        self.assertGreaterEqual(ys.min(), CARD_POS[1])
        self.assertLessEqual(ys.max(), CARD_POS[1] + CARD_H)
        self.assertEqual(int(a[1000, 1800]), 0)          # rest of the frame is transparent

    def test_custom_frame_size(self):
        img = hud(w=1280, h=720)
        self.assertEqual(img.size, (1280, 720))
        self.assertEqual(img.mode, "RGBA")
        self.assertGreater(int(np.asarray(img)[..., 3].max()), 0)

    def test_score_text_changes(self):
        a, b = hud(0, 0), hud(1, 0)
        # score boxes: P1 box x = 50+241..50+287, P2 box x = 50+303..50+349, y = 40+36..40+74
        p1_a, p1_b = region(a, 291, 76, 337, 114), region(b, 291, 76, 337, 114)
        p2_a, p2_b = region(a, 353, 76, 399, 114), region(b, 353, 76, 399, 114)
        self.assertFalse(np.array_equal(p1_a, p1_b), "P1 score digit must change 0 -> 1")
        self.assertTrue(np.array_equal(p2_a, p2_b), "P2 score box must stay the same")
        self.assertFalse(np.array_equal(np.asarray(a), np.asarray(b)))

    def test_position_is_identical_for_every_score(self):
        boxes = []
        for s in [(0, 0), (1, 0), (2, 2), (3, 2)]:
            a = np.asarray(hud(*s))[..., 3]
            ys, xs = np.nonzero(a)
            boxes.append((xs.min(), ys.min(), xs.max(), ys.max()))
        self.assertEqual(len(set(boxes)), 1)

    def test_vietnamese_names_do_not_crash(self):
        for p1, p2 in [("Khương Liều", "Nguyễn Văn Ánh"), ("ĐẶNG THỊ MỸ DUYÊN", "Lê Hoàng Phương"),
                       ("Khương Liều", "Chung Choo")]:
            img = hud(2, 1, p1=p1, p2=p2)
            self.assertEqual(img.size, (1920, 1080))

    def test_long_names_stay_inside_card(self):
        img = hud(3, 2, p1="Nguyễn Hoàng Thiên Phúc Anh Khôi", p2="Trương Thị Quỳnh Như Hạnh Phúc Vô Cùng")
        a = np.asarray(img)[..., 3]
        ys, xs = np.nonzero(a)
        self.assertLessEqual(xs.max(), CARD_POS[0] + CARD_W)
        self.assertLessEqual(ys.max(), CARD_POS[1] + CARD_H)

    def test_names_render_text(self):
        # name areas must contain bright (white) text pixels
        img = hud(0, 0)
        n1 = region(img, 50 + 28, 40 + 40, 50 + 231, 40 + 70)
        n2 = region(img, 50 + 361, 40 + 40, 50 + 563, 40 + 70)
        for n in (n1, n2):
            self.assertGreater(int(((n[..., :3].min(axis=2) > 230) & (n[..., 3] > 200)).sum()), 50)

    def test_rack_label(self):
        self.assertEqual(rack_label_for(4, (1, 2), 3), "VÁN 4")
        self.assertEqual(rack_label_for(5, (3, 2), 3), "FINAL")
        # situation labels need the score at the start of the rack
        self.assertEqual(rack_label_for(5, (2, 2), 3, (2, 2)), "HILL-HILL")
        self.assertEqual(rack_label_for(4, (2, 1), 3, (2, 1)), "MATCH POINT")
        self.assertEqual(rack_label_for(2, (1, 0), 3, (0, 0)), "VÁN 2")
        self.assertEqual(rack_label_for(5, (2, 3), 3, (2, 2)), "FINAL")       # the jump that ends the match
        self.assertEqual(rack_label_for(1, (0, 0), 1, (0, 0)), "VÁN 1")      # race to 1: no hill
        self.assertEqual(rack_label_for(5, (2, 3), 3), "FINAL")


class TestStyleConfig(unittest.TestCase):
    def test_default_is_swiss(self):
        self.assertEqual(cd.CondensedConfig().style, "swiss")

    def test_old_config_without_style_defaults_to_swiss(self):
        self.assertEqual(cd.config_from_dict({"fps": 25}).style, "swiss")
        self.assertEqual(cd.config_from_dict({"style": "classic"}).style, "classic")

    def test_render_subcommand_has_style_flag(self):
        import contextlib
        import io
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            cd.main(["render", "--project", "x", "--style", "nope"])


if __name__ == "__main__":
    unittest.main()
