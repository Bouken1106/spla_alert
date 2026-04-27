import unittest

from spla_alert import source


class SourceTest(unittest.TestCase):
    def test_normalize_fourcc_accepts_case_insensitive_value(self):
        self.assertEqual(source._normalize_fourcc("mjpg"), "MJPG")

    def test_normalize_fourcc_rejects_wrong_length(self):
        with self.assertRaisesRegex(ValueError, "4 characters"):
            source._normalize_fourcc("mjpeg")


if __name__ == "__main__":
    unittest.main()
