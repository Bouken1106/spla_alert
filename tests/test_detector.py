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

    def _draw_slots(self, frame, config, side, alive_indexes, alive_color):
        h, w = frame.shape[:2]
        xs = (
            config.hud.friendly_slot_centers_x
            if side == "friendly"
            else config.hud.enemy_slot_centers_x
        )
        radius = int(config.hud.slot_size * h * 0.32)
        for idx, x_ratio in enumerate(xs):
            center = (int(x_ratio * w), int(config.hud.slot_center_y * h))
            color = alive_color if idx in alive_indexes else (130, 130, 130)
            cv2.circle(frame, center, radius, color, thickness=-1)
            cv2.rectangle(
                frame,
                (center[0] - radius // 3, center[1] - radius // 5),
                (center[0] + radius // 3, center[1] + radius // 5),
                (20, 20, 20),
                thickness=-1,
            )


if __name__ == "__main__":
    unittest.main()

