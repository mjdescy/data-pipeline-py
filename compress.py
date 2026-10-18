"""Create Zstandard-compressed files and directory archives."""

import os
import shutil
import tarfile
import tempfile
from pathlib import Path

from compression import zstd

from manifest import Manifest, ManifestEntry


ZSTD_COMPRESSION_LEVEL = 6


def _manifest_path(archive_path: Path) -> Path:
    """Return the sidecar manifest path for an archive."""
    return archive_path.with_name(f"{archive_path.name}.manifest.json")


def _create_temporary_path(parent: Path, prefix: str) -> Path:
    """Create a temporary file path in the destination directory."""
    with tempfile.NamedTemporaryFile(
        dir=parent, prefix=prefix, suffix=".tmp", delete=False
    ) as temporary_file:
        return Path(temporary_file.name)


def _write_manifest(manifest: Manifest, path: Path) -> None:
    """Write a manifest JSON sidecar."""
    path.write_text(manifest.to_json() + "\n", encoding="utf-8")


def _publish_archive(
    temporary_archive: Path,
    archive_path: Path,
    manifest: Manifest,
) -> Manifest:
    """Publish an archive and its manifest sidecar."""
    temporary_manifest = _create_temporary_path(
        archive_path.parent, f".{archive_path.name}.manifest."
    )
    try:
        _write_manifest(manifest, temporary_manifest)
        os.replace(temporary_archive, archive_path)
        os.replace(temporary_manifest, _manifest_path(archive_path))
    finally:
        temporary_manifest.unlink(missing_ok=True)
        temporary_archive.unlink(missing_ok=True)
    return manifest


def compress_file(source: Path, archive_path: Path) -> Manifest:
    """Compress one file to a Zstandard stream and write its manifest.

    The manifest is written beside the archive as
    ``<archive name>.manifest.json``. Its entry path is the file name stored
    in the compressed stream.
    """
    source = Path(source).resolve()
    archive_path = Path(archive_path).resolve()

    if not source.is_file():
        raise FileNotFoundError(f"Input path is not a file: {source}")

    manifest_path = _manifest_path(archive_path)
    if archive_path == source or manifest_path == source:
        raise ValueError("Archive and manifest paths must not overwrite source")

    archive_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_archive = _create_temporary_path(
        archive_path.parent, f".{archive_path.name}."
    )
    try:
        with source.open("rb") as source_file:
            with zstd.ZstdFile(
                temporary_archive,
                mode="wb",
                level=ZSTD_COMPRESSION_LEVEL,
            ) as compressed_file:
                shutil.copyfileobj(source_file, compressed_file)

        source_entry = ManifestEntry.from_path(source)
        manifest = Manifest([ManifestEntry(
            path=Path(source.name),
            file_size_bytes=source_entry.file_size_bytes,
            sha256=source_entry.sha256,
        )])
        return _publish_archive(temporary_archive, archive_path, manifest)
    finally:
        temporary_archive.unlink(missing_ok=True)


def compress_directory(source: Path, archive_path: Path) -> Manifest:
    """Compress a directory tree into a Zstandard-compressed TAR archive.

    Files are stored at paths relative to the source directory. Symlinks are
    rejected rather than following paths outside the tree. The manifest is
    written beside the archive as ``<archive name>.manifest.json`` and records
    each file using its relative archive path.
    """
    source = Path(source).resolve()
    archive_path = Path(archive_path).resolve()

    if not source.is_dir():
        raise NotADirectoryError(f"Input path is not a directory: {source}")
    if archive_path == source or source in archive_path.parents:
        raise ValueError("Archive must not be inside the source directory")

    paths = sorted(source.rglob("*"))
    symlinks = [path for path in paths if path.is_symlink()]
    if symlinks:
        raise ValueError(f"Directory tree contains a symlink: {symlinks[0]}")

    files = [path for path in paths if path.is_file()]
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_archive = _create_temporary_path(
        archive_path.parent, f".{archive_path.name}."
    )
    try:
        with tarfile.open(
            temporary_archive,
            mode="w:zst",
            level=ZSTD_COMPRESSION_LEVEL,
        ) as archive:
            for path in files:
                relative_path = path.relative_to(source)
                archive.add(
                    path,
                    arcname=relative_path.as_posix(),
                    recursive=False,
                )

        manifest_entries = []
        for path in files:
            relative_path = path.relative_to(source)
            source_entry = ManifestEntry.from_path(path)
            manifest_entries.append(ManifestEntry(
                path=relative_path,
                file_size_bytes=source_entry.file_size_bytes,
                sha256=source_entry.sha256,
            ))
        return _publish_archive(
            temporary_archive,
            archive_path,
            Manifest(manifest_entries),
        )
    finally:
        temporary_archive.unlink(missing_ok=True)


__all__ = [
    "ZSTD_COMPRESSION_LEVEL",
    "compress_directory",
    "compress_file",
]