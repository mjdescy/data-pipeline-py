import compress
import hashlib
import json
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from compression import zstd


class CompressFileTests(unittest.TestCase):
    def test_compresses_file_and_writes_manifest(self):
        contents = b"single file contents" * 100
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "sample.bin"
            archive_path = root / "sample.bin.zst"
            source.write_bytes(contents)

            manifest = compress.compress_file(source, archive_path)

            with zstd.ZstdFile(archive_path, mode="rb") as compressed_file:
                self.assertEqual(compressed_file.read(), contents)

            entry = manifest.entries[0]
            self.assertEqual(entry.path, Path(source.name))
            self.assertEqual(entry.file_size_bytes, len(contents))
            self.assertEqual(
                entry.sha256, hashlib.sha256(contents).hexdigest()
            )
            manifest_path = root / "sample.bin.zst.manifest.json"
            self.assertEqual(
                json.loads(manifest_path.read_text(encoding="utf-8")),
                [{
                    "path": source.name,
                    "file_size_bytes": len(contents),
                    "sha256": hashlib.sha256(contents).hexdigest(),
                }],
            )

    def test_compression_uses_maximum_level(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "sample.txt"
            source.write_text("content")

            with patch(
                "compress.zstd.ZstdFile", wraps=zstd.ZstdFile
            ) as zstd_file:
                compress.compress_file(source, root / "sample.zst")

            self.assertEqual(
                zstd_file.call_args.kwargs["level"],
                compress.ZSTD_COMPRESSION_LEVEL,
            )
            self.assertEqual(compress.ZSTD_COMPRESSION_LEVEL, 6)

    def test_rejects_missing_input_file(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)

            with self.assertRaises(FileNotFoundError):
                compress.compress_file(root / "missing.txt", root / "out.zst")

    def test_rejects_archive_path_that_would_overwrite_source(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "sample.txt"
            source.write_text("content")

            with self.assertRaisesRegex(ValueError, "must not overwrite"):
                compress.compress_file(source, source)


class CompressDirectoryTests(unittest.TestCase):
    def test_compression_uses_maximum_level(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "source"
            source.mkdir()

            with patch(
                "compress.tarfile.open", wraps=tarfile.open
            ) as tar_open:
                compress.compress_directory(source, root / "source.tar.zst")

            self.assertEqual(
                tar_open.call_args.kwargs["level"],
                compress.ZSTD_COMPRESSION_LEVEL,
            )

    def test_compresses_tree_to_tar_zstd_and_manifests_each_file(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "source"
            nested = source / "nested"
            nested.mkdir(parents=True)
            (source / "root.txt").write_bytes(b"root content")
            (nested / "child.bin").write_bytes(b"\x00child content")
            archive_path = root / "source.tar.zst"

            manifest = compress.compress_directory(source, archive_path)

            with tarfile.open(archive_path, mode="r:zst") as archive:
                self.assertEqual(
                    set(archive.getnames()),
                    {"root.txt", "nested/child.bin"},
                )
                self.assertEqual(
                    archive.extractfile("root.txt").read(),
                    b"root content",
                )
                self.assertEqual(
                    archive.extractfile("nested/child.bin").read(),
                    b"\x00child content",
                )

            expected = {
                Path("root.txt"): b"root content",
                Path("nested/child.bin"): b"\x00child content",
            }
            self.assertEqual(
                {entry.path for entry in manifest.entries}, set(expected)
            )
            for entry in manifest.entries:
                contents = expected[entry.path]
                self.assertEqual(entry.file_size_bytes, len(contents))
                self.assertEqual(
                    entry.sha256, hashlib.sha256(contents).hexdigest()
                )

            manifest_path = root / "source.tar.zst.manifest.json"
            self.assertEqual(
                json.loads(manifest_path.read_text(encoding="utf-8")),
                [
                    {
                        "path": entry.path.as_posix(),
                        "file_size_bytes": entry.file_size_bytes,
                        "sha256": entry.sha256,
                    }
                    for entry in manifest.entries
                ],
            )

    def test_compresses_empty_directory_tree(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "empty"
            source.mkdir()
            archive_path = root / "empty.tar.zst"

            manifest = compress.compress_directory(source, archive_path)

            self.assertEqual(manifest.entries, [])
            self.assertEqual(
                json.loads(
                    (root / "empty.tar.zst.manifest.json").read_text(
                        encoding="utf-8"
                    )
                ),
                [],
            )
            with tarfile.open(archive_path, mode="r:zst") as archive:
                self.assertEqual(archive.getnames(), [])

    def test_rejects_archive_inside_source_tree(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "source"
            source.mkdir()

            with self.assertRaisesRegex(ValueError, "inside the source"):
                compress.compress_directory(source, source / "archive.tar.zst")

    def test_rejects_symlinks_in_source_tree(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "source"
            source.mkdir()
            target = root / "target.txt"
            target.write_text("outside")
            (source / "linked.txt").symlink_to(target)

            with self.assertRaisesRegex(ValueError, "contains a symlink"):
                compress.compress_directory(
                    source, root / "archive.tar.zst"
                )


if __name__ == "__main__":
    unittest.main()
