import os
import tempfile
import unittest
from unittest import mock
import align

DEMO = '''#!/usr/bin/env bash
source "${PACE_LIB:-/dev/null}" 2>/dev/null || true
type pace >/dev/null 2>&1 || pace() { :; }
echo "Acme CLI tour"
pace 37
echo "$ widget init"
echo "created myapp/"
pace 33
echo "$ widget build"
pace 25
'''


class ExtractSectionsTest(unittest.TestCase):
    def test_one_label_per_pace(self):
        self.assertEqual(
            align.extract_sections(DEMO),
            ["Acme CLI tour", "$ widget init created myapp/", "$ widget build"],
        )

    def test_no_pace_yields_empty(self):
        self.assertEqual(align.extract_sections('echo "hi"\n'), [])


class ParseValidateHoldsTest(unittest.TestCase):
    def test_parse_plain(self):
        self.assertEqual(align.parse_assignment("[1, 1, 2]"), [1, 1, 2])

    def test_parse_with_prose(self):
        self.assertEqual(align.parse_assignment("Here you go:\n[1,2,2]\nthanks"), [1, 2, 2])

    def test_parse_garbage_is_none(self):
        self.assertIsNone(align.parse_assignment("no array here"))

    def test_validate_good(self):
        self.assertTrue(align.validate_assignment([1, 1, 2, 3], 4, 3))

    def test_validate_wrong_length(self):
        self.assertFalse(align.validate_assignment([1, 2], 4, 3))

    def test_validate_out_of_range(self):
        self.assertFalse(align.validate_assignment([1, 2, 4], 3, 3))

    def test_validate_not_monotonic(self):
        self.assertFalse(align.validate_assignment([1, 3, 2], 3, 3))

    def test_validate_section_uncovered(self):
        self.assertFalse(align.validate_assignment([1, 1, 3], 3, 3))  # section 2 missing

    def test_compute_holds(self):
        self.assertEqual(align.compute_holds([1.0, 2.0, 3.0, 4.0], [1, 1, 2, 3], 3), [3.0, 3.0, 4.0])


class MainTest(unittest.TestCase):
    def _fixture(self, d):
        timing = os.path.join(d, "demo.timing.json")
        with open(timing, "w") as f:
            f.write('[{"text":"Welcome to the tour.","dur":1.0},'
                    '{"text":"First we init.","dur":2.0},'
                    '{"text":"Then we build.","dur":3.0}]')
        demo = os.path.join(d, "demo.sh")
        with open(demo, "w") as f:
            f.write('echo "tour"\npace 1\necho "init"\npace 1\necho "build"\npace 1\n')
        return timing, demo

    def test_main_success_prints_holds(self):
        with tempfile.TemporaryDirectory() as d:
            timing, demo = self._fixture(d)
            with mock.patch("align.query_ollama", return_value="[1,2,3]"):
                with mock.patch("sys.stdout") as out:
                    with self.assertRaises(SystemExit) as cm:
                        align.main(["--timing", timing, "--demo", demo])
            self.assertEqual(cm.exception.code, 0)
            printed = "".join(c.args[0] for c in out.write.call_args_list)
            self.assertIn("1.0 2.0 3.0", printed)

    def test_main_ollama_unreachable_exits_1(self):
        with tempfile.TemporaryDirectory() as d:
            timing, demo = self._fixture(d)
            with mock.patch("align.query_ollama", side_effect=OSError("refused")):
                with self.assertRaises(SystemExit) as cm:
                    align.main(["--timing", timing, "--demo", demo])
            self.assertEqual(cm.exception.code, 1)

    def test_main_malformed_reply_exits_1(self):
        with tempfile.TemporaryDirectory() as d:
            timing, demo = self._fixture(d)
            with mock.patch("align.query_ollama", return_value="sorry, no"):
                with self.assertRaises(SystemExit) as cm:
                    align.main(["--timing", timing, "--demo", demo])
            self.assertEqual(cm.exception.code, 1)

    def test_main_no_pace_exits_2(self):
        with tempfile.TemporaryDirectory() as d:
            timing, _ = self._fixture(d)
            demo = os.path.join(d, "nopace.sh")
            with open(demo, "w") as f:
                f.write('echo "hi"\n')
            with self.assertRaises(SystemExit) as cm:
                align.main(["--timing", timing, "--demo", demo])
            self.assertEqual(cm.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
