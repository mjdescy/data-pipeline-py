"""
Classes for file manifests.
"""
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path


def _compute_sha256(path: Path) -> str:
    """Compute the SHA-256 hash of a file."""
    sha256_hash = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            sha256_hash.update(chunk)
    return sha256_hash.hexdigest()


@dataclass
class ManifestEntry:
    """A single entry in a file manifest."""
    path: Path
    file_size_bytes: int
    sha256: str

    @classmethod
    def from_path(cls, path: Path) -> "ManifestEntry":
        """Create a manifest entry from a file path."""

        if not path.is_file():
            raise FileNotFoundError(f"Path does not point to a file: {path}")

        file_size_bytes = path.stat().st_size
        sha256_hash = _compute_sha256(path)
        return cls(
            path=path,
            file_size_bytes=file_size_bytes,
            sha256=sha256_hash,
        )

    def to_json(self) -> str:
        """Serialize the manifest entry as a JSON object."""
        return json.dumps({
            "path": str(self.path),
            "file_size_bytes": self.file_size_bytes,
            "sha256": self.sha256,
        })


class Manifest:
    """A file manifest containing multiple manifest entries."""

    def __init__(self, entries: list[ManifestEntry] | None = None) -> None:
        self.entries = entries if entries is not None else []

    def add_entry(self, entry: ManifestEntry) -> None:
        """Add a manifest entry to the manifest."""
        if not hasattr(self, "entries"):
            self.entries = []
        self.entries.append(entry)

    @classmethod
    def from_paths(cls, paths: list[Path]) -> "Manifest":
        """Create a manifest from a list of file paths."""
        manifest = cls()
        for path in paths:
            manifest.add_entry(ManifestEntry.from_path(path))
        return manifest

    @classmethod
    def from_directory_tree(cls, root: Path) -> "Manifest":
        """Create a manifest from all files in a directory tree."""
        manifest = cls()
        paths = [path for path in root.rglob("*") if path.is_file()]
        with ThreadPoolExecutor() as executor:
            manifest.entries.extend(
                executor.map(ManifestEntry.from_path, paths)
            )
        return manifest

    def to_json(self) -> str:
        """Serialize the manifest as a JSON array of manifest entries."""
        return json.dumps([json.loads(entry.to_json()) for entry in self.entries])
