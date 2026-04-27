import unittest

import cv2
import numpy as np

from spla_alert.config import WeaponConfig
from spla_alert.weapons import (
    WeaponInfo,
    WeaponRecognizer,
    WeaponTemplate,
    _distance_from_edges,
    _image_urls_from_stat_ink_page,
    _manifest_weapons,
)


class WeaponRecognizerTest(unittest.TestCase):
    def test_predicts_best_edge_template(self):
        slot = np.full((80, 80, 3), (170, 30, 200), dtype=np.uint8)
        cv2.rectangle(slot, (34, 14), (46, 66), (25, 25, 25), thickness=-1)
        cv2.line(slot, (28, 24), (52, 56), (235, 235, 235), 3)

        recognizer = WeaponRecognizer(
            WeaponConfig(confidence_threshold=0.2, min_edge_ratio=0.001),
            templates=(
                self._template("vertical", "vertical"),
                self._template("horizontal", "horizontal"),
            ),
        )

        prediction = recognizer.predict(slot)

        self.assertIsNotNone(prediction)
        self.assertEqual(prediction.key, "vertical")
        self.assertEqual(
            [item.key for item in prediction.candidates],
            ["vertical", "horizontal"],
        )

    def test_builds_manifest_entries_from_stat_ink_page_images(self):
        source_html = """
            <img src="/assets/hash/msfoie2j/Shooters/splattershot.png?v=1">
            <img src="/assets/hash/msfoie2j/Rollers/splatroller.png?v=1">
        """
        api_data = [
            {
                "key": "splattershot",
                "name": {"en_US": "Splattershot", "ja_JP": "Splattershot JP"},
                "type": {"key": "shooter"},
            },
            {
                "key": "missing",
                "name": {"en_US": "Missing"},
                "type": {"key": "shooter"},
            },
        ]

        urls = _image_urls_from_stat_ink_page(
            source_html,
            "https://stat.ink/api-info/weapon3",
        )
        manifest = _manifest_weapons(api_data, urls, "s3")

        self.assertEqual(len(manifest), 1)
        self.assertEqual(manifest[0]["key"], "splattershot")
        self.assertEqual(manifest[0]["game"], "s3")
        self.assertEqual(manifest[0]["main_key"], "splattershot")
        self.assertEqual(
            manifest[0]["image_url"],
            "https://stat.ink/assets/hash/msfoie2j/Shooters/splattershot.png?v=1",
        )

    def _template(self, key, orientation):
        canvas = np.zeros((64, 64), dtype=np.uint8)
        if orientation == "vertical":
            cv2.rectangle(canvas, (28, 10), (36, 54), 255, 2)
            cv2.line(canvas, (24, 20), (40, 44), 255, 2)
        else:
            cv2.rectangle(canvas, (10, 28), (54, 36), 255, 2)
            cv2.line(canvas, (20, 24), (44, 40), 255, 2)
        edges = canvas > 0
        return WeaponTemplate(
            info=WeaponInfo(
                key=key,
                name=key,
                type_key=None,
                image_url=f"https://example.test/{key}.png",
                game="s3",
                main_key=key,
            ),
            edges=edges,
            distance=_distance_from_edges(edges),
        )


if __name__ == "__main__":
    unittest.main()
