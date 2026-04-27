from __future__ import annotations

from dataclasses import dataclass
from glob import glob
import subprocess
from typing import Protocol

import cv2
import numpy as np


class FrameSource(Protocol):
    def read(self) -> tuple[bool, np.ndarray | None]:
        ...

    def release(self) -> None:
        ...


class OpenCvFrameSource:
    def __init__(
        self,
        source: int | str,
        width: int | None = None,
        height: int | None = None,
        fps: float | None = None,
    ):
        self.cap = cv2.VideoCapture(source)
        if width is not None:
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        if height is not None:
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        if fps is not None:
            self.cap.set(cv2.CAP_PROP_FPS, fps)

        if not self.cap.isOpened():
            raise RuntimeError(f"failed to open video source: {source!r}")

    def read(self) -> tuple[bool, np.ndarray | None]:
        return self.cap.read()

    def release(self) -> None:
        self.cap.release()


@dataclass(frozen=True)
class ScreenRegion:
    left: int
    top: int
    width: int
    height: int


class ScreenFrameSource:
    def __init__(self, region: ScreenRegion | None = None):
        try:
            import mss
        except ImportError as exc:
            raise RuntimeError("screen capture requires mss: pip install mss") from exc

        self._mss_module = mss
        self._sct = mss.mss()
        if region is None:
            monitor = self._sct.monitors[1]
            self._monitor = {
                "left": monitor["left"],
                "top": monitor["top"],
                "width": monitor["width"],
                "height": monitor["height"],
            }
        else:
            self._monitor = {
                "left": region.left,
                "top": region.top,
                "width": region.width,
                "height": region.height,
            }

    def read(self) -> tuple[bool, np.ndarray | None]:
        shot = self._sct.grab(self._monitor)
        frame = np.asarray(shot)
        bgr = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
        return True, bgr

    def release(self) -> None:
        self._sct.close()


def create_source(
    source: str,
    width: int | None = None,
    height: int | None = None,
    fps: float | None = None,
) -> FrameSource:
    if source.startswith("screen"):
        return ScreenFrameSource(_parse_screen_region(source))
    return OpenCvFrameSource(_parse_opencv_source(source), width, height, fps)


def list_video_devices() -> list[str]:
    devices = sorted(glob("/dev/video*"))
    names: list[str] = []
    for dev in devices:
        name = _v4l2_name(dev)
        names.append(f"{dev}{' - ' + name if name else ''}")
    return names


def _parse_opencv_source(source: str) -> int | str:
    try:
        return int(source)
    except ValueError:
        return source


def _parse_screen_region(source: str) -> ScreenRegion | None:
    if source == "screen":
        return None
    prefix = "screen:"
    if not source.startswith(prefix):
        raise ValueError("screen source must be 'screen' or 'screen:left,top,width,height'")
    values = source[len(prefix) :].split(",")
    if len(values) != 4:
        raise ValueError("screen source must be 'screen:left,top,width,height'")
    left, top, width, height = (int(value.strip()) for value in values)
    if width <= 0 or height <= 0:
        raise ValueError("screen width and height must be positive")
    return ScreenRegion(left=left, top=top, width=width, height=height)


def _v4l2_name(device: str) -> str | None:
    try:
        completed = subprocess.run(
            ["v4l2-ctl", "-D", "-d", device],
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        return None
    if completed.returncode != 0:
        return None
    for line in completed.stdout.splitlines():
        stripped = line.strip()
        if stripped.startswith("Card type"):
            _, value = stripped.split(":", 1)
            return value.strip()
    return None

