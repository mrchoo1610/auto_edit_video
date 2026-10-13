"""Tests for the YouTube title / description / tags generator."""

import unittest
from datetime import date

from billiards_highlight_editor import condensed_seo as seo

CHAPTERS = "0:00 Ván 1: A 1 - 0 B\n4:07 Ván 2: A 1 - 1 B\n"


def facts(**kw):
    base = dict(p1="Chung Choo", p2="Khương Liều", race_to=7, score=(3, 7), winner=2, chapters=CHAPTERS,
                duration_min=46.5, played_on=date(2026, 10, 12))
    base.update(kw)
    return seo.MatchFacts(**base)


class TestTitle(unittest.TestCase):
    def test_title_within_soft_limit_and_keyword_first(self):
        t = seo.pick_title(facts())
        self.assertLessEqual(len(t), seo.TITLE_SOFT_LIMIT)
        self.assertTrue(t.startswith("Chung Choo vs Khương Liều"))
        self.assertIn("Race to 7", t)
        self.assertIn("(3-7)", t)

    def test_long_names_still_under_hard_limit(self):
        t = seo.pick_title(facts(p1="Nguyễn Văn Trường Giang", p2="Phạm Hoàng Anh Tuấn Kiệt"))
        self.assertLessEqual(len(t), seo.TITLE_HARD_LIMIT)

    def test_no_score_variant_has_no_result(self):
        self.assertNotIn("3-7", seo.title_without_score(facts()))

    def test_no_final_score_leaves_score_out(self):
        self.assertNotIn("(", seo.pick_title(facts(score=None, winner=None)))


class TestDescription(unittest.TestCase):
    def test_hook_carries_keywords_and_fits(self):
        h = seo.hook_line(facts())
        self.assertLessEqual(len(h), seo.HOOK_MAX_CHARS)
        for word in ("Chung Choo", "Khương Liều", "race to 7", "Khương Liều thắng 7-3"):
            self.assertIn(word, h)

    def test_description_has_chapters_and_hashtags_last(self):
        d = seo.description(facts())
        self.assertIn("0:00 Ván 1: A 1 - 0 B", d)
        self.assertIn("12/10/2026", d)
        self.assertTrue(d.strip().splitlines()[-1].startswith("#"))

    def test_missing_facts_are_left_out_not_invented(self):
        d = seo.description(facts(played_on=None))
        self.assertNotIn("Ngày thi đấu", d)
        self.assertNotIn("Địa điểm", d)
        self.assertEqual(seo.missing_facts(facts(played_on=None)), ["địa điểm (`--venue`)", "ngày thi đấu (`--date`)"])

    def test_no_filler_sentences(self):
        d = seo.description(facts(channel="Kênh Y"))
        for filler in ("rút gọn chỉ giữ", "Về bản video này", "đăng ký kênh", "hãy bấm thích", "bấm vào mốc"):
            self.assertNotIn(filler, d)

    def test_venue_channel_tournament_used_when_given(self):
        d = seo.description(facts(venue="CLB X", channel="Kênh Y", tournament="Giao lưu Z"))
        for word in ("CLB X", "Kênh Y", "Giao lưu Z"):
            self.assertIn(word, d)

    def test_score_without_winner_says_so_neutrally(self):
        d = seo.description(facts(score=(2, 3), winner=None))
        self.assertNotIn("thắng", seo.hook_line(facts(score=(2, 3), winner=None)))
        self.assertIn("2 - 3", d)


class TestTagsAndHashtags(unittest.TestCase):
    def test_hashtags_limited_ascii_no_spaces(self):
        h = seo.hashtags(facts())
        self.assertLessEqual(len(h), seo.HASHTAG_MAX)
        self.assertEqual(h[:3], ["#Pool9Bi", "#Bida", "#Billiards"])
        self.assertIn("#KhuongLieu", h)
        for t in h:
            self.assertRegex(t, r"^#[0-9A-Za-z]+$")

    def test_tags_within_character_budget(self):
        tg = seo.tags(facts(extra_keywords=["x" * 200, "y" * 200, "z" * 200]))
        self.assertLessEqual(len(",".join(tg)), seo.TAGS_MAX_CHARS)
        self.assertEqual(tg[0], "Chung Choo vs Khương Liều")

    def test_ascii_slug(self):
        self.assertEqual(seo.ascii_slug("Khương Liều"), "KhuongLieu")
        self.assertEqual(seo.ascii_slug("Đặng Văn"), "DangVan")

    def test_markdown_and_date_parse(self):
        md = seo.to_markdown(seo.build_youtube_metadata(facts()), ["tên kênh (`--channel`)"])
        self.assertIn("## Tiêu đề", md)
        self.assertIn("Mô tả chưa có: tên kênh", md)
        self.assertEqual(seo.parse_date_from_project_name("2026-10-12_A_vs_B"), date(2026, 10, 12))
        self.assertIsNone(seo.parse_date_from_project_name("match_1"))


if __name__ == "__main__":
    unittest.main()
