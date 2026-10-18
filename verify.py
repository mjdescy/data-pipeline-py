import hashlib
def files_are_identical(path1: Path, path2: Path) -> bool:
    """Return True if the files at the given paths have the same SHA-256 digest."""
    return compute_file_sha256(path1) == compute_file_sha256(path2)
from pathlib import Path

def compute_file_sha256(path: Path) -> str:
    """Return the SHA-256 digest of a file, reading it in chunks."""
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
