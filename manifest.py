"""
Classes for file manifests.
"""
import json
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ManifestEntry:
    path: Path
    file_size_bytes: int
    sha256: str

    def to_json(self) -> str:
        """Serialize the manifest entry as a JSON object."""
        return json.dumps({
            "path": str(self.path),
            "file_size_bytes": self.file_size_bytes,
            "sha256": self.sha256,
        })


@dataclass
class Manifest:
    entries: list[ManifestEntry]

    def to_json(self) -> str:
        """Serialize the manifest as a JSON array of manifest entries."""
        return json.dumps([json.loads(entry.to_json()) for entry in self.entries])
