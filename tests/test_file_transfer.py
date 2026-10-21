import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import file_transfer


class CopyDirectoryVerifiedTests(unittest.TestCase):
    def test_copies_files_recursively_and_preserves_contents(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "source"
            destination = root / "destination"
            (source / "nested").mkdir(parents=True)
            (source / "first.txt").write_bytes(b"first file")
            (source / "nested" / "second.bin").write_bytes(b"\x00\x01second")

            manifest = file_transfer.copy_directory_verified(source, destination)

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

            with patch("file_transfer.shutil.copy2", side_effect=corrupt_copy):
                with self.assertRaisesRegex(
                    file_transfer.CopyVerificationError, "SHA-256 mismatch"
                ):
                    file_transfer.copy_directory_verified(source, destination)

    def test_rejects_destination_inside_source(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "source"
            source.mkdir()

            with self.assertRaisesRegex(ValueError, "inside it"):
                file_transfer.copy_directory_verified(
                    source, source / "destination"
                )


class CopyAndMoveFileVerifiedTests(unittest.TestCase):
    def test_copy_file_returns_destination_manifest(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "source.txt"
            destination = root / "destination.txt"
            source.write_bytes(b"file contents")

            manifest = file_transfer.copy_file_verified(source, destination)

            self.assertEqual(len(manifest.entries), 1)
            entry = manifest.entries[0]
            self.assertEqual(entry.path, destination)
            self.assertEqual(entry.file_size_bytes, len(b"file contents"))
            self.assertEqual(
                entry.sha256, file_transfer.verify.compute_file_sha256(source)
            )
            self.assertTrue(source.exists())

    def test_copy_file_raises_when_copy_fails(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "source.txt"
            source.write_text("contents")

            with patch(
                "file_transfer.shutil.copy2",
                side_effect=OSError("copy failed"),
            ):
                with self.assertRaisesRegex(OSError, "copy failed"):
                    file_transfer.copy_file_verified(
                        source, root / "destination.txt"
                    )

    def test_move_file_verifies_copy_then_removes_source(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "source.txt"
            destination = root / "destination.txt"
            source.write_bytes(b"file contents")

            manifest = file_transfer.move_file_verified(source, destination)

            self.assertFalse(source.exists())
            self.assertEqual(destination.read_bytes(), b"file contents")
            self.assertEqual(manifest.entries[0].path, destination)
            self.assertEqual(
                manifest.entries[0].sha256,
                file_transfer.verify.compute_file_sha256(destination),
            )

    def test_move_file_keeps_source_when_copy_hashes_differ(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "source.txt"
            destination = root / "destination.txt"
            source.write_text("source")

            def corrupt_copy(source_file, destination_file):
                destination_file.write_text(
                    f"{source_file.read_text()}corrupted"
                )

            with patch(
                "file_transfer.shutil.copy2", side_effect=corrupt_copy
            ):
                with self.assertRaisesRegex(
                    file_transfer.CopyVerificationError, "SHA-256 mismatch"
                ):
                    file_transfer.move_file_verified(source, destination)

            self.assertTrue(source.exists())


class MoveDirectoryVerifiedTests(unittest.TestCase):
    def test_moves_files_recursively_and_returns_destination_manifest(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "source"
            destination = root / "destination"
            (source / "nested").mkdir(parents=True)
            (source / "first.txt").write_bytes(b"first file")
            (source / "nested" / "second.bin").write_bytes(b"\x00second")

            manifest = file_transfer.move_directory_verified(
                source, destination
            )

            self.assertEqual(
                [entry.path for entry in manifest.entries],
                [
                    destination / "first.txt",
                    destination / "nested" / "second.bin",
                ],
            )
            self.assertFalse((source / "first.txt").exists())
            self.assertFalse((source / "nested" / "second.bin").exists())
            for entry in manifest.entries:
                self.assertEqual(
                    entry.sha256,
                    file_transfer.verify.compute_file_sha256(entry.path),
                )

    def test_move_directory_keeps_source_when_copy_hashes_differ(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "source"
            source.mkdir()
            source_file = source / "file.txt"
            source_file.write_text("source")

            def corrupt_copy(source_path, destination_path):
                destination_path.write_text(
                    f"{source_path.read_text()}corrupted"
                )

            with patch(
                "file_transfer.shutil.copy2", side_effect=corrupt_copy
            ):
                with self.assertRaisesRegex(
                    file_transfer.CopyVerificationError, "SHA-256 mismatch"
                ):
                    file_transfer.move_directory_verified(
                        source, root / "destination"
                    )

            self.assertTrue(source_file.exists())


if __name__ == "__main__":
    unittest.main()
