import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
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

    def test_run_passes_fourcc_to_source_factory(self):
        source = FakeSource(frame_count=1)
        output = io.StringIO()

        with patch("spla_alert.cli.create_source", return_value=source) as create:
            with contextlib.redirect_stdout(output):
                code = cli.main(
                    [
                        "run",
                        "--source",
                        "fake",
                        "--fourcc",
                        "MJPG",
                        "--max-frames",
                        "1",
                    ]
                )

        self.assertEqual(code, 0)
        create.assert_called_once_with("fake", None, None, None, 1, "MJPG")

    def test_snapshot_can_save_json_and_slot_crops(self):
        source = FakeSource(frame_count=1)
        output = io.StringIO()

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            overlay = root / "overlay.jpg"
            result_json = root / "result.json"
            crops_dir = root / "crops"

            with patch("spla_alert.cli.create_source", return_value=source):
                with contextlib.redirect_stdout(output):
                    code = cli.main(
                        [
                            "snapshot",
                            "--source",
                            "fake",
                            "--output",
                            str(overlay),
                            "--json-output",
                            str(result_json),
                            "--crops-dir",
                            str(crops_dir),
                        ]
                    )

            self.assertEqual(code, 0)
            self.assertTrue(overlay.exists())
            self.assertEqual(json.loads(result_json.read_text())["friendly_alive"], 0)
            self.assertEqual(len(list(crops_dir.glob("*.jpg"))), 8)


if __name__ == "__main__":
    unittest.main()
