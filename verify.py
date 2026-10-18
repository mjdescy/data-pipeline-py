import hashlib
from pathlib import Path
    
def compute_file_sha256(path: Path) -> str:
    """Return the SHA-256 digest of a file, reading it in chunks."""
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
