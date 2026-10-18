import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import copy_verify


class CopyDirectoryVerifiedTests(unittest.TestCase):
    def test_copies_files_recursively_and_preserves_contents(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "source"
            destination = root / "destination"
            (source / "nested").mkdir(parents=True)
            (source / "first.txt").write_bytes(b"first file")
            (source / "nested" / "second.bin").write_bytes(b"\x00\x01second")

            manifest = copy_verify.copy_directory_verified(source, destination)

            self.assertEqual(
                [entry.path for entry in manifest.entries],
                [
                    destination / "first.txt",
                    destination / "nested" / "second.bin",
                ],
            )
            self.assertEqual(
                [entry.file_size_bytes for entry in manifest.entries],
                [len(b"first file"), len(b"\x00\x01second")],
            )
            self.assertEqual(
                (destination / "first.txt").read_bytes(), b"first file"
            )
            self.assertEqual(
                (destination / "nested" / "second.bin").read_bytes(),
                b"\x00\x01second",
            )

    def test_raises_when_destination_hash_differs(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "source"
            destination = root / "destination"
            source.mkdir()
            (source / "file.txt").write_text("source")

            def corrupt_copy(source_file, destination_file):
                destination_file.write_text(
                    f"{source_file.read_text()}corrupted"
                )

            with patch("copy_verify.shutil.copy2", side_effect=corrupt_copy):
                with self.assertRaisesRegex(
                    copy_verify.CopyVerificationError, "SHA-256 mismatch"
                ):
                    copy_verify.copy_directory_verified(source, destination)

    def test_rejects_destination_inside_source(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "source"
            source.mkdir()

            with self.assertRaisesRegex(ValueError, "inside it"):
                copy_verify.copy_directory_verified(
                    source, source / "destination"
                )


if __name__ == "__main__":
    unittest.main()
