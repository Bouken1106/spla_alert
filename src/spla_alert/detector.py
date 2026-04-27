from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Any, Iterable, Literal

import cv2
import numpy as np

from .config import AppConfig, ClassifierConfig


Side = Literal["friendly", "enemy"]
BBox = tuple[int, int, int, int]
SlotRegion = tuple[Side, int, BBox]


@dataclass(frozen=True)
class _SlotColorMetrics:
    colored_ratio: float
    visible_colored_ratio: float
    p90_saturation: float
    p90_channel_spread: float
    colored_pixels: int
    visible_pixels: int
    score_pixels: int
    dominant_hue: float | None


@dataclass(frozen=True)
class SlotStatus:
    side: Side
    index: int
    alive: bool
    bbox: BBox
    colored_ratio: float
    visible_colored_ratio: float
    p90_saturation: float
    p90_channel_spread: float
    colored_pixels: int
    visible_pixels: int
    score_pixels: int
    dominant_hue: float | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "side": self.side,
            "index": self.index,
            "alive": self.alive,
            "bbox": self.bbox,
            "colored_ratio": round(self.colored_ratio, 4),
            "visible_colored_ratio": round(self.visible_colored_ratio, 4),
            "p90_saturation": round(self.p90_saturation, 1),
            "p90_channel_spread": round(self.p90_channel_spread, 1),
            "colored_pixels": self.colored_pixels,
            "visible_pixels": self.visible_pixels,
            "score_pixels": self.score_pixels,
            "dominant_hue": (
                None if self.dominant_hue is None else round(self.dominant_hue, 1)
            ),
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
        if crop.size == 0:
            return _dead_slot_status(side, index, bbox)

        cfg = self.config.classifier
        metrics = _measure_slot_color(crop, cfg)
        return _slot_status(side, index, bbox, _is_alive(metrics, cfg), metrics)


def _measure_slot_color(crop: np.ndarray, cfg: ClassifierConfig) -> _SlotColorMetrics:
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    lab = cv2.cvtColor(crop, cv2.COLOR_BGR2LAB)
    saturation = hsv[:, :, 1]
    value = hsv[:, :, 2]
    channel_spread = (
        crop.max(axis=2).astype(np.int16) - crop.min(axis=2).astype(np.int16)
    )
    lab_a = lab[:, :, 1].astype(np.float32) - 128.0
    lab_b = lab[:, :, 2].astype(np.float32) - 128.0
    lab_chroma = np.sqrt(lab_a * lab_a + lab_b * lab_b)

    score_mask = _ellipse_mask(crop.shape[:2], cfg.inner_ignore_ratio)
    visible_mask = score_mask & (value >= cfg.value_min)
    score_pixels = int(score_mask.sum())
    visible_pixels = int(visible_mask.sum())
    if score_pixels == 0 or visible_pixels == 0:
        return _empty_color_metrics(visible_pixels, score_pixels)

    colored_mask = visible_mask & _colored_pixel_mask(
        saturation,
        channel_spread,
        lab_chroma,
        cfg,
    )
    colored_pixels = int(colored_mask.sum())

    return _SlotColorMetrics(
        colored_ratio=colored_pixels / score_pixels,
        visible_colored_ratio=colored_pixels / visible_pixels,
        p90_saturation=float(np.percentile(saturation[visible_mask], 90)),
        p90_channel_spread=float(np.percentile(channel_spread[visible_mask], 90)),
        colored_pixels=colored_pixels,
        visible_pixels=visible_pixels,
        score_pixels=score_pixels,
        dominant_hue=_dominant_hue(hsv[:, :, 0][colored_mask]),
    )


def _colored_pixel_mask(
    saturation: np.ndarray,
    channel_spread: np.ndarray,
    lab_chroma: np.ndarray,
    cfg: ClassifierConfig,
) -> np.ndarray:
    saturated = saturation >= cfg.saturation_threshold
    color_separated = channel_spread >= cfg.channel_spread_threshold
    chromatic = lab_chroma >= cfg.lab_chroma_threshold
    return (saturated & color_separated) | chromatic


def _is_alive(metrics: _SlotColorMetrics, cfg: ClassifierConfig) -> bool:
    if metrics.score_pixels == 0 or metrics.visible_pixels == 0:
        return False

    min_colored_pixels = max(
        cfg.min_colored_pixels,
        int(round(metrics.score_pixels * cfg.min_colored_area_ratio)),
    )
    if metrics.colored_pixels < min_colored_pixels:
        return False

    strong_area_match = metrics.colored_ratio >= cfg.colored_ratio_threshold
    strong_visible_match = (
        metrics.visible_colored_ratio >= cfg.visible_colored_ratio_threshold
    )
    weak_but_saturated = (
        metrics.colored_ratio >= cfg.weak_colored_ratio_threshold
        and (
            metrics.p90_saturation >= cfg.p90_saturation_threshold
            or metrics.p90_channel_spread >= cfg.p90_channel_spread_threshold
        )
    )
    return strong_area_match or strong_visible_match or weak_but_saturated


def _slot_status(
    side: Side,
    index: int,
    bbox: BBox,
    alive: bool,
    metrics: _SlotColorMetrics,
) -> SlotStatus:
    return SlotStatus(
        side=side,
        index=index,
        alive=alive,
        bbox=bbox,
        colored_ratio=metrics.colored_ratio,
        visible_colored_ratio=metrics.visible_colored_ratio,
        p90_saturation=metrics.p90_saturation,
        p90_channel_spread=metrics.p90_channel_spread,
        colored_pixels=metrics.colored_pixels,
        visible_pixels=metrics.visible_pixels,
        score_pixels=metrics.score_pixels,
        dominant_hue=metrics.dominant_hue,
    )


def _empty_color_metrics(
    visible_pixels: int = 0, score_pixels: int = 0
) -> _SlotColorMetrics:
    return _SlotColorMetrics(
        colored_ratio=0.0,
        visible_colored_ratio=0.0,
        p90_saturation=0.0,
        p90_channel_spread=0.0,
        colored_pixels=0,
        visible_pixels=visible_pixels,
        score_pixels=score_pixels,
        dominant_hue=None,
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


def _dead_slot_status(
    side: Side,
    index: int,
    bbox: BBox,
    visible_pixels: int = 0,
    score_pixels: int = 0,
) -> SlotStatus:
    metrics = _empty_color_metrics(visible_pixels, score_pixels)
    return _slot_status(side, index, bbox, False, metrics)


def _ellipse_mask(
    shape: tuple[int, int], inner_ignore_ratio: float = 0.0
) -> np.ndarray:
    height, width = shape
    yy, xx = np.ogrid[:height, :width]
    center_y = (height - 1) / 2.0
    center_x = (width - 1) / 2.0
    radius_y = max(height * 0.48, 1.0)
    radius_x = max(width * 0.48, 1.0)
    normalized = ((yy - center_y) / radius_y) ** 2 + (
        (xx - center_x) / radius_x
    ) ** 2
    outer = normalized <= 1.0
    if inner_ignore_ratio <= 0.0:
        return outer
    inner = normalized <= inner_ignore_ratio * inner_ignore_ratio
    return outer & ~inner


def _dominant_hue(hue: np.ndarray) -> float | None:
    if hue.size == 0:
        return None

    # OpenCV hue is 0..179. Doubling maps it onto a full 0..360 degree circle.
    radians = hue.astype(np.float32) * (2.0 * np.pi / 180.0)
    mean_sin = float(np.sin(radians).mean())
    mean_cos = float(np.cos(radians).mean())
    if mean_sin == 0.0 and mean_cos == 0.0:
        return None
    angle = np.arctan2(mean_sin, mean_cos)
    if angle < 0:
        angle += 2.0 * np.pi
    return float(angle * 90.0 / np.pi)
