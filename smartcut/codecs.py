from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from smartcut.config import MAX_CRF
from smartcut.exceptions import SmartcutError

SUPPORTED_CONTAINERS = frozenset({".mp4", ".m4v", ".mov", ".mkv", ".webm", ".ts"})
SUPPORTED_VIDEO_CODECS = frozenset({"h264", "hevc", "av1", "vp9", "mpeg2video"})
SUPPORTED_AUDIO_CODECS = frozenset(
    {"aac", "mp3", "opus", "vorbis", "ac3", "eac3", "flac"}
)

VIDEO_ENCODER_CANDIDATES: dict[str, tuple[str, ...]] = {
    "h264": ("libx264",),
    "hevc": ("libx265",),
    "vp9": ("libvpx-vp9",),
    "av1": ("libsvtav1", "libaom-av1"),
}

AUDIO_ENCODER_CANDIDATES: dict[str, tuple[str, ...]] = {
    "mp3": ("libmp3lame",),
    "opus": ("libopus",),
    "vorbis": ("libvorbis",),
}

LOSSY_AUDIO_ENCODERS = frozenset(
    {"aac", "libmp3lame", "libopus", "libvorbis", "ac3", "eac3"}
)


@dataclass(frozen=True)
class EncoderProfile:
    supports_crf: bool = False
    supports_preset: bool = False
    needs_zero_bitrate: bool = False
    closed_gop: tuple[str, str] | None = None
    crf_range: tuple[int, int] = (0, MAX_CRF)


ENCODER_PROFILES: dict[str, EncoderProfile] = {
    "libx264": EncoderProfile(
        supports_crf=True,
        supports_preset=True,
        closed_gop=("-x264-params", "open-gop=0"),
        crf_range=(0, 51),
    ),
    "libx265": EncoderProfile(
        supports_crf=True,
        supports_preset=True,
        closed_gop=("-x265-params", "open-gop=0:repeat-headers=1"),
        crf_range=(0, 51),
    ),
    "libvpx-vp9": EncoderProfile(
        supports_crf=True,
        needs_zero_bitrate=True,
        crf_range=(0, 63),
    ),
    "libaom-av1": EncoderProfile(
        supports_crf=True,
        needs_zero_bitrate=True,
        crf_range=(0, 63),
    ),
    "libsvtav1": EncoderProfile(supports_crf=True, crf_range=(0, 63)),
}

TS_VIDEO_CODECS = frozenset({"h264", "hevc", "mpeg2video"})
TS_INPUT_SUFFIXES = frozenset({".ts", ".m2ts", ".mts"})
ANNEXB_BITSTREAM_FILTERS = {"h264": "h264_mp4toannexb", "hevc": "hevc_mp4toannexb"}
FASTSTART_SUFFIXES = frozenset({".mp4", ".m4v", ".mov"})


def profile_for(encoder: str) -> EncoderProfile:
    return ENCODER_PROFILES.get(encoder, EncoderProfile())


def ensure_container(path: Path) -> None:
    if path.suffix.lower() not in SUPPORTED_CONTAINERS:
        supported = ", ".join(sorted(SUPPORTED_CONTAINERS))
        found = f"Format '{path.suffix}'" if path.suffix else "A file without extension"
        raise SmartcutError(f"{found} is not supported (supported: {supported})")


def ensure_input_file(path: Path) -> None:
    if not path.is_file():
        raise SmartcutError(f"Input file not found: {path}")
    ensure_container(path)
