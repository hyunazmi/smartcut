from __future__ import annotations

import logging
import shutil
import sys

logger = logging.getLogger(__name__)
BAR_WIDTH = 30
MIN_BAR_WIDTH = 10
BAR_DECORATION_WIDTH = 3


class StepProgress:
    def __init__(self, message: str, total_seconds: float) -> None:
        self._total = total_seconds
        self._live = sys.stderr.isatty()
        logger.info(message)
        if self._live:
            self._draw(0.0)

    def update(self, done_seconds: float) -> None:
        if self._live:
            self._draw(done_seconds / self._total)

    def close(self, completed: bool) -> None:
        if not self._live:
            return
        if completed:
            self._draw(1.0)
        sys.stderr.write("\n")
        sys.stderr.flush()

    def _draw(self, ratio: float) -> None:
        ratio = min(max(ratio, 0.0), 1.0)
        percent = f"{ratio * 100:5.1f}%"
        columns = shutil.get_terminal_size().columns
        room = columns - 1 - len(percent) - BAR_DECORATION_WIDTH
        width = min(BAR_WIDTH, room)
        if width >= MIN_BAR_WIDTH:
            filled = int(ratio * width)
            line = f"[{'#' * filled}{'-' * (width - filled)}] {percent}"
        else:
            line = percent
        sys.stderr.write("\r" + line)
        sys.stderr.flush()
