from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import NamedTuple

from snipy.codecs import (
    ANNEXB_BITSTREAM_FILTERS,
    FASTSTART_SUFFIXES,
    LOSSY_AUDIO_ENCODERS,
    TS_INPUT_SUFFIXES,
    TS_VIDEO_CODECS,
    profile_for,
)
from snipy.planner import Segment
from snipy.streams import OutputStream
from snipy.timecode import to_ffmpeg_time

TS_SUFFIX = ".ts"
MKV_SUFFIX = ".mkv"
AUDIO_PART_SUFFIX = ".mka"
DUMP_EXTRA_FILTER = "dump_extra=freq=keyframe"
FRAME_LIMIT_PADDING = 0.5


class AudioPart(NamedTuple):
    path: Path
    offset: float


def video_part_suffix(video: OutputStream) -> str:
    return TS_SUFFIX if video.output_codec in TS_VIDEO_CODECS else MKV_SUFFIX


def copy_stream_args(streams: Sequence[OutputStream]) -> list[str]:
    args: list[str] = []
    for index, item in enumerate(streams):
        args += ["-map", f"0:{item.stream.index}", f"-c:{index}", "copy"]
    return args


def encode_stream_args(
    streams: Sequence[OutputStream], crf: int, preset: str
) -> list[str]:
    args: list[str] = []
    for index, item in enumerate(streams):
        args += ["-map", f"0:{item.stream.index}", f"-c:{index}", item.encoder]
        if item.is_video:
            args += _video_quality_args(item, index, crf, preset)
        else:
            args += _audio_quality_args(item, index)
    return args


def annexb_args(video: OutputStream | None, input_path: Path, part: Path) -> list[str]:
    if part.suffix != TS_SUFFIX or input_path.suffix.lower() in TS_INPUT_SUFFIXES:
        return []
    if video is None or video.output_codec not in ANNEXB_BITSTREAM_FILTERS:
        return []
    annexb_filter = ANNEXB_BITSTREAM_FILTERS[video.output_codec]
    return ["-bsf:v", f"{annexb_filter},{DUMP_EXTRA_FILTER}"]


def container_args(path: Path) -> list[str]:
    suffix = path.suffix.lower()
    if suffix == TS_SUFFIX:
        return ["-muxdelay", "0", "-muxpreload", "0"]
    if suffix in FASTSTART_SUFFIXES:
        return ["-movflags", "+faststart"]
    return []


def length_limit_args(segment: Segment) -> list[str]:
    if segment.frames is None:
        return ["-t", to_ffmpeg_time(segment.duration)]
    return [
        "-frames:v",
        str(segment.frames),
        "-t",
        to_ffmpeg_time(segment.duration + FRAME_LIMIT_PADDING),
    ]


def merge_args(list_file: Path, audio: AudioPart | None) -> list[str]:
    args = ["-f", "concat", "-safe", "0", "-i", str(list_file)]
    if audio is not None:
        args += ["-itsoffset", to_ffmpeg_time(audio.offset), "-i", str(audio.path)]
    args += ["-map", "0:v:0"]
    if audio is not None:
        args += ["-map", "1:a"]
    return [*args, "-c", "copy"]


def _video_quality_args(
    item: OutputStream, index: int, crf: int, preset: str
) -> list[str]:
    profile = profile_for(item.encoder)
    args: list[str] = []
    if profile.closed_gop:
        option, value = profile.closed_gop
        args += [f"{option}:{index}", value]
    if profile.supports_crf:
        args += [f"-crf:{index}", str(crf)]
    if profile.supports_preset:
        args += [f"-preset:{index}", preset]
    if profile.needs_zero_bitrate:
        args += [f"-b:{index}", "0"]
    if item.native and item.stream.pix_fmt:
        args += [f"-pix_fmt:{index}", item.stream.pix_fmt]
    return args


def _audio_quality_args(item: OutputStream, index: int) -> list[str]:
    if item.encoder in LOSSY_AUDIO_ENCODERS and item.stream.bit_rate:
        return [f"-b:{index}", str(item.stream.bit_rate)]
    return []
