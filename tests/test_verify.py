import hashlib
import tempfile
import unittest
from pathlib import Path

from verify import compute_file_sha256


class ComputeFileSha256Tests(unittest.TestCase):
    def test_returns_sha256_for_file_larger_than_one_chunk(self):
        contents = b"file contents" * 100_000
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "large.bin"
            path.write_bytes(contents)

            digest = compute_file_sha256(path)

        self.assertEqual(digest, hashlib.sha256(contents).hexdigest())

    def test_returns_sha256_for_empty_file(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "empty.bin"
            path.touch()

            digest = compute_file_sha256(path)

        self.assertEqual(digest, hashlib.sha256(b"").hexdigest())

    def test_raises_when_file_does_not_exist(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "missing.bin"

            with self.assertRaises(FileNotFoundError):
                compute_file_sha256(path)


if __name__ == "__main__":
    unittest.main()
