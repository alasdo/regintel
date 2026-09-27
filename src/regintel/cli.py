"""Command-line entry point: `regintel <command>`."""

from __future__ import annotations

import argparse
import logging
from collections.abc import Sequence


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="regintel")
    parser.add_subparsers(dest="command", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    args = build_parser().parse_args(argv)
    raise SystemExit(f"unknown command {args.command!r}")
