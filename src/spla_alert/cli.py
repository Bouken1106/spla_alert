from __future__ import annotations

import argparse
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
import json
import sys
import time
from pathlib import Path

import cv2

from .config import load_config
from .detector import CountResult, SplatoonHudDetector, draw_overlay
from .source import FrameSource, create_source, list_video_devices


@dataclass(frozen=True)
class DetectionRuntime:
    detector: SplatoonHudDetector
    source: FrameSource


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "devices":
        return _devices()
    if args.command == "snapshot":
        return _snapshot(args)
    if args.command == "run":
        return _run(args)

    parser.print_help()
    return 2


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="spla-alert")
    subparsers = parser.add_subparsers(dest="command")

    devices = subparsers.add_parser("devices", help="list /dev/video* capture devices")
    devices.set_defaults(command="devices")

    snapshot = subparsers.add_parser(
        "snapshot", help="save one frame with HUD slot overlay"
    )
    _add_source_args(snapshot)
    snapshot.add_argument("--output", default="snapshot_overlay.jpg")
    snapshot.add_argument(
        "--json-output",
        default=None,
        help="optional path to save the detailed snapshot result as JSON",
    )
    snapshot.add_argument(
        "--crops-dir",
        default=None,
        help="optional directory to save the 8 detected slot crops",
    )
    snapshot.set_defaults(command="snapshot")

    run = subparsers.add_parser("run", help="count alive icons in realtime")
    _add_source_args(run)
    run.add_argument("--every", type=int, default=10, help="process every N frames")
    run.add_argument("--show", action="store_true", help="show OpenCV preview window")
    run.add_argument(
        "--json-lines",
        action="store_true",
        help="print one JSON result for each processed frame",
    )
    run.add_argument(
        "--max-frames",
        type=int,
        default=0,
        help="stop after N captured frames; 0 means forever",
    )
    run.set_defaults(command="run")

    return parser


def _add_source_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--source",
        default="/dev/video0",
        help=(
            "OpenCV source: /dev/video0, 0, video file, RTMP/RTSP URL, "
            "or screen:left,top,width,height"
        ),
    )
    parser.add_argument(
        "--config",
        default=None,
        help="optional JSON config; built-in defaults are used when omitted",
    )
    parser.add_argument("--width", type=int, default=None)
    parser.add_argument("--height", type=int, default=None)
    parser.add_argument("--fps", type=float, default=None)
    parser.add_argument(
        "--buffer-size",
        type=int,
        default=1,
        help="OpenCV capture buffer size for /dev/video* or stream sources",
    )
    parser.add_argument(
        "--fourcc",
        default=None,
        help="optional 4-character capture format for /dev/video*, for example MJPG",
    )


def _devices() -> int:
    devices = list_video_devices()
    if not devices:
        print("No /dev/video* devices found.")
        return 1
    for device in devices:
        print(device)
    return 0


def _snapshot(args: argparse.Namespace) -> int:
    with _detection_runtime(args) as runtime:
        ok, frame = runtime.source.read()
        if not ok or frame is None:
            print("failed to read a frame", file=sys.stderr)
            return 1
        result = runtime.detector.count(frame, 0)
        overlay = draw_overlay(frame, result)
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        if not cv2.imwrite(str(output), overlay):
            print(f"failed to write {output}", file=sys.stderr)
            return 1
        if args.json_output is not None:
            _save_json_result(result, Path(args.json_output))
        if args.crops_dir is not None:
            if not _save_slot_crops(frame, result, Path(args.crops_dir)):
                return 1
        print(f"saved {output}")
        print(_format_result(result))
        return 0


def _run(args: argparse.Namespace) -> int:
    if args.every <= 0:
        print("--every must be positive", file=sys.stderr)
        return 2

    frame_index = 0
    last_result = None

    try:
        with _detection_runtime(args) as runtime:
            while True:
                ok, frame = runtime.source.read()
                if not ok or frame is None:
                    print("source ended or failed to read", file=sys.stderr)
                    return 1

                if frame_index % args.every == 0:
                    last_result = runtime.detector.count(frame, frame_index)
                    _print_result(last_result, args.json_lines)

                if args.show and _preview_requested(frame, last_result):
                    break

                frame_index += 1
                if args.max_frames and frame_index >= args.max_frames:
                    break

    except KeyboardInterrupt:
        return 0
    finally:
        if args.show:
            cv2.destroyAllWindows()
    return 0


@contextmanager
def _detection_runtime(args: argparse.Namespace) -> Iterator[DetectionRuntime]:
    config = load_config(args.config)
    source = create_source(
        args.source,
        args.width,
        args.height,
        args.fps,
        args.buffer_size,
        args.fourcc,
    )
    try:
        yield DetectionRuntime(SplatoonHudDetector(config), source)
    finally:
        source.release()


def _print_result(result: CountResult, json_lines: bool) -> None:
    if json_lines:
        print(json.dumps(result.to_dict(), ensure_ascii=False), flush=True)
    else:
        print(_format_result(result), flush=True)


def _preview_requested(frame, result: CountResult | None) -> bool:
    preview = draw_overlay(frame, result) if result else frame
    cv2.imshow("spla-alert", preview)
    key = cv2.waitKey(1) & 0xFF
    return key in (ord("q"), 27)


def _format_result(result: CountResult) -> str:
    timestamp = time.strftime("%H:%M:%S", time.localtime(result.processed_at))
    return (
        f"{timestamp} frame={result.frame_index} "
        f"friendly={result.friendly_alive}/4 enemy={result.enemy_alive}/4"
    )


def _save_json_result(result: CountResult, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(result.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _save_slot_crops(frame, result: CountResult, crops_dir: Path) -> bool:
    crops_dir.mkdir(parents=True, exist_ok=True)
    ok = True
    for slot in result.slots:
        x1, y1, x2, y2 = slot.bbox
        state = "alive" if slot.alive else "dead"
        filename = f"{slot.side}_{slot.index + 1}_{state}.jpg"
        crop = frame[y1:y2, x1:x2]
        if not cv2.imwrite(str(crops_dir / filename), crop):
            print(f"failed to write {crops_dir / filename}", file=sys.stderr)
            ok = False
    return ok


if __name__ == "__main__":
    raise SystemExit(main())
