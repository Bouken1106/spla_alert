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

    def test_load_config_applies_classifier_overrides(self):
        config_path = self._write_config(
            {
                "classifier": {
                    "require_hud_presence": "false",
                    "channel_spread_threshold": "45",
                    "visible_colored_ratio_threshold": "0.3",
                    "x_mark_dark_value_max": "75",
                    "x_mark_saturation_max": "65",
                    "x_mark_contrast_threshold": "0.12",
                    "x_mark_max_colored_ratio": "0.58",
                    "probe_radius_ratio": "0.04",
                    "hud_timer_dark_ratio_threshold": "0.2",
                    "hud_timer_edge_ratio_threshold": "0.08",
                    "hud_team_hue_slots_min": "3",
                    "hud_min_alive_slots": "2",
                },
                "weapons": {
                    "enabled": "true",
                    "confidence_threshold": "0.41",
                    "template_size": "48",
                    "cache_dir": "/tmp/spla-alert-weapons",
                }
            }
        )

        config = load_config(config_path)

        self.assertFalse(config.classifier.require_hud_presence)
        self.assertEqual(config.classifier.channel_spread_threshold, 45)
        self.assertEqual(config.classifier.visible_colored_ratio_threshold, 0.3)
        self.assertEqual(config.classifier.x_mark_dark_value_max, 75)
        self.assertEqual(config.classifier.x_mark_saturation_max, 65)
        self.assertEqual(config.classifier.x_mark_contrast_threshold, 0.12)
        self.assertEqual(config.classifier.x_mark_max_colored_ratio, 0.58)
        self.assertEqual(config.classifier.probe_radius_ratio, 0.04)
        self.assertEqual(config.classifier.hud_timer_dark_ratio_threshold, 0.2)
        self.assertEqual(config.classifier.hud_timer_edge_ratio_threshold, 0.08)
        self.assertEqual(config.classifier.hud_team_hue_slots_min, 3)
        self.assertEqual(config.classifier.hud_min_alive_slots, 2)
        self.assertEqual(
            config.classifier.saturation_threshold,
            AppConfig().classifier.saturation_threshold,
        )
        self.assertTrue(config.weapons.enabled)
        self.assertEqual(config.weapons.confidence_threshold, 0.41)
        self.assertEqual(config.weapons.template_size, 48)
        self.assertEqual(config.weapons.cache_dir, "/tmp/spla-alert-weapons")

    def _write_config(self, value):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        path = Path(temp_dir.name) / "config.json"
        path.write_text(json.dumps(value), encoding="utf-8")
        return path


if __name__ == "__main__":
    unittest.main()
