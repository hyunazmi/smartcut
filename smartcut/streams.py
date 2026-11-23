from __future__ import annotations

from dataclasses import dataclass

from smartcut.codecs import (
    AUDIO_ENCODER_CANDIDATES,
    SUPPORTED_AUDIO_CODECS,
    SUPPORTED_VIDEO_CODECS,
    VIDEO_ENCODER_CANDIDATES,
    profile_for,
)
from smartcut.exceptions import SmartcutError
from smartcut.ffmpeg import available_encoders
from smartcut.probe import MediaInfo, StreamInfo

FALLBACK_VIDEO_ENCODER = "libx264"
FALLBACK_VIDEO_CODEC = "h264"
FALLBACK_AUDIO_ENCODER = "aac"
FALLBACK_AUDIO_CODEC = "aac"


@dataclass(frozen=True)
class OutputStream:
    stream: StreamInfo
    encoder: str
    output_codec: str
    native: bool

    @property
    def is_video(self) -> bool:
        return self.stream.codec_type == "video"


@dataclass(frozen=True)
class StreamSelection:
    streams: tuple[OutputStream, ...]
    excluded: tuple[StreamInfo, ...]

    @property
    def video(self) -> OutputStream | None:
        return next((stream for stream in self.streams if stream.is_video), None)

    @property
    def audio(self) -> tuple[OutputStream, ...]:
        return tuple(stream for stream in self.streams if not stream.is_video)

    @property
    def can_smartcut(self) -> bool:
        return self.video is not None and all(s.native for s in self.streams)


def select_streams(media: MediaInfo) -> StreamSelection:
    kept: list[OutputStream] = []
    excluded: list[StreamInfo] = []
    video_taken = False

    for stream in media.streams:
        is_main_video = (
            stream.codec_type == "video"
            and not stream.is_attached_pic
            and not video_taken
        )
        if is_main_video:
            _ensure_supported(stream)
            video_taken = True
            kept.append(_choose_encoder(stream))
        elif stream.codec_type == "audio":
            _ensure_supported(stream)
            kept.append(_choose_encoder(stream))
        else:
            excluded.append(stream)

    if not kept:
        raise SmartcutError("No video or audio stream can be processed")
    return StreamSelection(tuple(kept), tuple(excluded))


def ensure_crf_supported(selection: StreamSelection, crf: int) -> None:
    video = selection.video
    if video is None:
        return
    profile = profile_for(video.encoder)
    if not profile.supports_crf:
        return
    low, high = profile.crf_range
    if not low <= crf <= high:
        raise SmartcutError(
            f"CRF {crf} is outside the range {low}-{high} "
            f"supported by encoder '{video.encoder}'"
        )


def _ensure_supported(stream: StreamInfo) -> None:
    is_video = stream.codec_type == "video"
    allowed = SUPPORTED_VIDEO_CODECS if is_video else SUPPORTED_AUDIO_CODECS
    if stream.codec_name not in allowed:
        raise SmartcutError(
            f"{stream.codec_type.capitalize()} codec '{stream.codec_name}' "
            f"is not supported (supported: {', '.join(sorted(allowed))})"
        )


def _choose_encoder(stream: StreamInfo) -> OutputStream:
    is_video = stream.codec_type == "video"
    candidates_map = VIDEO_ENCODER_CANDIDATES if is_video else AUDIO_ENCODER_CANDIDATES
    candidates = candidates_map.get(stream.codec_name, (stream.codec_name,))
    installed = available_encoders()

    for name in candidates:
        if name in installed:
            return OutputStream(stream, name, stream.codec_name, native=True)

    if is_video:
        encoder, codec = FALLBACK_VIDEO_ENCODER, FALLBACK_VIDEO_CODEC
    else:
        encoder, codec = FALLBACK_AUDIO_ENCODER, FALLBACK_AUDIO_CODEC
    if encoder not in installed:
        raise SmartcutError(
            f"Encoder '{encoder}' is not available, "
            f"so codec '{stream.codec_name}' cannot be processed"
        )
    return OutputStream(stream, encoder, codec, native=False)
