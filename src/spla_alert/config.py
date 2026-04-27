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
    "hud_timer_bright_value_min",
    "hud_timer_bright_saturation_max",
    "hud_timer_dark_value_max",
    "hud_team_hue_slots_min",
    "hud_min_alive_slots",
)
_CLASSIFIER_FLOAT_FIELDS = (
    "lab_chroma_threshold",
    "colored_ratio_threshold",
    "weak_colored_ratio_threshold",
    "visible_colored_ratio_threshold",
    "min_colored_area_ratio",
    "x_mark_line_ratio_threshold",
    "x_mark_contrast_threshold",
    "x_mark_band_width",
    "x_mark_max_colored_ratio",
    "probe_radius_ratio",
    "hud_timer_width_ratio",
    "hud_timer_height_ratio",
    "hud_timer_bright_ratio_threshold",
    "hud_timer_dark_ratio_threshold",
    "hud_timer_edge_ratio_threshold",
    "hud_min_team_hue_distance",
)
_CLASSIFIER_BOOL_FIELDS = (
    "require_hud_presence",
)
_WEAPON_INT_FIELDS = (
    "template_size",
    "max_templates",
    "candidate_count",
    "cache_ttl_hours",
    "download_timeout_seconds",
)
_WEAPON_FLOAT_FIELDS = (
    "confidence_threshold",
    "min_edge_ratio",
    "crop_left_ratio",
    "crop_top_ratio",
    "crop_right_ratio",
    "crop_bottom_ratio",
)
_WEAPON_BOOL_FIELDS = (
    "enabled",
    "refresh_cache",
)
_WEAPON_STR_FIELDS = (
    "api_url",
    "source_url",
    "cache_dir",
    "user_agent",
)


@dataclass(frozen=True)
class HudConfig:
    slot_center_y: float = 0.058
    slot_size: float = 0.074
    friendly_slot_centers_x: SlotCenters = DEFAULT_FRIENDLY_X
    enemy_slot_centers_x: SlotCenters = DEFAULT_ENEMY_X


@dataclass(frozen=True)
class ClassifierConfig:
    require_hud_presence: bool = True
    saturation_threshold: int = 60
    channel_spread_threshold: int = 35
    lab_chroma_threshold: float = 22.0
    value_min: int = 45
    colored_ratio_threshold: float = 0.08
    weak_colored_ratio_threshold: float = 0.045
    visible_colored_ratio_threshold: float = 0.22
    p90_saturation_threshold: int = 100
    p90_channel_spread_threshold: int = 70
    min_colored_pixels: int = 12
    min_colored_area_ratio: float = 0.012
    x_mark_value_min: int = 80
    x_mark_saturation_max: int = 70
    x_mark_line_ratio_threshold: float = 0.24
    x_mark_contrast_threshold: float = 0.11
    x_mark_band_width: float = 0.12
    x_mark_max_colored_ratio: float = 0.62
    probe_radius_ratio: float = 0.035
    hud_timer_width_ratio: float = 0.09
    hud_timer_height_ratio: float = 0.06
    hud_timer_bright_value_min: int = 185
    hud_timer_bright_saturation_max: int = 95
    hud_timer_dark_value_max: int = 60
    hud_timer_bright_ratio_threshold: float = 0.045
    hud_timer_dark_ratio_threshold: float = 0.16
    hud_timer_edge_ratio_threshold: float = 0.07
    hud_team_hue_slots_min: int = 2
    hud_min_alive_slots: int = 1
    hud_min_team_hue_distance: float = 25.0


@dataclass(frozen=True)
class WeaponConfig:
    enabled: bool = False
    api_url: str = "https://stat.ink/api/v3/weapon"
    source_url: str = "https://stat.ink/api-info/weapon3"
    cache_dir: str = "local_assets/weapons/stat_ink_weapon3"
    user_agent: str = "spla-alert/0.1"
    template_size: int = 64
    max_templates: int = 0
    candidate_count: int = 3
    cache_ttl_hours: int = 24 * 7
    download_timeout_seconds: int = 30
    refresh_cache: bool = False
    confidence_threshold: float = 0.42
    min_edge_ratio: float = 0.01
    crop_left_ratio: float = 0.08
    crop_top_ratio: float = 0.10
    crop_right_ratio: float = 0.92
    crop_bottom_ratio: float = 0.88


@dataclass(frozen=True)
class AppConfig:
    hud: HudConfig = field(default_factory=HudConfig)
    classifier: ClassifierConfig = field(default_factory=ClassifierConfig)
    weapons: WeaponConfig = field(default_factory=WeaponConfig)


def load_config(path: str | Path | None) -> AppConfig:
    if path is None:
        return AppConfig()

    config_path = Path(path)
    with config_path.open("r", encoding="utf-8") as f:
        raw = json.load(f)

    config = AppConfig()
    hud_raw = raw.get("hud", {})
    classifier_raw = raw.get("classifier", {})
    weapons_raw = raw.get("weapons", {})

    if hud_raw:
        config = replace(config, hud=_load_hud(config.hud, hud_raw))
    if classifier_raw:
        config = replace(
            config, classifier=_load_classifier(config.classifier, classifier_raw)
        )
    if weapons_raw:
        config = replace(config, weapons=_load_weapons(config.weapons, weapons_raw))
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
    overrides.update(_coerced_overrides(raw, _CLASSIFIER_BOOL_FIELDS, _coerce_bool))
    return replace(default, **overrides)


def _load_weapons(default: WeaponConfig, raw: dict[str, Any]) -> WeaponConfig:
    overrides: dict[str, Any] = {}
    overrides.update(_coerced_overrides(raw, _WEAPON_INT_FIELDS, int))
    overrides.update(_coerced_overrides(raw, _WEAPON_FLOAT_FIELDS, float))
    overrides.update(_coerced_overrides(raw, _WEAPON_BOOL_FIELDS, _coerce_bool))
    overrides.update(_coerced_overrides(raw, _WEAPON_STR_FIELDS, str))
    return replace(default, **overrides)


def _coerced_overrides(
    raw: dict[str, Any],
    field_names: tuple[str, ...],
    coerce: Callable[[Any], Any],
) -> dict[str, Any]:
    return {name: coerce(raw[name]) for name in field_names if name in raw}


def _coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes", "on")
    return bool(value)


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
