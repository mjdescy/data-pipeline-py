"""Copy files between directories and verify each copy with SHA-256."""

import argparse
import hashlib
import json
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path


class CopyVerificationError(Exception):
    """Raised when a copied file does not match its source."""


@dataclass
class ManifestEntry:
    path: Path
    size_bytes: int
    sha256: str

    def to_json(self) -> str:
        """Serialize the manifest entry as a JSON object."""
        return json.dumps({
            "path": str(self.path),
            "size_bytes": self.size_bytes,
            "sha256": self.sha256,
        })


@dataclass
class Manifest:
    entries: list[ManifestEntry]

    def to_json(self) -> str:
        """Serialize the manifest as a JSON array of manifest entries."""
        return json.dumps([json.loads(entry.to_json()) for entry in self.entries])


def sha256_file(path: Path) -> str:
    """Return the SHA-256 digest of a file, reading it in chunks."""
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def copy_file_verified(source: Path, destination: Path) -> None:
    """Copy a single file and verify it with SHA-256."""
    _copy_file_verified(source, destination, source)


def _copy_file_verified(
    source: Path, destination: Path, display_path: Path
) -> None:
    """Copy a file and report digest mismatches using the given path."""
    source_hash = sha256_file(source)
    shutil.copy2(source, destination)
    destination_hash = sha256_file(destination)

    if source_hash != destination_hash:
        raise CopyVerificationError(
            f"SHA-256 mismatch for {display_path}: "
            f"source={source_hash}, destination={destination_hash}"
        )


def _resolve_and_validate_directories(
    source: Path, destination: Path
) -> tuple[Path, Path]:
    """Resolve directories and ensure the destination is not inside source."""
    source = source.resolve()
    destination = destination.resolve()

    if not source.is_dir():
        raise NotADirectoryError(f"Source directory does not exist: {source}")
    if destination == source or source in destination.parents:
        raise ValueError(
            "Destination must not be the source directory or inside it")

    return source, destination


def _copy_directory_file(
    source_file: Path, source: Path, destination: Path
) -> Path:
    """Copy one source file to its corresponding destination path."""
    relative_path = source_file.relative_to(source)
    destination_file = destination / relative_path
    destination_file.parent.mkdir(parents=True, exist_ok=True)
    _copy_file_verified(source_file, destination_file, relative_path)
    return destination_file


def copy_directory_verified(source: Path, destination: Path) -> Manifest:
    """Copy source files recursively, verifying each destination with SHA-256.

    Files are copied with their paths relative to source. Existing destination
    files are overwritten. Raises OSError for filesystem failures and
    CopyVerificationError when a source and destination digest differ. Returns
    a manifest of the verified destination paths.
    """
    source, destination = _resolve_and_validate_directories(
        source, destination
    )

    files = sorted(path for path in source.rglob("*") if path.is_file())
    destination_paths = [
        _copy_directory_file(source_file, source, destination)
        for source_file in files
    ]
    return Manifest([ManifestEntry(
        path=path,
        size_bytes=path.stat().st_size,
        sha256=sha256_file(path)
    ) for path in destination_paths])


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
