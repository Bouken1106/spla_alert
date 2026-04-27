import unittest

import cv2
import numpy as np

from spla_alert.config import AppConfig
from spla_alert.detector import SplatoonHudDetector


class DetectorTest(unittest.TestCase):
    def test_counts_colored_icons_as_alive_and_gray_icons_as_dead(self):
        config = AppConfig()
        frame = np.zeros((1080, 1920, 3), dtype=np.uint8)

        friendly_alive = {0, 2, 3}
        enemy_alive = {1}
        self._draw_slots(frame, config, "friendly", friendly_alive, (40, 230, 80))
        self._draw_slots(frame, config, "enemy", enemy_alive, (230, 40, 190))

        result = SplatoonHudDetector(config).count(frame, frame_index=20)

        self.assertEqual(result.friendly_alive, 3)
        self.assertEqual(result.enemy_alive, 1)
        self.assertEqual(result.frame_index, 20)

    def test_counts_scaled_720p_frame(self):
        config = AppConfig()
        frame = np.zeros((720, 1280, 3), dtype=np.uint8)

        self._draw_slots(frame, config, "friendly", {0, 1}, (0, 180, 255))
        self._draw_slots(frame, config, "enemy", {0, 1, 2, 3}, (255, 70, 0))

        result = SplatoonHudDetector(config).count(frame)

        self.assertEqual(result.friendly_alive, 2)
        self.assertEqual(result.enemy_alive, 4)

    def test_blank_frame_counts_all_slots_as_dead(self):
        frame = np.zeros((1080, 1920, 3), dtype=np.uint8)

        result = SplatoonHudDetector(AppConfig()).count(frame)

        self.assertEqual(result.friendly_alive, 0)
        self.assertEqual(result.enemy_alive, 0)

    def test_special_glow_and_weapon_overlay_do_not_hide_alive_icon(self):
        config = AppConfig()
        frame = np.zeros((1080, 1920, 3), dtype=np.uint8)

        self._draw_slots(
            frame,
            config,
            "friendly",
            {0, 1, 2, 3},
            (40, 230, 80),
            glow_indexes={1, 3},
        )
        self._draw_slots(
            frame,
            config,
            "enemy",
            {0, 2},
            (230, 40, 190),
            glow_indexes={2},
        )

        result = SplatoonHudDetector(config).count(frame)

        self.assertEqual(result.friendly_alive, 4)
        self.assertEqual(result.enemy_alive, 2)

    def test_gray_icons_with_white_highlights_are_dead(self):
        config = AppConfig()
        frame = np.zeros((1080, 1920, 3), dtype=np.uint8)

        self._draw_slots(
            frame,
            config,
            "friendly",
            set(),
            (40, 230, 80),
            glow_indexes={0, 1, 2, 3},
        )
        self._draw_slots(
            frame,
            config,
            "enemy",
            set(),
            (230, 40, 190),
            glow_indexes={0, 1, 2, 3},
        )

        result = SplatoonHudDetector(config).count(frame)

        self.assertEqual(result.friendly_alive, 0)
        self.assertEqual(result.enemy_alive, 0)

    def test_smaller_advantage_icons_are_still_counted(self):
        config = AppConfig()
        frame = np.zeros((1080, 1920, 3), dtype=np.uint8)

        self._draw_slots(
            frame,
            config,
            "friendly",
            {0, 1},
            (30, 220, 240),
            radius_scale=0.22,
        )
        self._draw_slots(
            frame,
            config,
            "enemy",
            {0, 1, 2},
            (220, 60, 40),
            radius_scale=0.24,
        )

        result = SplatoonHudDetector(config).count(frame)

        self.assertEqual(result.friendly_alive, 2)
        self.assertEqual(result.enemy_alive, 3)

    def _draw_slots(
        self,
        frame,
        config,
        side,
        alive_indexes,
        alive_color,
        glow_indexes=None,
        radius_scale=0.32,
    ):
        glow_indexes = glow_indexes or set()
        h, w = frame.shape[:2]
        xs = (
            config.hud.friendly_slot_centers_x
            if side == "friendly"
            else config.hud.enemy_slot_centers_x
        )
        radius = int(config.hud.slot_size * h * radius_scale)
        for idx, x_ratio in enumerate(xs):
            center = (int(x_ratio * w), int(config.hud.slot_center_y * h))
            color = alive_color if idx in alive_indexes else (130, 130, 130)
            cv2.circle(frame, center, radius, color, thickness=-1)
            if idx in glow_indexes:
                cv2.circle(
                    frame,
                    center,
                    radius + max(2, radius // 5),
                    (245, 245, 245),
                    2,
                )
            cv2.rectangle(
                frame,
                (center[0] - radius // 3, center[1] - radius // 5),
                (center[0] + radius // 3, center[1] + radius // 5),
                (20, 20, 20),
                thickness=-1,
            )


if __name__ == "__main__":
    unittest.main()
