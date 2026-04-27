from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field, replace
import json
from pathlib import Path
from typing import Any


SLOT_COUNT = 4
SlotCenters = tuple[float, float, float, float]
DEFAULT_FRIENDLY_X = (0.374, 0.409, 0.444, 0.479)
DEFAULT_ENEMY_X = (0.521, 0.556, 0.591, 0.626)
_CLASSIFIER_INT_FIELDS = (
    "saturation_threshold",
    "channel_spread_threshold",
    "value_min",
    "x_mark_value_min",
    "x_mark_saturation_max",
    "p90_saturation_threshold",
    "p90_channel_spread_threshold",
    "min_colored_pixels",
)
_CLASSIFIER_FLOAT_FIELDS = (
    "lab_chroma_threshold",
    "colored_ratio_threshold",
    "weak_colored_ratio_threshold",
    "visible_colored_ratio_threshold",
    "min_colored_area_ratio",
    "inner_ignore_ratio",
    "x_mark_line_ratio_threshold",
    "x_mark_contrast_threshold",
    "x_mark_band_width",
    "x_mark_max_colored_ratio",
)


@dataclass(frozen=True)
class HudConfig:
    slot_center_y: float = 0.058
    slot_size: float = 0.074
    friendly_slot_centers_x: SlotCenters = DEFAULT_FRIENDLY_X
    enemy_slot_centers_x: SlotCenters = DEFAULT_ENEMY_X


@dataclass(frozen=True)
class ClassifierConfig:
    saturation_threshold: int = 60
    channel_spread_threshold: int = 35
    lab_chroma_threshold: float = 22.0
    value_min: int = 45
    colored_ratio_threshold: float = 0.08
    weak_colored_ratio_threshold: float = 0.045
    visible_colored_ratio_threshold: float = 0.22
    p90_saturation_threshold: int = 100
    p90_channel_spread_threshold: int = 70
    min_colored_pixels: int = 40
    min_colored_area_ratio: float = 0.012
    inner_ignore_ratio: float = 0.26
    x_mark_value_min: int = 80
    x_mark_saturation_max: int = 70
    x_mark_line_ratio_threshold: float = 0.24
    x_mark_contrast_threshold: float = 0.11
    x_mark_band_width: float = 0.12
    x_mark_max_colored_ratio: float = 0.62


@dataclass(frozen=True)
class AppConfig:
    hud: HudConfig = field(default_factory=HudConfig)
    classifier: ClassifierConfig = field(default_factory=ClassifierConfig)


def load_config(path: str | Path | None) -> AppConfig:
    if path is None:
        return AppConfig()

    config_path = Path(path)
    with config_path.open("r", encoding="utf-8") as f:
        raw = json.load(f)

    config = AppConfig()
    hud_raw = raw.get("hud", {})
    classifier_raw = raw.get("classifier", {})

    if hud_raw:
        config = replace(config, hud=_load_hud(config.hud, hud_raw))
    if classifier_raw:
        config = replace(
            config, classifier=_load_classifier(config.classifier, classifier_raw)
        )
    return config


def _load_hud(default: HudConfig, raw: dict[str, Any]) -> HudConfig:
    return HudConfig(
        slot_center_y=float(raw.get("slot_center_y", default.slot_center_y)),
        slot_size=float(raw.get("slot_size", default.slot_size)),
        friendly_slot_centers_x=_slot_centers(
            raw.get("friendly_slot_centers_x", default.friendly_slot_centers_x),
            "friendly_slot_centers_x",
        ),
        enemy_slot_centers_x=_slot_centers(
            raw.get("enemy_slot_centers_x", default.enemy_slot_centers_x),
            "enemy_slot_centers_x",
        ),
    )


def _load_classifier(
    default: ClassifierConfig, raw: dict[str, Any]
) -> ClassifierConfig:
    overrides: dict[str, Any] = {}
    overrides.update(_coerced_overrides(raw, _CLASSIFIER_INT_FIELDS, int))
    overrides.update(_coerced_overrides(raw, _CLASSIFIER_FLOAT_FIELDS, float))
    return replace(default, **overrides)


def _coerced_overrides(
    raw: dict[str, Any],
    field_names: tuple[str, ...],
    coerce: Callable[[Any], Any],
) -> dict[str, Any]:
    return {name: coerce(raw[name]) for name in field_names if name in raw}


def _slot_centers(value: Any, field_name: str) -> SlotCenters:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise ValueError(f"{field_name} must contain exactly {SLOT_COUNT} values")
    if len(value) != SLOT_COUNT:
        raise ValueError(f"{field_name} must contain exactly {SLOT_COUNT} values")
    return (
        float(value[0]),
        float(value[1]),
        float(value[2]),
        float(value[3]),
    )
