import unittest
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


if __name__ == "__main__":
    unittest.main()
