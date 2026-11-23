from __future__ import annotations

import logging
import os
import tempfile
import time
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import NamedTuple

from smartcut.codecs import ensure_container, ensure_input_file
from smartcut.config import CutOptions
from smartcut.exceptions import CancelledError, ProbeError, SmartcutError
from smartcut.ffmpeg import ensure_tools_available, run_ffmpeg
from smartcut.ffmpeg_args import (
    AUDIO_PART_SUFFIX,
    AudioPart,
    annexb_args,
    container_args,
    copy_stream_args,
    encode_stream_args,
    length_limit_args,
    merge_args,
    video_part_suffix,
)
from smartcut.planner import (
    Segment,
    SegmentKind,
    is_full_reencode,
    plan_full_reencode,
    plan_smart_segments,
    resolve_range,
    video_window,
)
from smartcut.probe import (
    MediaInfo,
    probe_audio_frame,
    probe_media,
    probe_timeline,
)
from smartcut.progress import StepProgress
from smartcut.streams import (
    OutputStream,
    StreamSelection,
    ensure_crf_supported,
    select_streams,
)
from smartcut.summary import CutSummary, StepTiming
from smartcut.timecode import format_duration, to_ffmpeg_time

logger = logging.getLogger(__name__)
PRE_ROLL_SECONDS = 10.0
MSG_FINDING = "Finding the frames to cut..."
LABEL_ANALYZE = "Analyze video"


class _Step(NamedTuple):
    message: str
    label: str


STEP_ENCODE_START = _Step("Re-encoding the start of the video", "Re-encode start")
STEP_COPY_VIDEO = _Step("Copying the middle of the video", "Copy middle")
STEP_ENCODE_END = _Step("Re-encoding the end of the video", "Re-encode end")
STEP_ENCODE_ALL = _Step("Re-encoding the whole range", "Re-encode whole range")
STEP_COPY_AUDIO = _Step("Copying the audio", "Copy audio")
STEP_MERGE = _Step("Merging the parts", "Merge")


def step_message(message: str, seconds: float) -> str:
    return f"{message} ({format_duration(seconds)})..."


@dataclass(frozen=True)
class _Job:
    input_path: Path
    selection: StreamSelection
    crf: int
    preset: str
    timings: list[StepTiming]


@contextmanager
def _timed(timings: list[StepTiming], label: str) -> Iterator[None]:
    begin = time.perf_counter()
    yield
    timings.append(StepTiming(label, time.perf_counter() - begin))


def cut_video(options: CutOptions, confirm_overwrite: Callable[[], bool]) -> CutSummary:
    ensure_tools_available()
    ensure_input_file(options.input_path)
    output = _prepare_output(options, confirm_overwrite)
    started = time.perf_counter()
    timings: list[StepTiming] = []
    logger.info(MSG_FINDING)
    with _timed(timings, LABEL_ANALYZE):
        media = probe_media(options.input_path)
        selection = select_streams(media)
        ensure_crf_supported(selection, options.crf)
        _log_excluded(selection)
        start, end = resolve_range(options.start, options.end, media.duration)
        segments = _plan_segments(media, selection, start, end)
    job = _Job(options.input_path, selection, options.crf, options.preset, timings)
    _write_atomically(job, segments, output)
    total_seconds = time.perf_counter() - started
    return CutSummary(
        output=output,
        total_seconds=total_seconds,
        steps=tuple(timings),
        requested_duration=end - start,
        output_duration=_probe_duration(output),
        output_size=output.stat().st_size,
        copied_seconds=sum(
            seg.duration for seg in segments if seg.kind is SegmentKind.COPY
        ),
        reencoded_seconds=sum(
            seg.duration for seg in segments if seg.kind is SegmentKind.ENCODE
        ),
    )


def _probe_duration(path: Path) -> float | None:
    try:
        return probe_media(path).duration
    except ProbeError:
        return None


def _prepare_output(options: CutOptions, confirm_overwrite: Callable[[], bool]) -> Path:
    output = options.resolved_output()
    if output.is_dir():
        raise SmartcutError(f"Output path is a directory: {output}")
    ensure_container(output)
    if output.resolve() == options.input_path.resolve():
        raise SmartcutError("Output file must not be the same as the input file")
    if output.exists():
        logger.warning("Output file already exists: %s", output)
        if not confirm_overwrite():
            raise CancelledError("the existing output file was not overwritten")
    output.parent.mkdir(parents=True, exist_ok=True)
    if not os.access(output.parent, os.W_OK):
        raise SmartcutError(f"No write permission for directory: {output.parent}")
    return output


def _log_excluded(selection: StreamSelection) -> None:
    for stream in selection.excluded:
        logger.warning(
            "Stream #%d (%s/%s) is not included in the output",
            stream.index,
            stream.codec_type,
            stream.codec_name,
        )


def _plan_segments(
    media: MediaInfo, selection: StreamSelection, start: float, end: float
) -> list[Segment]:
    if selection.video is None:
        return plan_full_reencode(start, end)
    if not selection.can_smartcut:
        logger.warning(
            "Some streams have no encoder for their original codec, "
            "so the whole range will be re-encoded"
        )
        return plan_full_reencode(start, end)
    timeline = probe_timeline(
        media.path, selection.video.stream.type_index, media.start_time
    )
    segments = plan_smart_segments(start, end, timeline.frame_times, timeline.gops)
    if is_full_reencode(segments):
        logger.warning(
            "No keyframe inside the range, so the whole range will be re-encoded"
        )
    return segments


def _write_atomically(job: _Job, segments: list[Segment], output: Path) -> None:
    partial = output.with_name(f"{output.stem}.partial{output.suffix}")
    video = job.selection.video
    try:
        if video is None or is_full_reencode(segments):
            streams = job.selection.streams
            _encode_segment(job, segments[0], partial, STEP_ENCODE_ALL, streams)
        else:
            _assemble(job, video, segments, partial)
        partial.replace(output)
    finally:
        partial.unlink(missing_ok=True)


def _assemble(
    job: _Job, video: OutputStream, segments: list[Segment], output: Path
) -> None:
    suffix = video_part_suffix(video)
    origin, length = video_window(segments)
    with tempfile.TemporaryDirectory(prefix="smartcut_") as temp_dir:
        folder = Path(temp_dir)
        parts: list[Path] = []
        copy_done = False
        for index, segment in enumerate(segments):
            part = folder / f"part_{index:03d}{suffix}"
            if segment.kind is SegmentKind.COPY:
                _copy_video(job, video, segment, part)
                copy_done = True
            else:
                step = STEP_ENCODE_END if copy_done else STEP_ENCODE_START
                _encode_segment(job, segment, part, step, (video,))
            parts.append(part)
        audio = None
        if job.selection.audio:
            audio = _copy_audio(job, origin, length, folder)
        list_file = folder / "segments.ffconcat"
        list_file.write_text(_concat_list(parts, segments), encoding="utf-8")
        with _timed(job.timings, STEP_MERGE.label):
            run_ffmpeg(
                [
                    *merge_args(list_file, audio),
                    *container_args(output),
                    str(output),
                ],
                StepProgress(step_message(STEP_MERGE.message, length), length),
            )


def _copy_video(job: _Job, video: OutputStream, segment: Segment, part: Path) -> None:
    with _timed(job.timings, STEP_COPY_VIDEO.label):
        run_ffmpeg(
            [
                "-ss",
                to_ffmpeg_time(segment.seek_time),
                "-i",
                str(job.input_path),
                *length_limit_args(segment),
                *copy_stream_args((video,)),
                *annexb_args(video, job.input_path, part),
                "-avoid_negative_ts",
                "make_zero",
                *container_args(part),
                str(part),
            ],
            StepProgress(
                step_message(STEP_COPY_VIDEO.message, segment.duration),
                segment.duration,
            ),
        )


def _copy_audio(job: _Job, origin: float, length: float, folder: Path) -> AudioPart:
    part = folder / f"audio{AUDIO_PART_SUFFIX}"
    frame = probe_audio_frame(job.input_path, job.selection.audio[0].stream.type_index)
    audio_length = length if frame is None else max(length - frame / 2.0, frame)
    with _timed(job.timings, STEP_COPY_AUDIO.label):
        run_ffmpeg(
            [
                *_seek_args(job.input_path, origin),
                "-t",
                to_ffmpeg_time(audio_length),
                *copy_stream_args(job.selection.audio),
                str(part),
            ],
            StepProgress(step_message(STEP_COPY_AUDIO.message, length), length),
        )
    return AudioPart(part, probe_media(part).start_time)


def _encode_segment(
    job: _Job,
    segment: Segment,
    output: Path,
    step: _Step,
    streams: Sequence[OutputStream],
) -> None:
    with _timed(job.timings, step.label):
        run_ffmpeg(
            [
                *_seek_args(job.input_path, segment.start),
                *length_limit_args(segment),
                *encode_stream_args(streams, job.crf, job.preset),
                "-avoid_negative_ts",
                "make_zero",
                *container_args(output),
                str(output),
            ],
            StepProgress(
                step_message(step.message, segment.duration), segment.duration
            ),
        )


def _seek_args(input_path: Path, start: float) -> list[str]:
    seek = max(0.0, start - PRE_ROLL_SECONDS)
    return [
        "-ss",
        to_ffmpeg_time(seek),
        "-i",
        str(input_path),
        "-ss",
        to_ffmpeg_time(start - seek),
    ]


def _concat_list(parts: Sequence[Path], segments: Sequence[Segment]) -> str:
    last = segments[-1]
    ends = [segment.first_frame for segment in segments[1:]]
    ends.append(last.first_frame + last.span)
    lines = ["ffconcat version 1.0"]
    for part, segment, end in zip(parts, segments, ends, strict=True):
        escaped = str(part.resolve()).replace("'", "'\\''")
        lines.append(f"file '{escaped}'")
        lines.append(f"duration {end - segment.first_frame:.6f}")
    return "\n".join(lines) + "\n"
