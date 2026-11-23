from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from smartcut.exceptions import ProbeError
from smartcut.ffmpeg import run_ffprobe

CSV_WITHOUT_SECTION_NAME = "csv=print_section=0"
KEYFRAME_FLAG = "K"


@dataclass(frozen=True)
class StreamInfo:
    index: int
    codec_type: str
    codec_name: str
    type_index: int
    is_attached_pic: bool
    pix_fmt: str | None
    bit_rate: int | None


@dataclass(frozen=True)
class MediaInfo:
    path: Path
    duration: float | None
    streams: tuple[StreamInfo, ...]
    start_time: float


@dataclass(frozen=True)
class GroupOfPictures:
    key_time: float
    display_start: float
    frame_count: int


@dataclass(frozen=True)
class VideoTimeline:
    frame_times: tuple[float, ...]
    gops: tuple[GroupOfPictures, ...]


def probe_media(path: Path) -> MediaInfo:
    raw = run_ffprobe(
        ["-output_format", "json", "-show_format", "-show_streams", str(path)]
    )
    try:
        data: dict[str, Any] = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ProbeError(f"Invalid ffprobe output for {path}") from exc
    streams = _parse_streams(data.get("streams", []))
    if not streams:
        raise ProbeError(f"No media streams detected in {path}")
    fmt = data.get("format", {})
    return MediaInfo(
        path=path,
        duration=_to_float(fmt.get("duration")),
        streams=streams,
        start_time=_to_float(fmt.get("start_time")) or 0.0,
    )


def probe_timeline(path: Path, video_type_index: int, origin: float) -> VideoTimeline:
    raw = run_ffprobe(
        [
            "-select_streams",
            f"v:{video_type_index}",
            "-show_entries",
            "packet=pts_time,flags",
            "-output_format",
            CSV_WITHOUT_SECTION_NAME,
            str(path),
        ]
    )
    packets: list[tuple[float, bool]] = []
    for line in raw.splitlines():
        parts = line.split(",")
        if len(parts) < 2:
            continue
        timestamp = _to_float(parts[0])
        if timestamp is None:
            continue
        packets.append((max(0.0, timestamp - origin), KEYFRAME_FLAG in parts[1]))
    frame_times = tuple(sorted(time for time, _ in packets))
    gops = _build_gops(packets)
    return VideoTimeline(frame_times=frame_times, gops=gops)


def probe_audio_frame(path: Path, audio_type_index: int) -> float | None:
    raw = run_ffprobe(
        [
            "-select_streams",
            f"a:{audio_type_index}",
            "-read_intervals",
            "%+#2",
            "-show_entries",
            "packet=duration_time",
            "-output_format",
            CSV_WITHOUT_SECTION_NAME,
            str(path),
        ]
    )
    for line in raw.splitlines():
        value = _to_float(line.strip().rstrip(","))
        if value:
            return value
    return None


def _build_gops(packets: list[tuple[float, bool]]) -> tuple[GroupOfPictures, ...]:
    key_positions = [i for i, (_, is_key) in enumerate(packets) if is_key]
    gops: list[GroupOfPictures] = []
    for position, first in enumerate(key_positions):
        last = (
            key_positions[position + 1]
            if position + 1 < len(key_positions)
            else len(packets)
        )
        members = packets[first:last]
        gops.append(
            GroupOfPictures(
                key_time=members[0][0],
                display_start=min(time for time, _ in members),
                frame_count=len(members),
            )
        )
    return tuple(gops)


def _parse_streams(raw_streams: list[dict[str, Any]]) -> tuple[StreamInfo, ...]:
    counters: dict[str, int] = {}
    streams: list[StreamInfo] = []
    for raw in raw_streams:
        codec_type = raw.get("codec_type", "unknown")
        type_index = counters.get(codec_type, 0)
        counters[codec_type] = type_index + 1
        disposition = raw.get("disposition", {})
        streams.append(
            StreamInfo(
                index=int(raw["index"]),
                codec_type=codec_type,
                codec_name=raw.get("codec_name", "unknown"),
                type_index=type_index,
                is_attached_pic=bool(disposition.get("attached_pic", 0)),
                pix_fmt=raw.get("pix_fmt"),
                bit_rate=_to_int(raw.get("bit_rate")),
            )
        )
    return tuple(streams)


def _to_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) and number >= 0 else None


def _to_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
