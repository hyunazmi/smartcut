from __future__ import annotations

import re

_TIMECODE_PATTERN = re.compile(r"(\d{2,}):([0-5]\d):([0-5]\d)(?:\.(\d+))?")


def parse_timecode(value: str) -> float:
    match = _TIMECODE_PATTERN.fullmatch(value.strip())
    if match is None:
        raise ValueError(f"Invalid time format '{value}', use HH:MM:SS or HH:MM:SS.ms")
    hours, minutes, seconds, fraction = match.groups()
    total = float(int(hours) * 3600 + int(minutes) * 60 + int(seconds))
    if fraction:
        total += float(f"0.{fraction}")
    return total


def to_ffmpeg_time(seconds: float) -> str:
    return f"{seconds:.6f}"


def format_timecode(seconds: float) -> str:
    millis = round(seconds * 1000)
    hours, rest = divmod(millis, 3600000)
    minutes, rest = divmod(rest, 60000)
    secs, ms = divmod(rest, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{ms:03d}"


def format_duration(seconds: float) -> str:
    if round(seconds, 1) < 60:
        return f"{max(seconds, 0.0):.1f}s"
    total = round(seconds)
    hours, rest = divmod(total, 3600)
    minutes, secs = divmod(rest, 60)
    if hours:
        return f"{hours}h {minutes:02d}m {secs:02d}s"
    return f"{minutes}m {secs:02d}s"
