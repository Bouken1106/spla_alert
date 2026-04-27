from __future__ import annotations

from dataclasses import dataclass
import html
import json
from pathlib import Path
import re
import time
from typing import Any
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

import cv2
import numpy as np

from .config import WeaponConfig


@dataclass(frozen=True)
class WeaponInfo:
    key: str
    name: str
    type_key: str | None
    image_url: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "name": self.name,
            "type_key": self.type_key,
            "image_url": self.image_url,
        }


@dataclass(frozen=True)
class WeaponCandidate:
    key: str
    name: str
    score: float
    image_url: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "name": self.name,
            "score": round(self.score, 4),
            "image_url": self.image_url,
        }


@dataclass(frozen=True)
class WeaponPrediction:
    key: str
    name: str
    score: float
    confidence: float
    image_url: str
    candidates: tuple[WeaponCandidate, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "name": self.name,
            "score": round(self.score, 4),
            "confidence": round(self.confidence, 4),
            "image_url": self.image_url,
            "candidates": [candidate.to_dict() for candidate in self.candidates],
        }


@dataclass(frozen=True)
class WeaponTemplate:
    info: WeaponInfo
    edges: np.ndarray
    distance: np.ndarray


class WeaponRecognizer:
    def __init__(
        self,
        config: WeaponConfig,
        templates: tuple[WeaponTemplate, ...] | None = None,
    ):
        self.config = config
        self._templates = templates
        self._load_failed = False

    def predict(self, slot_crop: np.ndarray) -> WeaponPrediction | None:
        templates = self._loaded_templates()
        if not templates:
            return None

        slot_edges = _extract_slot_edges(slot_crop, self.config)
        if _edge_ratio(slot_edges) < self.config.min_edge_ratio:
            return None

        slot_distance = _distance_from_edges(slot_edges)
        scores = tuple(
            _score_template(slot_edges, slot_distance, template)
            for template in templates
        )
        ranked = sorted(
            zip(templates, scores, strict=True),
            key=lambda item: item[1],
            reverse=True,
        )
        top_template, top_score = ranked[0]
        second_score = ranked[1][1] if len(ranked) > 1 else 0.0
        confidence = _confidence(top_score, second_score)
        if confidence < self.config.confidence_threshold:
            return None

        candidates = tuple(
            WeaponCandidate(
                key=template.info.key,
                name=template.info.name,
                score=score,
                image_url=template.info.image_url,
            )
            for template, score in ranked[: max(1, self.config.candidate_count)]
        )
        return WeaponPrediction(
            key=top_template.info.key,
            name=top_template.info.name,
            score=top_score,
            confidence=confidence,
            image_url=top_template.info.image_url,
            candidates=candidates,
        )

    def _loaded_templates(self) -> tuple[WeaponTemplate, ...]:
        if self._templates is not None or self._load_failed:
            return self._templates or ()
        try:
            self._templates = load_external_weapon_templates(self.config)
        except (OSError, ValueError, cv2.error):
            self._load_failed = True
            self._templates = ()
        return self._templates


def load_external_weapon_templates(config: WeaponConfig) -> tuple[WeaponTemplate, ...]:
    cache_dir = Path(config.cache_dir).expanduser()
    manifest = _load_or_fetch_manifest(config, cache_dir)
    templates: list[WeaponTemplate] = []
    for info in _weapon_infos(manifest):
        image_path = _cached_image_path(cache_dir, info.key)
        if config.refresh_cache or not image_path.exists():
            try:
                _download_file(info.image_url, image_path, config)
            except OSError:
                continue
        try:
            image = _read_image(image_path)
        except OSError:
            continue
        if image is None:
            continue
        template = _template_from_image(info, image, config.template_size)
        if template is not None:
            templates.append(template)
        if config.max_templates > 0 and len(templates) >= config.max_templates:
            break
    return tuple(templates)


def _load_or_fetch_manifest(
    config: WeaponConfig, cache_dir: Path
) -> dict[str, Any]:
    manifest_path = cache_dir / "manifest.json"
    if (
        not config.refresh_cache
        and manifest_path.exists()
        and not _cache_expired(manifest_path, config.cache_ttl_hours)
    ):
        return json.loads(manifest_path.read_text(encoding="utf-8"))

    cache_dir.mkdir(parents=True, exist_ok=True)
    api_data = _download_json(config.api_url, config)
    source_html = _download_text(config.source_url, config)
    image_urls = _image_urls_from_stat_ink_page(source_html, config.source_url)
    weapons = _manifest_weapons(api_data, image_urls)
    manifest = {
        "generated_at": time.time(),
        "api_url": config.api_url,
        "source_url": config.source_url,
        "weapons": weapons,
    }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def _manifest_weapons(
    api_data: list[dict[str, Any]], image_urls: dict[str, str]
) -> list[dict[str, Any]]:
    weapons: list[dict[str, Any]] = []
    for item in api_data:
        key = str(item.get("key", ""))
        image_url = image_urls.get(key)
        if not key or image_url is None:
            continue
        name = item.get("name", {})
        type_info = item.get("type", {})
        weapons.append(
            {
                "key": key,
                "name": str(name.get("ja_JP") or name.get("en_US") or key),
                "type_key": (
                    type_info.get("key") if isinstance(type_info, dict) else None
                ),
                "image_url": image_url,
            }
        )
    return weapons


def _weapon_infos(manifest: dict[str, Any]) -> tuple[WeaponInfo, ...]:
    infos = []
    for item in manifest.get("weapons", []):
        infos.append(
            WeaponInfo(
                key=str(item["key"]),
                name=str(item.get("name") or item["key"]),
                type_key=item.get("type_key"),
                image_url=str(item["image_url"]),
            )
        )
    return tuple(infos)


def _image_urls_from_stat_ink_page(source_html: str, source_url: str) -> dict[str, str]:
    urls: dict[str, str] = {}
    pattern = r"<img\b[^>]*\bsrc=[\"']([^\"']+\.png[^\"']*)"
    for match in re.finditer(pattern, source_html):
        raw_url = html.unescape(match.group(1))
        absolute_url = urljoin(source_url, raw_url)
        path = urlparse(absolute_url).path
        key = Path(path).stem
        if key and key not in urls:
            urls[key] = absolute_url
    return urls


def _download_json(url: str, config: WeaponConfig) -> list[dict[str, Any]]:
    raw = _download_text(url, config)
    data = json.loads(raw)
    if not isinstance(data, list):
        raise OSError(f"weapon API returned {type(data).__name__}, expected list")
    return data


def _download_text(url: str, config: WeaponConfig) -> str:
    request = Request(url, headers={"User-Agent": config.user_agent})
    with urlopen(request, timeout=config.download_timeout_seconds) as response:
        return response.read().decode("utf-8")


def _download_file(url: str, path: Path, config: WeaponConfig) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    request = Request(url, headers={"User-Agent": config.user_agent})
    with urlopen(request, timeout=config.download_timeout_seconds) as response:
        path.write_bytes(response.read())


def _cached_image_path(cache_dir: Path, key: str) -> Path:
    return cache_dir / "images" / f"{key}.png"


def _cache_expired(path: Path, ttl_hours: int) -> bool:
    if ttl_hours <= 0:
        return True
    return time.time() - path.stat().st_mtime > ttl_hours * 60 * 60


def _read_image(path: Path) -> np.ndarray | None:
    raw = np.frombuffer(path.read_bytes(), dtype=np.uint8)
    image = cv2.imdecode(raw, cv2.IMREAD_UNCHANGED)
    return image


def _template_from_image(
    info: WeaponInfo, image: np.ndarray, size: int
) -> WeaponTemplate | None:
    square = _resize_to_square(image, size)
    if square.shape[2] == 4:
        bgr = square[:, :, :3]
        alpha = square[:, :, 3]
    else:
        bgr = square[:, :, :3]
        alpha = np.full(square.shape[:2], 255, dtype=np.uint8)

    foreground = alpha > 16
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    gray = np.where(foreground, gray, 0).astype(np.uint8)
    alpha_edges = cv2.Canny(alpha, 32, 96) > 0
    gray_edges = cv2.Canny(gray, 48, 144) > 0
    edges = (alpha_edges | gray_edges) & _center_keep_mask(gray.shape)
    if int(edges.sum()) < max(6, size):
        return None
    return WeaponTemplate(info=info, edges=edges, distance=_distance_from_edges(edges))


def _extract_slot_edges(crop: np.ndarray, config: WeaponConfig) -> np.ndarray:
    weapon_crop = _weapon_crop(crop, config)
    if weapon_crop.size == 0:
        return np.zeros((config.template_size, config.template_size), dtype=bool)

    resized = cv2.resize(
        weapon_crop,
        (config.template_size, config.template_size),
        interpolation=cv2.INTER_AREA,
    )
    gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(resized, cv2.COLOR_BGR2HSV)
    saturation = hsv[:, :, 1]
    value = hsv[:, :, 2]

    weapon_like = (saturation <= 115) | (value <= 78) | (value >= 225)
    weapon_like = cv2.morphologyEx(
        weapon_like.astype(np.uint8),
        cv2.MORPH_CLOSE,
        np.ones((3, 3), dtype=np.uint8),
    ).astype(bool)
    weapon_like = cv2.dilate(
        weapon_like.astype(np.uint8), np.ones((3, 3), dtype=np.uint8), iterations=1
    ).astype(bool)

    blurred = cv2.GaussianBlur(gray, (3, 3), 0)
    edges = cv2.Canny(blurred, 42, 132) > 0
    edges &= weapon_like & _center_keep_mask(gray.shape)
    edges[:2, :] = False
    edges[-2:, :] = False
    edges[:, :2] = False
    edges[:, -2:] = False
    return edges


def _weapon_crop(crop: np.ndarray, config: WeaponConfig) -> np.ndarray:
    height, width = crop.shape[:2]
    x1 = int(round(width * config.crop_left_ratio))
    y1 = int(round(height * config.crop_top_ratio))
    x2 = int(round(width * config.crop_right_ratio))
    y2 = int(round(height * config.crop_bottom_ratio))
    x1 = max(0, min(width, x1))
    x2 = max(x1, min(width, x2))
    y1 = max(0, min(height, y1))
    y2 = max(y1, min(height, y2))
    return crop[y1:y2, x1:x2]


def _score_template(
    slot_edges: np.ndarray,
    slot_distance: np.ndarray,
    template: WeaponTemplate,
) -> float:
    if not slot_edges.any() or not template.edges.any():
        return 0.0

    size = slot_edges.shape[0]
    max_distance = max(3.0, size * 0.12)
    slot_to_template = float(
        np.minimum(template.distance[slot_edges], max_distance).mean()
    )
    template_to_slot = float(
        np.minimum(slot_distance[template.edges], max_distance).mean()
    )
    distance = (slot_to_template * 0.62) + (template_to_slot * 0.38)
    return max(0.0, 1.0 - (distance / max_distance))


def _confidence(top_score: float, second_score: float) -> float:
    margin = max(0.0, top_score - second_score)
    return min(1.0, top_score * 0.78 + margin * 1.4)


def _distance_from_edges(edges: np.ndarray) -> np.ndarray:
    inverse = (~edges).astype(np.uint8)
    return cv2.distanceTransform(inverse, cv2.DIST_L2, 3)


def _resize_to_square(image: np.ndarray, size: int) -> np.ndarray:
    if image.ndim != 3:
        raise ValueError("weapon template image must have channels")
    height, width = image.shape[:2]
    scale = min(size / max(width, 1), size / max(height, 1))
    resized_width = max(1, int(round(width * scale)))
    resized_height = max(1, int(round(height * scale)))
    resized = cv2.resize(
        image,
        (resized_width, resized_height),
        interpolation=cv2.INTER_AREA,
    )
    channels = resized.shape[2]
    square = np.zeros((size, size, channels), dtype=resized.dtype)
    x = (size - resized_width) // 2
    y = (size - resized_height) // 2
    square[y : y + resized_height, x : x + resized_width] = resized
    return square


def _center_keep_mask(shape: tuple[int, int]) -> np.ndarray:
    height, width = shape
    yy, xx = np.ogrid[:height, :width]
    center_y = (height - 1) / 2.0
    center_x = (width - 1) / 2.0
    radius_y = max(height * 0.48, 1.0)
    radius_x = max(width * 0.48, 1.0)
    return ((yy - center_y) / radius_y) ** 2 + (
        (xx - center_x) / radius_x
    ) ** 2 <= 1.0


def _edge_ratio(edges: np.ndarray) -> float:
    if edges.size == 0:
        return 0.0
    return float(edges.mean())
