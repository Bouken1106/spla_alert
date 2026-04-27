from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field, replace
import json
from pathlib import Path
from typing import Any


SLOT_COUNT = 4
SlotCenters = tuple[float, float, float, float]
DEFAULT_FRIENDLY_X = (0.374, 0.409, 0.444, 0.479)
DEFAULT_ENEMY_X = (0.521, 0.556, 0.591, 0.626)


@dataclass(frozen=True)
class HudConfig:
    slot_center_y: float = 0.058
    slot_size: float = 0.074
    friendly_slot_centers_x: SlotCenters = DEFAULT_FRIENDLY_X
    enemy_slot_centers_x: SlotCenters = DEFAULT_ENEMY_X


@dataclass(frozen=True)
class ClassifierConfig:
    saturation_threshold: int = 60
    value_min: int = 45
    colored_ratio_threshold: float = 0.08
    weak_colored_ratio_threshold: float = 0.045
    p90_saturation_threshold: int = 100
    min_colored_pixels: int = 40


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
    return ClassifierConfig(
        saturation_threshold=int(
            raw.get("saturation_threshold", default.saturation_threshold)
        ),
        value_min=int(raw.get("value_min", default.value_min)),
        colored_ratio_threshold=float(
            raw.get("colored_ratio_threshold", default.colored_ratio_threshold)
        ),
        weak_colored_ratio_threshold=float(
            raw.get("weak_colored_ratio_threshold", default.weak_colored_ratio_threshold)
        ),
        p90_saturation_threshold=int(
            raw.get("p90_saturation_threshold", default.p90_saturation_threshold)
        ),
        min_colored_pixels=int(
            raw.get("min_colored_pixels", default.min_colored_pixels)
        ),
    )


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
