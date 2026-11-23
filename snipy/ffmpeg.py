from __future__ import annotations

import shutil
import subprocess
import tempfile
from collections.abc import Sequence
from functools import lru_cache

from snipy.exceptions import FFmpegError, ProbeError, ToolNotFoundError
from snipy.progress import StepProgress

FFMPEG = "ffmpeg"
FFPROBE = "ffprobe"
ENCODING = "utf-8"

FFMPEG_BASE_ARGS = (
    "-hide_banner",
    "-loglevel",
    "warning",
    "-nostdin",
    "-progress",
    "pipe:1",
    "-y",
)
FFPROBE_BASE_ARGS = ("-hide_banner", "-loglevel", "error")

PROGRESS_TIME_KEY = "out_time_us"
MICROSECONDS_PER_SECOND = 1_000_000

ENCODER_FLAGS_WIDTH = 6
ENCODER_TYPE_FLAGS = "VAS"
ENCODER_LEGEND_MARKER = "="

STDERR_TAIL_LINES = 10
NO_ERROR_DETAILS = "no error details available"


def ensure_tools_available() -> None:
    for tool in (FFMPEG, FFPROBE):
        if shutil.which(tool) is None:
            raise ToolNotFoundError(
                f"'{tool}' was not found in PATH, please install FFmpeg first"
            )


def run_ffprobe(args: Sequence[str]) -> str:
    result = subprocess.run(
        [FFPROBE, *FFPROBE_BASE_ARGS, *args],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        encoding=ENCODING,
        errors="replace",
        check=False,
    )
    if result.returncode != 0:
        raise ProbeError(f"ffprobe failed:\n{_error_tail(result.stderr)}")
    return result.stdout


def run_ffmpeg(args: Sequence[str], step: StepProgress) -> None:
    command = [FFMPEG, *FFMPEG_BASE_ARGS, *args]
    completed = False
    stderr = ""
    try:
        with tempfile.TemporaryFile("w+", encoding=ENCODING, errors="replace") as log:
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=log,
                text=True,
                encoding=ENCODING,
                errors="replace",
            )
            completed = _wait_for(process, step)
            log.seek(0)
            stderr = log.read()
    finally:
        step.close(completed)

    if not completed:
        raise FFmpegError(
            f"ffmpeg failed (exit code {process.returncode}):\n{_error_tail(stderr)}"
        )


@lru_cache(maxsize=1)
def available_encoders() -> frozenset[str]:
    result = subprocess.run(
        [FFMPEG, "-hide_banner", "-encoders"],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        encoding=ENCODING,
        errors="replace",
        check=False,
    )
    names: set[str] = set()
    for line in result.stdout.splitlines():
        parts = line.split()
        if len(parts) < 2 or len(parts[0]) != ENCODER_FLAGS_WIDTH:
            continue
        flags, name = parts[0], parts[1]
        if flags[0] in ENCODER_TYPE_FLAGS and name != ENCODER_LEGEND_MARKER:
            names.add(name)
    return frozenset(names)


def _wait_for(process: subprocess.Popen[str], step: StepProgress) -> bool:
    try:
        for line in process.stdout or ():
            seconds = _progress_seconds(line)
            if seconds is not None:
                step.update(seconds)
        return process.wait() == 0
    except BaseException:
        process.kill()
        process.wait()
        raise


def _progress_seconds(line: str) -> float | None:
    key, _, value = line.strip().partition("=")
    if key == PROGRESS_TIME_KEY and value.lstrip("-").isdigit():
        return max(int(value), 0) / MICROSECONDS_PER_SECOND
    return None


def _error_tail(stderr: str) -> str:
    lines = [line for line in stderr.strip().splitlines() if line.strip()]
    return "\n".join(lines[-STDERR_TAIL_LINES:]) or NO_ERROR_DETAILS
