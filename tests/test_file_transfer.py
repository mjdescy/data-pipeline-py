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

            result = file_transfer.copy_directory_verified(source, destination)

            self.assertEqual(
                [entry.path for entry in result.manifest.entries],
                [
                    destination / "first.txt",
                    destination / "nested" / "second.bin",
                ],
            )
            self.assertEqual(
                [entry.file_size_bytes for entry in result.manifest.entries],
                [len(b"first file"), len(b"\x00\x01second")],
            )
            self.assertEqual(result.errors, [])
            self.assertEqual(
                (destination / "first.txt").read_bytes(), b"first file"
            )
            self.assertEqual(
                (destination / "nested" / "second.bin").read_bytes(),
                b"\x00\x01second",
            )

    def test_returns_hash_mismatch_error(self):
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
                result = file_transfer.copy_directory_verified(
                    source, destination
                )

            self.assertEqual(len(result.errors), 1)
            self.assertIn("file.txt", result.errors[0])
            self.assertIn("SHA-256 mismatch", result.errors[0])
            self.assertEqual(result.manifest.entries, [])

    def test_attempts_all_files_and_returns_all_copy_errors(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "source"
            source.mkdir()
            (source / "first.txt").write_text("first")
            (source / "middle.txt").write_text("middle")
            (source / "last.txt").write_text("last")
            attempted = []
            original_copy2 = file_transfer.shutil.copy2

            def fail_selected_copies(source_file, destination_file):
                attempted.append(source_file.name)
                if source_file.name != "middle.txt":
                    raise OSError(f"failed {source_file.name}")
                return original_copy2(source_file, destination_file)

            with patch(
                "file_transfer.shutil.copy2",
                side_effect=fail_selected_copies,
            ):
                result = file_transfer.copy_directory_verified(
                    source, root / "destination"
                )

            self.assertEqual(
                attempted, ["first.txt", "last.txt", "middle.txt"]
            )
            self.assertEqual(len(result.errors), 2)
            self.assertTrue(
                any("first.txt: failed first.txt" in error
                    for error in result.errors)
            )
            self.assertTrue(
                any("last.txt: failed last.txt" in error
                    for error in result.errors)
            )
            self.assertEqual(
                [entry.path.name for entry in result.manifest.entries],
                ["middle.txt"],
            )

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
            (source / "nested" / "deeper").mkdir(parents=True)
            (source / "empty").mkdir()
            (source / "first.txt").write_bytes(b"first file")
            (source / "nested" / "deeper" / "second.bin").write_bytes(
                b"\x00second"
            )

            result = file_transfer.move_directory_verified(
                source, destination
            )

            self.assertEqual(
                [entry.path for entry in result.manifest.entries],
                [
                    destination / "first.txt",
                    destination / "nested" / "deeper" / "second.bin",
                ],
            )
            self.assertEqual(result.errors, [])
            self.assertFalse((source / "first.txt").exists())
            self.assertFalse(
                (source / "nested" / "deeper" / "second.bin").exists()
            )
            self.assertTrue(source.is_dir())
            self.assertFalse((source / "nested").exists())
            self.assertFalse((source / "nested" / "deeper").exists())
            self.assertFalse((source / "empty").exists())
            for entry in result.manifest.entries:
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
                result = file_transfer.move_directory_verified(
                    source, root / "destination"
                )

            self.assertEqual(len(result.errors), 1)
            self.assertIn("SHA-256 mismatch", result.errors[0])
            self.assertEqual(result.manifest.entries, [])
            self.assertTrue(source_file.exists())

    def test_attempts_all_files_and_preserves_failed_sources(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "source"
            failed_dir = source / "failed"
            success_dir = source / "success"
            empty_dir = source / "empty"
            failed_dir.mkdir(parents=True)
            success_dir.mkdir()
            empty_dir.mkdir()
            failed_file = failed_dir / "first.txt"
            successful_file = success_dir / "second.txt"
            failed_file.write_text("first")
            successful_file.write_text("second")
            destination = root / "destination"
            attempted = []
            original_copy2 = file_transfer.shutil.copy2

            def fail_first_copy(source_file, destination_file):
                attempted.append(source_file.name)
                if source_file.name == "first.txt":
                    raise OSError("first copy failed")
                return original_copy2(source_file, destination_file)

            with patch(
                "file_transfer.shutil.copy2",
                side_effect=fail_first_copy,
            ):
                result = file_transfer.move_directory_verified(
                    source, destination
                )

            self.assertCountEqual(attempted, ["first.txt", "second.txt"])
            self.assertEqual(len(result.errors), 1)
            self.assertIn("first.txt: first copy failed", result.errors[0])
            self.assertEqual(
                [entry.path for entry in result.manifest.entries],
                [destination / "success" / "second.txt"],
            )
            self.assertTrue(failed_file.exists())
            self.assertFalse(successful_file.exists())
            self.assertTrue(source.is_dir())
            self.assertTrue(failed_dir.is_dir())
            self.assertFalse(success_dir.exists())
            self.assertFalse(empty_dir.exists())


if __name__ == "__main__":
    unittest.main()
