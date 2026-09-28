"""Чистые функции genjutsu.py: размер выхода, цена Seedance, проверка ссылок промпта, payload."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import genjutsu as g  # noqa: E402


class OutDims(unittest.TestCase):
    def test_vertical_short_side_is_resolution(self):
        self.assertEqual(g.out_dims("720p", 1080, 1920), (720, 1280))

    def test_horizontal_keeps_aspect(self):
        self.assertEqual(g.out_dims("480p", 1920, 1080), (853, 480))


class Price(unittest.TestCase):
    def test_matches_fal_formula_for_29s_vertical_720p(self):
        # 720·1280·(29+29)·24/1024 токенов × $0.0214/1000 × 0.6
        self.assertAlmostEqual(g.seedance_usd(29, 29, 720, 1280), 16.09, places=2)

    def test_input_seconds_are_billed(self):
        self.assertAlmostEqual(g.seedance_usd(10, 10, 720, 1280),
                               2 * g.seedance_usd(10, 0, 720, 1280))


class RefErrors(unittest.TestCase):
    def test_valid_prompt_has_no_errors(self):
        p = "Edit @Video 1. Replace the LEFT performer with @Image1 and @Image 2."
        self.assertEqual(g.ref_errors(p, 2), [])

    def test_image_beyond_passed_count(self):
        errs = g.ref_errors("Edit @Video 1 with @Image 3", 2)
        self.assertEqual(len(errs), 1)
        self.assertIn("@Image 3", errs[0])

    def test_missing_video_ref(self):
        errs = g.ref_errors("Replace him with @Image 1", 1)
        self.assertTrue(any("@Video 1" in e for e in errs))

    def test_second_video_rejected(self):
        errs = g.ref_errors("Edit @Video 1 and @Video 2", 0)
        self.assertTrue(any("@Video 2" in e for e in errs))

    def test_unfilled_placeholder_rejected(self):
        errs = g.ref_errors("Edit @Video1. Replace LEFT with @Element1: {OUTFIT_1}.", 0, 1)
        self.assertTrue(any("{OUTFIT_1}" in e for e in errs))


class Hands(unittest.TestCase):
    def test_block_appended_once(self):
        p = g.with_hands("Edit @Video1.")
        self.assertIn(g.HANDS_BLOCK, p)
        self.assertEqual(g.with_hands(p).count("HANDS ARE THE PRIORITY"), 1)

    def test_disabled_keeps_prompt(self):
        self.assertEqual(g.with_hands("Edit @Video1.", enabled=False), "Edit @Video1.")


class Splice(unittest.TestCase):
    def test_opening_replaced(self):
        self.assertEqual(g.splice_plan(0, 2.6, 14.9),
                         [("fix", 0.0, 2.6), ("base", 2.6, 14.9)])

    def test_middle_replaced(self):
        self.assertEqual(g.splice_plan(5, 8, 14.9),
                         [("base", 0.0, 5), ("fix", 0.0, 3), ("base", 8, 14.9)])

    def test_out_of_range_rejected(self):
        with self.assertRaises(ValueError):
            g.splice_plan(3, 2, 14.9)


class ElementRefs(unittest.TestCase):
    def test_kling_syntax_without_space_is_valid(self):
        p = "Edit @Video1. Replace LEFT with @Element1, RIGHT with @Element2. Scene @Image1."
        self.assertEqual(g.ref_errors(p, 1, 2), [])

    def test_element_beyond_passed_count(self):
        errs = g.ref_errors("Edit @Video1 with @Element3", 0, 2)
        self.assertEqual(len(errs), 1)
        self.assertIn("@Element 3", errs[0])


class KlingPayload(unittest.TestCase):
    def test_first_file_of_element_is_frontal(self):
        p = g.kling_payload("x", "v", ["s"], [["face", "body", "sheet"]], "original")
        self.assertEqual(p["elements"], [{"frontal_image_url": "face",
                                          "reference_image_urls": ["body", "sheet"]}])
        self.assertEqual(p["video_url"], "v")
        self.assertTrue(p["keep_audio"])

    def test_no_audio_drops_source_sound(self):
        self.assertFalse(g.kling_payload("x", "v", [], [], "none")["keep_audio"])


class Payload(unittest.TestCase):
    def test_editing_task_and_audio_flag(self):
        p = g.recast_payload("x", "v", ["a", "b"], "720p", "original", None)
        self.assertEqual(p["task"], "editing")
        self.assertEqual(p["video_urls"], ["v"])
        self.assertEqual(p["image_urls"], ["a", "b"])
        self.assertFalse(p["generate_audio"])
        self.assertNotIn("seed", p)

    def test_generated_audio_and_seed(self):
        p = g.recast_payload("x", "v", [], "480p", "generated", 7)
        self.assertTrue(p["generate_audio"])
        self.assertEqual(p["seed"], 7)


class SkillText(unittest.TestCase):
    def test_no_dollar_digit_in_skill(self):
        # Claude Code подставляет слова аргументов /genjutsu вместо $0, $1…: «$0.9» превращалось в «там.9»
        import re
        text = (Path(__file__).resolve().parent.parent / "SKILL.md").read_text(encoding="utf-8")
        self.assertEqual(re.findall(r"\$\d", text), [])


if __name__ == "__main__":
    unittest.main()
