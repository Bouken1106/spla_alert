import json
import tempfile
import unittest
from pathlib import Path

from spla_alert.config import DEFAULT_ENEMY_X, AppConfig, load_config


class ConfigTest(unittest.TestCase):
    def test_load_config_applies_partial_overrides(self):
        config_path = self._write_config(
            {
                "hud": {
                    "slot_center_y": 0.061,
                    "friendly_slot_centers_x": [0.1, 0.2, 0.3, 0.4],
                },
                "classifier": {"saturation_threshold": 70},
            }
        )

        config = load_config(config_path)

        self.assertEqual(config.hud.slot_center_y, 0.061)
        self.assertEqual(config.hud.slot_size, AppConfig().hud.slot_size)
        self.assertEqual(config.hud.friendly_slot_centers_x, (0.1, 0.2, 0.3, 0.4))
        self.assertEqual(config.hud.enemy_slot_centers_x, DEFAULT_ENEMY_X)
        self.assertEqual(config.classifier.saturation_threshold, 70)
        self.assertEqual(config.classifier.value_min, AppConfig().classifier.value_min)

    def test_load_config_rejects_wrong_slot_count(self):
        config_path = self._write_config(
            {"hud": {"friendly_slot_centers_x": [0.1, 0.2, 0.3]}}
        )

        with self.assertRaisesRegex(ValueError, "friendly_slot_centers_x"):
            load_config(config_path)

    def _write_config(self, value):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        path = Path(temp_dir.name) / "config.json"
        path.write_text(json.dumps(value), encoding="utf-8")
        return path


if __name__ == "__main__":
    unittest.main()
