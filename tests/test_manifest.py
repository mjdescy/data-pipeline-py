import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from manifest import Manifest, ManifestEntry


FIXTURE_TREE = Path(__file__).parent / "fixtures" / "manifest_tree"


class ManifestEntryTests(unittest.TestCase):
    def test_from_path_records_size_and_sha256(self):
        path = FIXTURE_TREE / "root.txt"

        entry = ManifestEntry.from_path(path)

        contents = path.read_bytes()
        self.assertEqual(entry.path, path)
        self.assertEqual(entry.file_size_bytes, len(contents))
        self.assertEqual(entry.sha256, hashlib.sha256(contents).hexdigest())

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

    def test_to_json_serializes_entry_fields(self):
        path = FIXTURE_TREE / "root.txt"
        entry = ManifestEntry.from_path(path)

        self.assertEqual(json.loads(entry.to_json()), {
            "path": str(path),
            "file_size_bytes": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        })


class ManifestTests(unittest.TestCase):
    def test_init_and_add_entry(self):
        manifest = Manifest()
        entry = ManifestEntry.from_path(FIXTURE_TREE / "root.txt")

        self.assertEqual(manifest.entries, [])
        manifest.add_entry(entry)
        self.assertEqual(manifest.entries, [entry])

    def test_init_accepts_entries(self):
        entry = ManifestEntry.from_path(FIXTURE_TREE / "root.txt")

        manifest = Manifest([entry])

        self.assertEqual(manifest.entries, [entry])

    def test_from_paths_creates_entries_in_input_order(self):
        paths = [
            FIXTURE_TREE / "nested" / "child.txt",
            FIXTURE_TREE / "root.txt",
        ]

        manifest = Manifest.from_paths(paths)

        self.assertEqual([entry.path for entry in manifest.entries], paths)
        for entry, path in zip(manifest.entries, paths):
            contents = path.read_bytes()
            self.assertEqual(entry.file_size_bytes, len(contents))
            self.assertEqual(
                entry.sha256, hashlib.sha256(contents).hexdigest()
            )

    def test_from_directory_tree_crawls_nested_fixture_files(self):
        manifest = Manifest.from_directory_tree(FIXTURE_TREE)

        expected_paths = {
            FIXTURE_TREE / "root.txt",
            FIXTURE_TREE / "nested" / "child.txt",
        }
        self.assertEqual({entry.path for entry in manifest.entries}, expected_paths)
        for entry in manifest.entries:
            contents = entry.path.read_bytes()
            self.assertEqual(entry.file_size_bytes, len(contents))
            self.assertEqual(
                entry.sha256, hashlib.sha256(contents).hexdigest()
            )

    def test_to_json_serializes_entries_as_json_array(self):
        manifest = Manifest.from_paths([
            FIXTURE_TREE / "root.txt",
            FIXTURE_TREE / "nested" / "child.txt",
        ])

        self.assertEqual(
            json.loads(manifest.to_json()),
            [
                json.loads(entry.to_json())
                for entry in manifest.entries
            ],
        )


if __name__ == "__main__":
    unittest.main()
