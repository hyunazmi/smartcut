from __future__ import annotations

import logging
from bisect import bisect_left
from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum, auto

from smartcut.exceptions import SmartcutError
from smartcut.probe import GroupOfPictures
from smartcut.timecode import format_timecode

logger = logging.getLogger(__name__)
EPSILON = 0.001
DTS_SEEK_BIAS = 3.0 / 23.0
SEEK_TOLERANCE = 0.01
MAX_SEEK_INTO_GOP = 1.0


def copy_seek_time(keyframe: float, next_keyframe: float) -> float:
    low = keyframe + DTS_SEEK_BIAS + SEEK_TOLERANCE
    high = min(next_keyframe - SEEK_TOLERANCE, low + MAX_SEEK_INTO_GOP)
    if low <= high:
        return (low + high) / 2.0
    return keyframe + EPSILON


class SegmentKind(Enum):
    COPY = auto()
    ENCODE = auto()


@dataclass(frozen=True)
class Segment:
    kind: SegmentKind
    start: float
    duration: float
    first_frame: float
    span: float
    frames: int | None = None
    seek: float | None = None

    @property
    def seek_time(self) -> float:
        return self.start if self.seek is None else self.seek


def resolve_range(
    start: float | None, end: float | None, duration: float | None
) -> tuple[float, float]:
    begin = 0.0 if start is None else start
    if end is None:
        if duration is None:
            raise SmartcutError(
                "Video duration is unknown, use -e to set the cut end time"
            )
        finish = duration
    else:
        finish = end
    if duration is not None:
        if begin >= duration:
            raise SmartcutError(
                f"Start time {format_timecode(begin)} is beyond "
                f"the video duration {format_timecode(duration)}"
            )
        if finish > duration + EPSILON:
            logger.warning(
                "End time is beyond the video duration, cutting until the end"
            )
            finish = duration
    if finish - begin <= EPSILON:
        raise SmartcutError("End time must be greater than start time")
    return (begin, finish)


def plan_full_reencode(start: float, end: float) -> list[Segment]:
    length = end - start
    return [
        Segment(SegmentKind.ENCODE, start, length, first_frame=start, span=length)
    ]


def is_full_reencode(segments: Sequence[Segment]) -> bool:
    return len(segments) == 1 and segments[0].kind is SegmentKind.ENCODE


def plan_smart_segments(
    start: float,
    end: float,
    frame_times: Sequence[float],
    gops: Sequence[GroupOfPictures],
) -> list[Segment]:
    copy_range = _find_copy_range(start, end, gops)
    if copy_range is None:
        return plan_full_reencode(start, end)
    first, last = copy_range
    copy_start = gops[first].display_start
    copy_end = gops[last].display_start
    copy = Segment(
        SegmentKind.COPY,
        copy_start,
        copy_end - copy_start,
        first_frame=copy_start,
        span=copy_end - copy_start,
        frames=sum(gop.frame_count for gop in gops[first:last]),
        seek=copy_seek_time(gops[first].key_time, copy_end),
    )
    head = _encode_edge(frame_times, start, copy_start)
    tail = _encode_edge(frame_times, copy_end, end)
    return [segment for segment in (head, copy, tail) if segment is not None]


def _find_copy_range(
    start: float, end: float, gops: Sequence[GroupOfPictures]
) -> tuple[int, int] | None:
    first = next(
        (
            i
            for i, gop in enumerate(gops)
            if gop.display_start >= start - EPSILON
            and abs(gop.display_start - gop.key_time) <= EPSILON
        ),
        None,
    )
    last = max(
        (i for i, gop in enumerate(gops) if gop.display_start <= end + EPSILON),
        default=None,
    )
    if first is None or last is None or last <= first:
        return None
    return (first, last)


def _encode_edge(
    frame_times: Sequence[float], begin: float, finish: float
) -> Segment | None:
    if finish - begin <= EPSILON:
        return None
    first = bisect_left(frame_times, begin - EPSILON)
    after = bisect_left(frame_times, finish - EPSILON)
    if after == first:
        return None
    first_frame = frame_times[first]
    return Segment(
        SegmentKind.ENCODE,
        begin,
        finish - begin,
        first_frame=first_frame,
        span=_frame_end(frame_times, after) - first_frame,
        frames=after - first,
    )


def _frame_end(frame_times: Sequence[float], after: int) -> float:
    if after < len(frame_times):
        return frame_times[after]
    if len(frame_times) >= 2:
        return 2.0 * frame_times[-1] - frame_times[-2]
    return frame_times[-1]


def video_window(segments: Sequence[Segment]) -> tuple[float, float]:
    origin = segments[0].first_frame
    last = segments[-1]
    return (origin, last.first_frame + last.span - origin)
