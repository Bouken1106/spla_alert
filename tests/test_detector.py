import unittest
from pathlib import Path

import cv2
import numpy as np

from spla_alert.config import AppConfig, ClassifierConfig
from spla_alert.detector import SplatoonHudDetector
from spla_alert.weapons import WeaponCandidate, WeaponPrediction


class FakeWeaponRecognizer:
    def __init__(self):
        self.calls = 0

    def predict(self, crop):
        self.calls += 1
        return WeaponPrediction(
            key="splattershot",
            name="Splattershot",
            score=0.8,
            confidence=0.7,
            image_url="https://example.test/splattershot.png",
            game="s3",
            main_key="splattershot",
            candidates=(
                WeaponCandidate(
                    key="splattershot",
                    name="Splattershot",
                    score=0.8,
                    image_url="https://example.test/splattershot.png",
                    game="s3",
                    main_key="splattershot",
                ),
            ),
        )


class DetectorTest(unittest.TestCase):
    def test_real_hud_fixtures_count_labeled_alive_players(self):
        fixtures = (
            ("splatoon_hud_friendly1_enemy4.jpg", 1, 4),
            ("splatoon_hud_friendly1_enemy3.jpg", 1, 3),
            ("splatoon_hud_friendly2_enemy3.jpg", 2, 3),
            ("splatoon_hud_friendly2_enemy4.jpg", 2, 4),
            ("splatoon_hud_friendly3_enemy3_capture2.jpg", 3, 3),
            ("splatoon_hud_friendly3_enemy4.jpg", 3, 4),
        )
        for filename, expected_friendly, expected_enemy in fixtures:
            with self.subTest(filename=filename):
                frame = cv2.imread(str(_fixture_path(filename)))
                self.assertIsNotNone(frame)

                result = SplatoonHudDetector(AppConfig()).count(frame)

                self.assertTrue(result.hud_present)
                self.assertEqual(result.friendly_alive, expected_friendly)
                self.assertEqual(result.enemy_alive, expected_enemy)

    def test_counts_colored_icons_as_alive_and_gray_icons_as_dead(self):
        config = self._config_without_hud_gate()
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
        config = self._config_without_hud_gate()
        frame = np.zeros((720, 1280, 3), dtype=np.uint8)

        self._draw_slots(frame, config, "friendly", {0, 1}, (0, 180, 255))
        self._draw_slots(frame, config, "enemy", {0, 1, 2, 3}, (255, 70, 0))

        result = SplatoonHudDetector(config).count(frame)

        self.assertEqual(result.friendly_alive, 2)
        self.assertEqual(result.enemy_alive, 4)

    def test_blank_frame_counts_all_slots_as_dead(self):
        frame = np.zeros((1080, 1920, 3), dtype=np.uint8)

        result = SplatoonHudDetector(AppConfig()).count(frame)

        self.assertFalse(result.hud_present)
        self.assertEqual(result.friendly_alive, 0)
        self.assertEqual(result.enemy_alive, 0)

    def test_colored_top_content_without_timer_is_not_counted(self):
        config = AppConfig()
        frame = np.zeros((1080, 1920, 3), dtype=np.uint8)

        self._draw_slots(frame, config, "friendly", {0, 1, 2, 3}, (40, 230, 80))
        self._draw_slots(frame, config, "enemy", {0, 1, 2, 3}, (230, 40, 190))

        result = SplatoonHudDetector(config).count(frame)

        self.assertFalse(result.hud_present)
        self.assertEqual(result.friendly_alive, 0)
        self.assertEqual(result.enemy_alive, 0)

    def test_timer_like_content_without_alive_slots_is_not_counted(self):
        config = AppConfig()
        frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
        h, w = frame.shape[:2]
        timer_center = (w // 2, int(config.hud.slot_center_y * h))
        cv2.rectangle(
            frame,
            (timer_center[0] - 55, timer_center[1] - 24),
            (timer_center[0] + 55, timer_center[1] + 24),
            (20, 20, 20),
            thickness=-1,
        )
        cv2.putText(
            frame,
            "4:00",
            (timer_center[0] - 42, timer_center[1] + 13),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.9,
            (235, 235, 235),
            2,
            cv2.LINE_AA,
        )

        result = SplatoonHudDetector(config).count(frame)

        self.assertFalse(result.hud_present)
        self.assertEqual(result.friendly_alive, 0)
        self.assertEqual(result.enemy_alive, 0)

    def test_special_glow_and_weapon_overlay_do_not_hide_alive_icon(self):
        config = self._config_without_hud_gate()
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

    def test_shifted_color_special_glow_is_still_alive(self):
        config = self._config_without_hud_gate()
        frame = np.zeros((1080, 1920, 3), dtype=np.uint8)

        self._draw_slots(
            frame,
            config,
            "friendly",
            {0, 1, 2, 3},
            (40, 230, 80),
            glow_indexes={0, 1, 2, 3},
            glow_color=(20, 240, 240),
            glow_thickness=10,
        )
        self._draw_slots(
            frame,
            config,
            "enemy",
            {0, 1, 2, 3},
            (230, 40, 190),
            glow_indexes={0, 1, 2, 3},
            glow_color=(240, 220, 20),
            glow_thickness=10,
        )

        result = SplatoonHudDetector(config).count(frame)

        self.assertEqual(result.friendly_alive, 4)
        self.assertEqual(result.enemy_alive, 4)

    def test_gray_icons_with_white_highlights_are_dead(self):
        config = self._config_without_hud_gate()
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

    def test_colored_center_weapon_on_dead_icon_is_ignored(self):
        config = self._config_without_hud_gate()
        frame = np.zeros((1080, 1920, 3), dtype=np.uint8)

        self._draw_slots(frame, config, "friendly", set(), (40, 230, 80))
        self._draw_slots(frame, config, "enemy", set(), (230, 40, 190))
        self._draw_center_weapon(frame, config, "friendly", 0, (40, 230, 80))
        self._draw_center_weapon(frame, config, "enemy", 2, (230, 40, 190))

        result = SplatoonHudDetector(config).count(frame)

        self.assertEqual(result.friendly_alive, 0)
        self.assertEqual(result.enemy_alive, 0)

    def test_x_marked_icon_with_colored_weapon_is_dead(self):
        config = self._config_without_hud_gate()
        frame = np.zeros((1080, 1920, 3), dtype=np.uint8)

        self._draw_slots(frame, config, "friendly", {1, 2, 3}, (40, 230, 80))
        self._draw_slots(frame, config, "enemy", {0, 1, 2, 3}, (230, 40, 190))
        self._draw_x_dead_slot(
            frame,
            config,
            "friendly",
            0,
            background_color=(240, 40, 200),
            weapon_color=(40, 230, 80),
        )

        result = SplatoonHudDetector(config).count(frame)

        self.assertEqual(result.friendly_alive, 3)
        self.assertEqual(result.enemy_alive, 4)
        self.assertFalse(result.slots[0].alive)
        self.assertGreater(
            result.slots[0].x_mark_score,
            config.classifier.x_mark_contrast_threshold,
        )

    def test_x_marked_hud_slots_over_colored_stage_are_dead(self):
        config = self._config_without_hud_gate()
        frame = np.full((720, 1280, 3), (25, 150, 35), dtype=np.uint8)

        self._draw_actual_hud_slots(
            frame,
            config,
            "friendly",
            alive_indexes={2, 3},
            alive_color=(190, 35, 165),
        )
        self._draw_actual_hud_slots(
            frame,
            config,
            "enemy",
            alive_indexes={0, 1, 2},
            alive_color=(35, 210, 60),
        )

        result = SplatoonHudDetector(config).count(frame)

        self.assertEqual(result.friendly_alive, 2)
        self.assertEqual(result.enemy_alive, 3)
        self.assertFalse(result.slots[0].alive)
        self.assertFalse(result.slots[1].alive)
        self.assertFalse(result.slots[7].alive)

    def test_yellow_timer_hud_counts_shifted_actual_slots(self):
        config = AppConfig()
        frame = np.full((720, 1280, 3), (220, 150, 70), dtype=np.uint8)
        self._draw_yellow_timer(frame, config, "0:22")
        self._draw_actual_hud_slots(
            frame,
            config,
            "friendly",
            alive_indexes={1},
            alive_color=(190, 35, 165),
            center_xs=(0.305, 0.352, 0.398, 0.438),
        )
        self._draw_actual_hud_slots(
            frame,
            config,
            "enemy",
            alive_indexes={0, 1, 2},
            alive_color=(35, 210, 60),
        )

        result = SplatoonHudDetector(config).count(frame)

        self.assertTrue(result.hud_present)
        self.assertEqual(result.friendly_alive, 1)
        self.assertEqual(result.enemy_alive, 3)

    def test_smaller_advantage_icons_are_still_counted(self):
        config = self._config_without_hud_gate()
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

    def test_attaches_weapon_prediction_to_each_hud_slot(self):
        config = self._config_without_hud_gate()
        frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
        self._draw_slots(frame, config, "friendly", {0, 1, 2, 3}, (40, 230, 80))
        self._draw_slots(frame, config, "enemy", {0, 1, 2, 3}, (230, 40, 190))
        recognizer = FakeWeaponRecognizer()

        result = SplatoonHudDetector(config, weapon_recognizer=recognizer).count(frame)

        self.assertEqual(recognizer.calls, 8)
        self.assertTrue(all(slot.weapon is not None for slot in result.slots))
        self.assertEqual(result.slots[0].to_dict()["weapon"]["key"], "splattershot")

    def _config_without_hud_gate(self):
        return AppConfig(classifier=ClassifierConfig(require_hud_presence=False))

    def _draw_slots(
        self,
        frame,
        config,
        side,
        alive_indexes,
        alive_color,
        glow_indexes=None,
        radius_scale=0.32,
        glow_color=(245, 245, 245),
        glow_thickness=2,
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
                    glow_color,
                    glow_thickness,
                )
            cv2.rectangle(
                frame,
                (center[0] - radius // 3, center[1] - radius // 5),
                (center[0] + radius // 3, center[1] + radius // 5),
                (20, 20, 20),
                thickness=-1,
            )

    def _draw_center_weapon(self, frame, config, side, index, color):
        h, w = frame.shape[:2]
        xs = (
            config.hud.friendly_slot_centers_x
            if side == "friendly"
            else config.hud.enemy_slot_centers_x
        )
        radius = int(config.hud.slot_size * h * 0.32)
        center = (int(xs[index] * w), int(config.hud.slot_center_y * h))
        cv2.rectangle(
            frame,
            (center[0] - radius // 2, center[1] - radius // 5),
            (center[0] + radius // 2, center[1] + radius // 5),
            color,
            thickness=-1,
        )

    def _draw_x_dead_slot(
        self,
        frame,
        config,
        side,
        index,
        background_color,
        weapon_color,
    ):
        h, w = frame.shape[:2]
        xs = (
            config.hud.friendly_slot_centers_x
            if side == "friendly"
            else config.hud.enemy_slot_centers_x
        )
        size = int(config.hud.slot_size * h)
        center = (int(xs[index] * w), int(config.hud.slot_center_y * h))
        x1 = max(0, center[0] - size // 2)
        y1 = max(0, center[1] - size // 2)
        x2 = min(w, x1 + size)
        y2 = min(h, y1 + size)
        radius = int(config.hud.slot_size * h * 0.32)

        frame[y1:y2, x1:x2] = background_color
        cv2.circle(frame, center, radius, (12, 12, 12), thickness=-1)
        cv2.rectangle(
            frame,
            (center[0] - radius // 2, center[1] - radius // 5),
            (center[0] + radius // 2, center[1] + radius // 5),
            weapon_color,
            thickness=-1,
        )
        thickness = max(4, radius // 4)
        cv2.line(
            frame,
            (center[0] - radius, center[1] - radius),
            (center[0] + radius, center[1] + radius),
            (165, 165, 165),
            thickness,
        )
        cv2.line(
            frame,
            (center[0] + radius, center[1] - radius),
            (center[0] - radius, center[1] + radius),
            (165, 165, 165),
            thickness,
        )

    def _draw_actual_hud_slots(
        self,
        frame,
        config,
        side,
        alive_indexes,
        alive_color,
        center_xs=None,
    ):
        h, w = frame.shape[:2]
        xs = center_xs or (
            config.hud.friendly_slot_centers_x
            if side == "friendly"
            else config.hud.enemy_slot_centers_x
        )
        slot_size = int(config.hud.slot_size * h)
        radius = max(10, int(slot_size * 0.36))
        for idx, x_ratio in enumerate(xs):
            center = (int(x_ratio * w), int(config.hud.slot_center_y * h))
            if idx in alive_indexes:
                points = np.array(
                    [
                        (center[0], center[1] - radius),
                        (center[0] - radius, center[1] + radius),
                        (center[0] + radius, center[1] + radius),
                    ],
                    dtype=np.int32,
                )
                cv2.fillConvexPoly(frame, points, alive_color)
                cv2.rectangle(
                    frame,
                    (center[0] - radius // 2, center[1] - radius // 6),
                    (center[0] + radius // 2, center[1] + radius // 5),
                    (25, 25, 25),
                    thickness=-1,
                )
            else:
                cv2.circle(frame, center, radius, (95, 95, 95), thickness=-1)
                cv2.line(
                    frame,
                    (center[0] - radius, center[1] - radius),
                    (center[0] + radius, center[1] + radius),
                    (12, 12, 12),
                    max(8, radius // 2),
                )
                cv2.line(
                    frame,
                    (center[0] + radius, center[1] - radius),
                    (center[0] - radius, center[1] + radius),
                    (12, 12, 12),
                    max(8, radius // 2),
                )
                cv2.line(
                    frame,
                    (center[0] - radius, center[1] - radius),
                    (center[0] + radius, center[1] + radius),
                    (165, 165, 165),
                    max(4, radius // 4),
                )
                cv2.line(
                    frame,
                    (center[0] + radius, center[1] - radius),
                    (center[0] - radius, center[1] + radius),
                    (165, 165, 165),
                    max(4, radius // 4),
                )

    def _draw_yellow_timer(self, frame, config, text):
        h, w = frame.shape[:2]
        center = (w // 2, int(config.hud.slot_center_y * h))
        cv2.rectangle(
            frame,
            (center[0] - 55, center[1] - 24),
            (center[0] + 55, center[1] + 24),
            (20, 20, 20),
            thickness=-1,
        )
        cv2.putText(
            frame,
            text,
            (center[0] - 38, center[1] + 14),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.9,
            (0, 240, 245),
            2,
            cv2.LINE_AA,
        )


def _fixture_path(filename):
    return Path(__file__).parent / "fixtures" / filename


if __name__ == "__main__":
    unittest.main()
