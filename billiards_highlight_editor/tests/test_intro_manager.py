import os
import unittest
import tempfile
from billiards_highlight_editor.intro_manager import IntroManager


class TestIntroManager(unittest.TestCase):
    def setUp(self):
        self.manager = IntroManager()
        self.temp_dir = tempfile.mkdtemp()

    def test_generate_all_styles_png(self):
        for style_id in [1, 2, 3, 4]:
            out_png = os.path.join(self.temp_dir, f"test_intro_{style_id}.png")
            res = self.manager.generate_intro_card_png(
                style_id=style_id,
                out_png_path=out_png,
                p1_name="Chung Choo",
                p2_name="Khương Liều",
                race_to=7
            )
            self.assertTrue(os.path.exists(res))
            self.assertTrue(os.path.getsize(res) > 5000)

    def test_generate_swiss_scoreboard_and_outro(self):
        sb_path = os.path.join(self.temp_dir, "test_sb.png")
        outro_path = os.path.join(self.temp_dir, "test_outro.png")

        res_sb = self.manager.generate_scoreboard_png(3, 7, sb_path)
        self.assertTrue(os.path.exists(res_sb))
        self.assertTrue(os.path.getsize(res_sb) > 2000)

        res_outro = self.manager.generate_outro_card_png("Khương Liều", "Chung Choo", 7, 3, outro_path)
        self.assertTrue(os.path.exists(res_outro))
        self.assertTrue(os.path.getsize(res_outro) > 5000)

    def tearDown(self):
        for f in os.listdir(self.temp_dir):
            try:
                os.remove(os.path.join(self.temp_dir, f))
            except Exception:
                pass
        try:
            os.rmdir(self.temp_dir)
        except Exception:
            pass


if __name__ == "__main__":
    unittest.main()
