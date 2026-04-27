from __future__ import annotations

from dataclasses import dataclass, replace
import time
from typing import Any, Iterable, Literal

import cv2
import numpy as np

from .config import AppConfig, ClassifierConfig


Side = Literal["friendly", "enemy"]
BBox = tuple[int, int, int, int]
SlotRegion = tuple[Side, int, BBox]


_SLOT_PROBE_OFFSETS = (
    (-0.22, -0.30),
    (0.00, -0.32),
    (0.22, -0.30),
    (-0.30, -0.22),
    (0.30, -0.22),
    (-0.34, 0.00),
    (-0.20, 0.00),
    (0.20, 0.00),
    (0.34, 0.00),
    (-0.30, 0.22),
    (0.30, 0.22),
    (-0.22, 0.30),
    (0.00, 0.32),
    (0.22, 0.30),
    (-0.18, -0.18),
    (0.18, -0.18),
    (-0.18, 0.18),
    (0.18, 0.18),
)


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
    x_mark_score: float
    x_mark_min_line_ratio: float


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
    x_mark_score: float
    x_mark_min_line_ratio: float

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
            "x_mark_score": round(self.x_mark_score, 4),
            "x_mark_min_line_ratio": round(self.x_mark_min_line_ratio, 4),
        }


@dataclass(frozen=True)
class CountResult:
    frame_index: int
    hud_present: bool
    friendly_alive: int
    enemy_alive: int
    slots: tuple[SlotStatus, ...]
    processed_at: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "frame_index": self.frame_index,
            "hud_present": self.hud_present,
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
        hud_present = (
            _hud_present(frame, slots, self.config)
            if self.config.classifier.require_hud_presence
            else True
        )
        if not hud_present:
            slots = tuple(replace(slot, alive=False) for slot in slots)

        friendly_alive = _alive_count(slots, "friendly")
        enemy_alive = _alive_count(slots, "enemy")

        return CountResult(
            frame_index=frame_index,
            hud_present=hud_present,
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

    score_mask = _probe_sample_mask(crop.shape[:2], cfg.probe_radius_ratio)
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
    x_mark_score, x_mark_min_line_ratio = _x_mark_score(crop, cfg)

    return _SlotColorMetrics(
        colored_ratio=colored_pixels / score_pixels,
        visible_colored_ratio=colored_pixels / visible_pixels,
        p90_saturation=float(np.percentile(saturation[visible_mask], 90)),
        p90_channel_spread=float(np.percentile(channel_spread[visible_mask], 90)),
        colored_pixels=colored_pixels,
        visible_pixels=visible_pixels,
        score_pixels=score_pixels,
        dominant_hue=_dominant_hue(hsv[:, :, 0][colored_mask]),
        x_mark_score=x_mark_score,
        x_mark_min_line_ratio=x_mark_min_line_ratio,
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


def _probe_sample_mask(
    shape: tuple[int, int], probe_radius_ratio: float
) -> np.ndarray:
    height, width = shape
    mask = np.zeros(shape, dtype=np.uint8)
    if height <= 0 or width <= 0:
        return mask.astype(bool)

    radius = max(1, int(round(min(height, width) * probe_radius_ratio)))
    for offset_x, offset_y in _SLOT_PROBE_OFFSETS:
        center_x = int(round((0.5 + offset_x) * (width - 1)))
        center_y = int(round((0.5 + offset_y) * (height - 1)))
        cv2.circle(mask, (center_x, center_y), radius, 1, thickness=-1)
    return mask.astype(bool)


def _is_alive(metrics: _SlotColorMetrics, cfg: ClassifierConfig) -> bool:
    if metrics.score_pixels == 0 or metrics.visible_pixels == 0:
        return False

    if (
        metrics.x_mark_score >= cfg.x_mark_contrast_threshold
        and metrics.x_mark_min_line_ratio >= cfg.x_mark_line_ratio_threshold
        and metrics.colored_ratio <= cfg.x_mark_max_colored_ratio
    ):
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


def _hud_present(
    frame: np.ndarray, slots: tuple[SlotStatus, ...], config: AppConfig
) -> bool:
    cfg = config.classifier
    return (
        _timer_present(frame, config)
        and _alive_count(slots, "friendly") + _alive_count(slots, "enemy")
        >= cfg.hud_min_alive_slots
        and _team_hues_are_separated(slots, cfg)
    )


def _timer_present(frame: np.ndarray, config: AppConfig) -> bool:
    cfg = config.classifier
    height, width = frame.shape[:2]
    crop_width = max(16, int(round(cfg.hud_timer_width_ratio * width)))
    crop_height = max(12, int(round(cfg.hud_timer_height_ratio * height)))
    center_x = width // 2
    center_y = int(round(config.hud.slot_center_y * height))
    x1 = max(0, center_x - crop_width // 2)
    x2 = min(width, center_x + crop_width // 2)
    y1 = max(0, center_y - crop_height // 2)
    y2 = min(height, center_y + crop_height // 2)
    crop = frame[y1:y2, x1:x2]
    if crop.size == 0:
        return False

    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    saturation = hsv[:, :, 1]
    value = hsv[:, :, 2]
    bright_timer_pixels = (value >= cfg.hud_timer_bright_value_min) & (
        saturation <= cfg.hud_timer_bright_saturation_max
    )
    dark_timer_pixels = value <= cfg.hud_timer_dark_value_max
    center_edges = _timer_center_edge_ratio(crop)
    return (
        float(bright_timer_pixels.mean()) >= cfg.hud_timer_bright_ratio_threshold
        and float(dark_timer_pixels.mean()) >= cfg.hud_timer_dark_ratio_threshold
        and center_edges >= cfg.hud_timer_edge_ratio_threshold
    )


def _timer_center_edge_ratio(crop: np.ndarray) -> float:
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 60, 160)
    height, width = edges.shape[:2]
    center = edges[
        height * 15 // 100 : height * 85 // 100,
        width * 35 // 100 : width * 65 // 100,
    ]
    if center.size == 0:
        return 0.0
    return float((center > 0).mean())


def _team_hues_are_separated(
    slots: tuple[SlotStatus, ...], cfg: ClassifierConfig
) -> bool:
    friendly_hue = _side_hue(slots, "friendly", cfg.hud_team_hue_slots_min)
    enemy_hue = _side_hue(slots, "enemy", cfg.hud_team_hue_slots_min)
    if friendly_hue is None or enemy_hue is None:
        return True
    return _hue_distance(friendly_hue, enemy_hue) >= cfg.hud_min_team_hue_distance


def _side_hue(
    slots: tuple[SlotStatus, ...], side: Side, min_slots: int
) -> float | None:
    hues = [
        slot.dominant_hue
        for slot in slots
        if slot.side == side and slot.alive and slot.dominant_hue is not None
    ]
    if len(hues) < min_slots:
        return None
    return _circular_mean(tuple(hues))


def _circular_mean(angles: tuple[float, ...]) -> float | None:
    if not angles:
        return None
    radians = np.deg2rad(np.array(angles, dtype=np.float32))
    mean_sin = float(np.sin(radians).mean())
    mean_cos = float(np.cos(radians).mean())
    if mean_sin == 0.0 and mean_cos == 0.0:
        return None
    angle = np.arctan2(mean_sin, mean_cos)
    if angle < 0:
        angle += 2.0 * np.pi
    return float(np.rad2deg(angle))


def _hue_distance(a: float, b: float) -> float:
    return abs((a - b + 180.0) % 360.0 - 180.0)


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
        x_mark_score=metrics.x_mark_score,
        x_mark_min_line_ratio=metrics.x_mark_min_line_ratio,
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
        x_mark_score=0.0,
        x_mark_min_line_ratio=0.0,
    )


def _x_mark_score(crop: np.ndarray, cfg: ClassifierConfig) -> tuple[float, float]:
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    saturation = hsv[:, :, 1]
    value = hsv[:, :, 2]
    pale_mask = (value >= cfg.x_mark_value_min) & (
        saturation <= cfg.x_mark_saturation_max
    )

    main, anti, outside = _x_mark_masks(crop.shape[:2], cfg.x_mark_band_width)
    main_ratio = _mask_ratio(pale_mask, main)
    anti_ratio = _mask_ratio(pale_mask, anti)
    outside_ratio = _mask_ratio(pale_mask, outside)
    min_line_ratio = min(main_ratio, anti_ratio)
    return max(0.0, min_line_ratio - outside_ratio), min_line_ratio


def _x_mark_masks(
    shape: tuple[int, int], band_width: float
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    height, width = shape
    yy, xx = np.mgrid[:height, :width]
    normalized_x = (xx + 0.5) / max(width, 1)
    normalized_y = (yy + 0.5) / max(height, 1)

    main = np.abs(normalized_y - normalized_x) <= band_width
    anti = np.abs((normalized_y + normalized_x) - 1.0) <= band_width
    ellipse = _ellipse_mask(shape)
    line_mask = (main | anti) & ellipse
    return main & ellipse, anti & ellipse, ellipse & ~line_mask


def _mask_ratio(source_mask: np.ndarray, target_mask: np.ndarray) -> float:
    target_pixels = int(target_mask.sum())
    if target_pixels == 0:
        return 0.0
    return float((source_mask & target_mask).sum() / target_pixels)


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
    text = (
        f"friendly {result.friendly_alive}/4  enemy {result.enemy_alive}/4"
        if result.hud_present
        else "HUD not found"
    )
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
