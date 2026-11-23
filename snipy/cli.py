from __future__ import annotations

import argparse
import logging
import signal
import sys
from pathlib import Path
from typing import NoReturn

from snipy import __version__
from snipy.codecs import profile_for
from snipy.config import (
    DEFAULT_CRF,
    DEFAULT_PRESET,
    MAX_CRF,
    PRESETS,
    CutOptions,
    parse_crf,
    validate_preset,
)
from snipy.cutter import cut_video
from snipy.exceptions import CancelledError, SnipyError
from snipy.interactive import confirm_overwrite, prompt_cut_options
from snipy.logging_setup import SUCCESS, configure_logging
from snipy.summary import format_summary
from snipy.timecode import parse_timecode

DESCRIPTION = "Cut videos with the smart cut method"
H26X_MAX_CRF = profile_for("libx264").crf_range[1]
EXIT_FAILURE = 1
EXIT_USAGE = 2
EXIT_INTERRUPTED = 130
logger = logging.getLogger(__name__)


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        self.print_usage(sys.stderr)
        logger.error("%s", message)
        self.exit(EXIT_USAGE)


def build_parser() -> argparse.ArgumentParser:
    parser = _Parser(prog="snipy", description=DESCRIPTION, add_help=False)
    files = parser.add_argument_group("input and output")
    cut_range = parser.add_argument_group("cut range")
    encoding = parser.add_argument_group("re-encoding")
    general = parser.add_argument_group("general")
    general.add_argument(
        "-h", "--help", action="help", help="Show this help message and exit"
    )
    general.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
        help="Show the version and exit",
    )
    files.add_argument(
        "-f",
        "--file",
        type=Path,
        metavar="FILE",
        help="Input video file (interactive mode starts if omitted)",
    )
    files.add_argument(
        "-o",
        "--output",
        type=Path,
        metavar="FILE",
        help="Output file (default: <input>_snipy.<ext>)",
    )
    cut_range.add_argument(
        "-s",
        "--start",
        type=_timecode_arg,
        metavar="HH:MM:SS",
        help="Start time (default: start of the video)",
    )
    cut_range.add_argument(
        "-e",
        "--end",
        type=_timecode_arg,
        metavar="HH:MM:SS",
        help="End time (default: end of the video)",
    )
    encoding.add_argument(
        "-c",
        "--crf",
        type=_crf_arg,
        default=DEFAULT_CRF,
        metavar="CRF",
        help=(
            "CRF quality of the re-encoded parts, lower is better: "
            f"0-{H26X_MAX_CRF} for H.264/H.265, 0-{MAX_CRF} for other encoders "
            f"(default: {DEFAULT_CRF})"
        ),
    )
    encoding.add_argument(
        "-p",
        "--preset",
        type=_preset_arg,
        default=DEFAULT_PRESET,
        metavar="PRESET",
        help=(
            f"Encoder preset for H.264/H.265, from {PRESETS[0]} to {PRESETS[-1]}, "
            f"slower gives smaller files (default: {DEFAULT_PRESET})"
        ),
    )
    general.add_argument(
        "-i",
        "--interactive",
        action="store_true",
        help="Interactive mode: ask for each option step by step",
    )
    general.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose output (show a detailed summary)",
    )
    return parser


def main() -> int:
    configure_logging()
    _treat_termination_as_interrupt()
    args = build_parser().parse_args()
    try:
        summary = cut_video(_collect_options(args), confirm_overwrite)
    except KeyboardInterrupt:
        logger.info("Cancelled by user")
        return EXIT_INTERRUPTED
    except CancelledError as exc:
        logger.info("Cancelled: %s", exc)
        return EXIT_FAILURE
    except EOFError:
        logger.error("No input available, cannot read an answer")
        return EXIT_FAILURE
    except SnipyError as exc:
        logger.error("%s", exc)
        return EXIT_FAILURE
    except OSError as exc:
        logger.error("File system error: %s", exc)
        return EXIT_FAILURE
    logger.log(SUCCESS, "Done: %s", summary.output)
    if args.verbose:
        logger.info("Summary")
        for line in format_summary(summary):
            logger.info("  %s", line)
    return 0


def _collect_options(args: argparse.Namespace) -> CutOptions:
    if args.interactive or args.file is None:
        return prompt_cut_options(
            input_path=args.file,
            output_path=args.output,
            start=args.start,
            end=args.end,
            crf=args.crf,
            preset=args.preset,
        )
    return CutOptions(
        input_path=args.file,
        output_path=args.output,
        start=args.start,
        end=args.end,
        crf=args.crf,
        preset=args.preset,
    )


def _treat_termination_as_interrupt() -> None:
    def raise_interrupt(*_: object) -> NoReturn:
        raise KeyboardInterrupt

    for name in ("SIGTERM", "SIGHUP"):
        number = getattr(signal, name, None)
        if number is not None:
            signal.signal(number, raise_interrupt)


def _timecode_arg(value: str) -> float:
    try:
        return parse_timecode(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def _crf_arg(value: str) -> int:
    try:
        return parse_crf(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def _preset_arg(value: str) -> str:
    try:
        return validate_preset(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc
