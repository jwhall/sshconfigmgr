#!/usr/bin/env python3
"""sshconfigmgr — TUI for managing SSH client configurations.

Usage:
    python main.py [config-file]
    python main.py ~/.ssh/config.work
"""
from __future__ import annotations

import argparse
from pathlib import Path

from app import SSHConfigApp


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="sshconfigmgr",
        description="TUI for managing SSH client configurations",
    )
    parser.add_argument(
        "config",
        nargs="?",
        default=str(Path.home() / ".ssh" / "config"),
        help="path to SSH config file (default: ~/.ssh/config)",
        metavar="CONFIG",
    )
    args = parser.parse_args()
    path = Path(args.config).expanduser().resolve()
    SSHConfigApp(path).run()


if __name__ == "__main__":
    main()
