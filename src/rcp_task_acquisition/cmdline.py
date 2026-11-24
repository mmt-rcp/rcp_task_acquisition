import argparse
import logging
import typing
from pathlib import Path


def parse_log_level(value: str) -> int:
    if value.isdigit():
        return int(value)
    else:
        lvl = logging.getLevelName(value)  # noqa
        if isinstance(lvl, str):
            lvl = logging.INFO
    return lvl


class RcpArgs(argparse.Namespace):
    config_dir: Path | None
    log_level: int | None


def make_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config_dir",
        "--config-dir",
        type=Path,
        help="Directory containing RCP config files",
        default=None,
    )
    parser.add_argument(
        "--log_level", "--log-level", type=parse_log_level, help="Logging level", default=None
    )
    return parser


def parse_args() -> RcpArgs:
    parser = make_parser()
    return typing.cast(RcpArgs, parser.parse_args())
