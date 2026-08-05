import json, os, tempfile, unittest
from timing_util import chunk_durations, write_timing


class TimingUtilTest(unittest.TestCase):
    def test_chunk_durations_includes_gap(self):
        # 24000 samples @ sr 24000 = 1.0s; +2400 gap = 0.1s
        self.assertEqual(chunk_durations([24000, 12000], 2400, 24000, 1.0), [1.1, 0.6])

    def test_chunk_durations_speed_scaling(self):
        # speed 2.0 => playback halved
        self.assertEqual(chunk_durations([24000], 0, 24000, 2.0), [0.5])

    def test_chunk_durations_zero_speed_treated_as_one(self):
        self.assertEqual(chunk_durations([24000], 0, 24000, 0.0), [1.0])

    def test_write_timing_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "x.timing.json")
            write_timing(p, ["a", "b"], [1.0, 2.0])
            with open(p) as f:
                self.assertEqual(json.load(f), [{"text": "a", "dur": 1.0}, {"text": "b", "dur": 2.0}])


if __name__ == "__main__":
    unittest.main()
