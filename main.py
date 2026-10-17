"""Command-line interface for verified directory copies."""

import argparse
import os
import sys
import tempfile
from pathlib import Path

from copy_verify import CopyVerificationError, copy_directory_verified
from manifest import Manifest


def _create_argument_parser() -> argparse.ArgumentParser:
    """Create the command-line argument parser."""
    parser = argparse.ArgumentParser(
        description="Recursively copy files and verify each copy with SHA-256."
    )
    parser.add_argument("source", type=Path,
                        help="Directory to copy files from")
    parser.add_argument("destination", type=Path,
                        help="Directory to copy files to")
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("manifest.json"),
        help="Path for the output manifest (default: manifest.json)",
    )
    return parser


def _prepare_manifest_path(
    manifest_path: Path, source: Path, destination: Path
) -> Path:
    """Remove any previous manifest and reject paths that overlap copied data."""
    manifest_path = manifest_path.resolve()
    source = source.resolve()
    destination = destination.resolve()

    if manifest_path.is_relative_to(source):
        raise ValueError("Manifest path must not be inside the source directory")
    if manifest_path.is_relative_to(destination):
        raise ValueError(
            "Manifest path must not be inside the destination directory"
        )

    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.unlink(missing_ok=True)
    return manifest_path


def _write_manifest_atomically(manifest: Manifest, manifest_path: Path) -> None:
    """Durably write a manifest then atomically publish its final path."""
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=manifest_path.parent,
            prefix=f".{manifest_path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            temporary_file.write(manifest.to_json())
            temporary_file.write("\n")
            temporary_file.flush()
            os.fsync(temporary_file.fileno())

        os.replace(temporary_path, manifest_path)
        temporary_path = None

        directory_fd = os.open(manifest_path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    args = _create_argument_parser().parse_args(argv)

    try:
        manifest_path = _prepare_manifest_path(
            args.manifest, args.source, args.destination
        )
        manifest = copy_directory_verified(args.source, args.destination)
        _write_manifest_atomically(manifest, manifest_path)
    except (OSError, ValueError, CopyVerificationError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    print(f"Wrote manifest to {manifest_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
