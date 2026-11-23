from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

DEFAULT_CRF = 23
DEFAULT_PRESET = "ultrafast"
MAX_CRF = 63
OUTPUT_SUFFIX_TAG = "_snipy"
PRESETS = (
    "ultrafast",
    "superfast",
    "veryfast",
    "faster",
    "fast",
    "medium",
    "slow",
    "slower",
    "veryslow",
    "placebo",
)


def validate_crf(value: int) -> int:
    if not 0 <= value <= MAX_CRF:
        raise ValueError(f"CRF must be between 0 and {MAX_CRF}, got {value}")
    return value


def parse_crf(text: str) -> int:
    try:
        number = int(text)
    except ValueError:
        raise ValueError(
            f"CRF must be an integer between 0 and {MAX_CRF}, got '{text}'"
        ) from None
    return validate_crf(number)


def validate_preset(value: str) -> str:
    if value not in PRESETS:
        raise ValueError(
            f"Unknown preset '{value}', choose one of: {', '.join(PRESETS)}"
        )
    return value


@dataclass(frozen=True)
class CutOptions:
    input_path: Path
    output_path: Path | None = None
    start: float | None = None
    end: float | None = None
    crf: int = DEFAULT_CRF
    preset: str = DEFAULT_PRESET

    def __post_init__(self) -> None:
        validate_crf(self.crf)
        validate_preset(self.preset)

    def resolved_output(self) -> Path:
        if self.output_path is not None:
            return self.output_path
        suffix = self.input_path.suffix or ".mp4"
        return self.input_path.with_name(
            f"{self.input_path.stem}{OUTPUT_SUFFIX_TAG}{suffix}"
        )
