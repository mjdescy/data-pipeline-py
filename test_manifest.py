import tempfile
import unittest
from pathlib import Path

from manifest import ManifestEntry


class ManifestEntryTests(unittest.TestCase):
    def test_from_path_rejects_nonexistent_file(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "missing.txt"

            with self.assertRaisesRegex(
                FileNotFoundError, "Path does not point to a file"
            ):
                ManifestEntry.from_path(path)

    def test_from_path_rejects_directory(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory)

            with self.assertRaisesRegex(
                FileNotFoundError, "Path does not point to a file"
            ):
                ManifestEntry.from_path(path)


if __name__ == "__main__":
    unittest.main()
