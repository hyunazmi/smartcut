from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from smartcut.timecode import format_duration, format_timecode

MIN_OTHER_SECONDS = 0.05


@dataclass(frozen=True)
class StepTiming:
    label: str
    seconds: float


@dataclass(frozen=True)
class CutSummary:
    output: Path
    total_seconds: float
    steps: tuple[StepTiming, ...]
    requested_duration: float
    output_duration: float | None
    output_size: int
    copied_seconds: float
    reencoded_seconds: float

    @property
    def duration_diff(self) -> float | None:
        if self.output_duration is None:
            return None
        return self.output_duration - self.requested_duration


def format_size(size: int) -> str:
    value = float(size)
    for unit in ("B", "KB", "MB"):
        if value < 1024:
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} GB"


def format_summary(summary: CutSummary) -> list[str]:
    rows: list[tuple[str, str]] = [
        ("Execution time", format_duration(summary.total_seconds))
    ]
    named = sum(step.seconds for step in summary.steps)
    for step in summary.steps:
        rows.append((f"  - {step.label}", format_duration(step.seconds)))
    other = summary.total_seconds - named
    if other >= MIN_OTHER_SECONDS:
        rows.append(("  - Other", format_duration(other)))
    rows.append(("Requested length", format_timecode(summary.requested_duration)))
    if summary.output_duration is None:
        rows.append(("Output length", "unknown"))
    else:
        rows.append(("Output length", format_timecode(summary.output_duration)))
        diff = summary.duration_diff or 0.0
        rows.append(("Difference", f"{diff:+.3f}s"))
    total_media = summary.copied_seconds + summary.reencoded_seconds
    if total_media > 0:
        copied_percent = summary.copied_seconds / total_media * 100
        copied = format_duration(summary.copied_seconds)
        reencoded = format_duration(summary.reencoded_seconds)
        rows.append(
            (
                "Copied / re-encoded",
                f"{copied} / {reencoded} ({copied_percent:.1f}% copied)",
            )
        )
    rows.append(("Output size", format_size(summary.output_size)))
    width = max(len(label) for label, _ in rows)
    return [f"{label:<{width}}  {value}" for label, value in rows]
