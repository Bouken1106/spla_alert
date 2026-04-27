import contextlib
import io
import json
import unittest
from unittest.mock import patch

import numpy as np

from spla_alert import cli


class FakeSource:
    def __init__(self, frame_count):
        self.frame_count = frame_count
        self.read_count = 0
        self.released = False
        self.frame = np.zeros((720, 1280, 3), dtype=np.uint8)

    def read(self):
        if self.read_count >= self.frame_count:
            return False, None
        self.read_count += 1
        return True, self.frame.copy()

    def release(self):
        self.released = True


class CliTest(unittest.TestCase):
    def test_run_processes_every_tenth_frame_by_default(self):
        source = FakeSource(frame_count=21)
        output = io.StringIO()

        with patch("spla_alert.cli.create_source", return_value=source):
            with contextlib.redirect_stdout(output):
                code = cli.main(
                    [
                        "run",
                        "--source",
                        "fake",
                        "--json-lines",
                        "--max-frames",
                        "21",
                    ]
                )

        self.assertEqual(code, 0)
        self.assertTrue(source.released)
        results = [json.loads(line) for line in output.getvalue().splitlines()]
        self.assertEqual([result["frame_index"] for result in results], [0, 10, 20])


if __name__ == "__main__":
    unittest.main()
