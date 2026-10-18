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


class MainTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
