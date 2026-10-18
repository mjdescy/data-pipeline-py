import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import copy_verify
import main
from manifest import Manifest


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

    def test_cli_writes_manifest_file_as_json(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "source"
            destination = root / "destination"
            manifest_path = root / "manifest.json"
            source.mkdir()
            (source / "file.txt").write_text("content")
            stdout = StringIO()
            stderr = StringIO()

            original_directory = Path.cwd()
            try:
                os.chdir(root)
                with redirect_stdout(stdout), redirect_stderr(stderr):
                    result = main.main([str(source), str(destination)])
            finally:
                os.chdir(original_directory)

            self.assertEqual(result, 0)
            self.assertEqual(stdout.getvalue(), "")
            self.assertIn(str(manifest_path), stderr.getvalue())
            self.assertEqual(
                json.loads(manifest_path.read_text()),
                [{
                    "path": str(destination / "file.txt"),
                    "file_size_bytes": len("content"),
                    "sha256": copy_verify.sha256_file(destination / "file.txt"),
                }],
            )

    def test_cli_removes_stale_manifest_when_copy_fails(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "source"
            destination = root / "destination"
            manifest_path = root / "manifest.json"
            source.mkdir()
            manifest_path.write_text('{"old": true}')
            stderr = StringIO()

            with (
                patch(
                    "main.copy_directory_verified",
                    side_effect=OSError("copy failed"),
                ),
                redirect_stderr(stderr),
            ):
                result = main.main([
                    str(source), str(destination), "--manifest",
                    str(manifest_path),
                ])

            self.assertEqual(result, 1)
            self.assertFalse(manifest_path.exists())
            self.assertIn("copy failed", stderr.getvalue())

    def test_manifest_path_cannot_be_inside_destination(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "source"
            destination = root / "destination"
            source.mkdir()
            destination.mkdir()
            manifest_path = destination / "manifest.json"
            stderr = StringIO()

            with redirect_stderr(stderr):
                result = main.main([
                    str(source), str(destination), "--manifest",
                    str(manifest_path),
                ])

            self.assertEqual(result, 1)
            self.assertFalse(manifest_path.exists())
            self.assertIn("must not be inside", stderr.getvalue())

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
                copy_verify.copy_directory_verified(source, source / "destination")

    def test_manifest_from_directory_tree_includes_each_file(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            nested = root / "nested"
            nested.mkdir()
            (root / "first.txt").write_text("first")
            (nested / "second.txt").write_text("second")

            manifest = Manifest.from_directory_tree(root)

            self.assertEqual(
                {entry.path for entry in manifest.entries},
                {root / "first.txt", nested / "second.txt"},
            )
            self.assertEqual(
                {entry.path: entry.file_size_bytes for entry in manifest.entries},
                {root / "first.txt": 5, nested / "second.txt": 6},
            )


if __name__ == "__main__":
    unittest.main()
