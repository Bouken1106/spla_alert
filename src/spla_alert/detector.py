from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Any, Iterable, Literal

import cv2
import numpy as np

from .config import AppConfig


Side = Literal["friendly", "enemy"]
BBox = tuple[int, int, int, int]
SlotRegion = tuple[Side, int, BBox]


@dataclass(frozen=True)
class SlotStatus:
    side: Side
    index: int
    alive: bool
    bbox: BBox
    colored_ratio: float
    p90_saturation: float
    colored_pixels: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "side": self.side,
            "index": self.index,
            "alive": self.alive,
            "bbox": self.bbox,
            "colored_ratio": round(self.colored_ratio, 4),
            "p90_saturation": round(self.p90_saturation, 1),
            "colored_pixels": self.colored_pixels,
        }


@dataclass(frozen=True)
class CountResult:
    frame_index: int
    friendly_alive: int
    enemy_alive: int
    slots: tuple[SlotStatus, ...]
    processed_at: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "frame_index": self.frame_index,
            "friendly_alive": self.friendly_alive,
            "enemy_alive": self.enemy_alive,
            "slots": [slot.to_dict() for slot in self.slots],
            "processed_at": self.processed_at,
        }


class SplatoonHudDetector:
    def __init__(self, config: AppConfig | None = None):
        self.config = config or AppConfig()

    def count(self, frame: np.ndarray, frame_index: int = 0) -> CountResult:
        if frame.ndim != 3 or frame.shape[2] != 3:
            raise ValueError("frame must be a BGR image with shape HxWx3")

        slots = tuple(self._classify_slots(frame))
        friendly_alive = _alive_count(slots, "friendly")
        enemy_alive = _alive_count(slots, "enemy")

        return CountResult(
            frame_index=frame_index,
            friendly_alive=friendly_alive,
            enemy_alive=enemy_alive,
            slots=slots,
            processed_at=time.time(),
        )

    def _classify_slots(self, frame: np.ndarray) -> Iterable[SlotStatus]:
        for side, index, bbox in self._slot_regions(frame.shape):
            yield self._classify_slot(_crop(frame, bbox), side, index, bbox)

    def _slot_regions(self, frame_shape: tuple[int, int, int]) -> Iterable[SlotRegion]:
        for side, center_x_ratios in (
            ("friendly", self.config.hud.friendly_slot_centers_x),
            ("enemy", self.config.hud.enemy_slot_centers_x),
        ):
            for index, center_x_ratio in enumerate(center_x_ratios):
                yield side, index, self._slot_bbox(frame_shape, center_x_ratio)

    def _slot_bbox(
        self, frame_shape: tuple[int, int, int], center_x_ratio: float
    ) -> BBox:
        height, width = frame_shape[:2]
        size = int(round(self.config.hud.slot_size * height))
        size = max(size, 8)
        center_x = int(round(center_x_ratio * width))
        center_y = int(round(self.config.hud.slot_center_y * height))

        x1 = max(0, center_x - size // 2)
        y1 = max(0, center_y - size // 2)
        x2 = min(width, x1 + size)
        y2 = min(height, y1 + size)
        if x2 - x1 < size:
            x1 = max(0, x2 - size)
        if y2 - y1 < size:
            y1 = max(0, y2 - size)
        return (x1, y1, x2, y2)

    def _classify_slot(
        self, crop: np.ndarray, side: Side, index: int, bbox: BBox
    ) -> SlotStatus:
        cfg = self.config.classifier
        if crop.size == 0:
            return SlotStatus(side, index, False, bbox, 0.0, 0.0, 0)

        hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
        saturation = hsv[:, :, 1]
        value = hsv[:, :, 2]
        mask = _ellipse_mask(crop.shape[:2])
        bright_mask = mask & (value >= cfg.value_min)
        denominator = int(mask.sum())
        if denominator == 0 or not np.any(bright_mask):
            return SlotStatus(side, index, False, bbox, 0.0, 0.0, 0)

        colored_mask = bright_mask & (saturation >= cfg.saturation_threshold)
        colored_pixels = int(colored_mask.sum())
        colored_ratio = colored_pixels / denominator
        p90_saturation = float(np.percentile(saturation[bright_mask], 90))

        alive = colored_pixels >= cfg.min_colored_pixels and (
            colored_ratio >= cfg.colored_ratio_threshold
            or (
                colored_ratio >= cfg.weak_colored_ratio_threshold
                and p90_saturation >= cfg.p90_saturation_threshold
            )
        )

        return SlotStatus(
            side=side,
            index=index,
            alive=alive,
            bbox=bbox,
            colored_ratio=colored_ratio,
            p90_saturation=p90_saturation,
            colored_pixels=colored_pixels,
        )


def draw_overlay(frame: np.ndarray, result: CountResult) -> np.ndarray:
    overlay = frame.copy()
    for slot in result.slots:
        _draw_slot(overlay, slot)
    _draw_summary(overlay, result)
    return overlay


def _draw_slot(overlay: np.ndarray, slot: SlotStatus) -> None:
    x1, y1, x2, y2 = slot.bbox
    color = (0, 220, 0) if slot.alive else (150, 150, 150)
    cv2.rectangle(overlay, (x1, y1), (x2, y2), color, 2)
    label = f"{slot.side[0].upper()}{slot.index + 1}:{'A' if slot.alive else 'D'}"
    cv2.putText(
        overlay,
        label,
        (x1, max(15, y1 - 5)),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.45,
        color,
        1,
        cv2.LINE_AA,
    )


def _draw_summary(overlay: np.ndarray, result: CountResult) -> None:
    text = f"friendly {result.friendly_alive}/4  enemy {result.enemy_alive}/4"
    cv2.putText(
        overlay,
        text,
        (20, 35),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.9,
        (255, 255, 255),
        3,
        cv2.LINE_AA,
    )
    cv2.putText(
        overlay,
        text,
        (20, 35),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.9,
        (20, 20, 20),
        1,
        cv2.LINE_AA,
    )


def _alive_count(slots: tuple[SlotStatus, ...], side: Side) -> int:
    return sum(1 for slot in slots if slot.side == side and slot.alive)


def _crop(frame: np.ndarray, bbox: BBox) -> np.ndarray:
    x1, y1, x2, y2 = bbox
    return frame[y1:y2, x1:x2]


def _ellipse_mask(shape: tuple[int, int]) -> np.ndarray:
    height, width = shape
    yy, xx = np.ogrid[:height, :width]
    center_y = (height - 1) / 2.0
    center_x = (width - 1) / 2.0
    radius_y = max(height * 0.48, 1.0)
    radius_x = max(width * 0.48, 1.0)
    normalized = ((yy - center_y) / radius_y) ** 2 + ((xx - center_x) / radius_x) ** 2
    return normalized <= 1.0
