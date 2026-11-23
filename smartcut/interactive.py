from __future__ import annotations

import logging
import sys
from collections.abc import Callable
from pathlib import Path
from typing import TypeVar

from smartcut.codecs import ensure_container, ensure_input_file
from smartcut.config import MAX_CRF, CutOptions, parse_crf, validate_preset
from smartcut.exceptions import SmartcutError
from smartcut.timecode import format_timecode, parse_timecode

logger = logging.getLogger(__name__)
T = TypeVar("T")
D = TypeVar("D")


def confirm_overwrite() -> bool:
    return _read("Overwrite it? [y/N]: ").strip().lower() in ("y", "yes")


def prompt_cut_options(
    *,
    input_path: Path | None,
    output_path: Path | None,
    start: float | None,
    end: float | None,
    crf: int,
    preset: str,
) -> CutOptions:
    logger.info("Interactive mode: press Enter to accept the value in [brackets]")
    chosen_input = _ask_required("Input video file", _parse_input, input_path)
    default_output = output_path or CutOptions(chosen_input).resolved_output()
    return CutOptions(
        input_path=chosen_input,
        output_path=_ask(
            "Output file", _parse_output, default_output, str(default_output)
        ),
        start=_ask_time("Start time (HH:MM:SS)", start, "start of the video"),
        end=_ask_time("End time (HH:MM:SS)", end, "end of the video"),
        crf=_ask(f"CRF (0-{MAX_CRF})", parse_crf, crf, str(crf)),
        preset=_ask("Encoder preset", _parse_preset, preset, preset),
    )


def _read(prompt: str) -> str:
    try:
        answer = input(prompt)
    except (KeyboardInterrupt, EOFError):
        print()
        raise
    if not sys.stdin.isatty():
        print()
    return answer


def _ask(
    prompt: str, parse: Callable[[str], T], default: D, label: str | None
) -> T | D:
    hint = f" [{label}]" if label else ""
    while True:
        answer = _read(f"{prompt}{hint}: ").strip()
        if not answer:
            return default
        try:
            return parse(answer)
        except (ValueError, SmartcutError) as exc:
            logger.error("%s", exc)


def _ask_required(prompt: str, parse: Callable[[str], T], default: T | None) -> T:
    label = None if default is None else str(default)
    while True:
        value = _ask(prompt, parse, default, label)
        if value is not None:
            return value
        logger.error("A value is required")


def _ask_time(prompt: str, default: float | None, empty_label: str) -> float | None:
    label = empty_label if default is None else format_timecode(default)
    return _ask(prompt, parse_timecode, default, label)


def _clean_path(text: str) -> Path:
    return Path(text.strip("\"'")).expanduser()


def _parse_input(text: str) -> Path:
    path = _clean_path(text)
    ensure_input_file(path)
    return path


def _parse_output(text: str) -> Path:
    path = _clean_path(text)
    ensure_container(path)
    return path


def _parse_preset(text: str) -> str:
    return validate_preset(text.lower())
