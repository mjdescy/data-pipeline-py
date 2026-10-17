"""Command-line interface for verified directory copies."""

import argparse
import sys
from pathlib import Path

from copy_verify import CopyVerificationError, copy_directory_verified


def _create_argument_parser() -> argparse.ArgumentParser:
    """Create the command-line argument parser."""
    parser = argparse.ArgumentParser(
        description="Recursively copy files and verify each copy with SHA-256."
    )
    parser.add_argument("source", type=Path,
                        help="Directory to copy files from")
    parser.add_argument("destination", type=Path,
                        help="Directory to copy files to")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _create_argument_parser().parse_args(argv)

    try:
        manifest = copy_directory_verified(args.source, args.destination)
    except (OSError, ValueError, CopyVerificationError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    print(manifest.to_json())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
