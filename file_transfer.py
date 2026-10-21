"""Copy and move files while verifying copies with SHA-256."""

import shutil
import verify
from pathlib import Path

from manifest import Manifest, ManifestEntry


class CopyVerificationError(Exception):
    """Raised when a copied file does not match its source."""


def copy_file_verified(source: Path, destination: Path) -> Manifest:
    """Copy one file, verify it with SHA-256, and return its manifest."""
    entry = _copy_file_verified(source, destination, source)
    return Manifest([entry])


def move_file_verified(source: Path, destination: Path) -> Manifest:
    """Copy and verify one file before deleting the source."""
    manifest = copy_file_verified(source, destination)
    source.unlink()
    return manifest


def _copy_file_verified(
    source: Path, destination: Path, display_path: Path
) -> ManifestEntry:
    """Copy a file and return its verified destination manifest entry."""
    source_hash = verify.compute_file_sha256(source)
    shutil.copy2(source, destination)
    destination_hash = verify.compute_file_sha256(destination)

    if source_hash != destination_hash:
        raise CopyVerificationError(
            f"SHA-256 mismatch for {display_path}: "
            f"source={source_hash}, destination={destination_hash}"
        )

    return ManifestEntry(
        path=destination,
        file_size_bytes=destination.stat().st_size,
        sha256=destination_hash,
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
) -> ManifestEntry:
    """Copy one source file and return its destination manifest entry."""
    relative_path = source_file.relative_to(source)
    destination_file = destination / relative_path
    destination_file.parent.mkdir(parents=True, exist_ok=True)
    return _copy_file_verified(
        source_file, destination_file, relative_path
    )


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
    entries = [
        _copy_directory_file(source_file, source, destination)
        for source_file in files
    ]
    return Manifest(entries)


def move_directory_verified(source: Path, destination: Path) -> Manifest:
    """Move a directory tree by copying and verifying each file before deletion.

    Files are copied with their paths relative to source. Existing destination
    files are overwritten. Each source file is deleted only after its copy has
    been verified with SHA-256. Returns a manifest of the destination files.
    Filesystem and verification failures are raised to the caller.
    """
    source, destination = _resolve_and_validate_directories(
        source, destination
    )

    files = sorted(path for path in source.rglob("*") if path.is_file())
    entries: list[ManifestEntry] = []
    for source_file in files:
        entry = _copy_directory_file(source_file, source, destination)
        source_file.unlink()
        entries.append(entry)
    return Manifest(entries)
