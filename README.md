# Verified file copy and move

Copy files recursively from one directory to another and verify each copied
file by comparing its SHA-256 digest before and after the copy. On success,
the command atomically publishes a JSON manifest file.

```bash
python main.py /path/to/folder-a /path/to/folder-b
```

By default, the manifest is written to `manifest.json` in the current working
directory. Set `--manifest /path/to/manifest.json` to choose another location.
The manifest is first written and flushed to a temporary file in the same
directory, then atomically renamed into place. A previous manifest at that
path is removed when a run starts, so a failed run cannot leave an older
manifest looking like the result of the current run. The manifest path must
not be inside the source or destination directory.

The utility preserves paths relative to the source directory and overwrites
files with matching destination paths. Each manifest entry contains the
destination path, file size in bytes, and SHA-256 digest. The program exits
with a non-zero status if copying or manifest publication fails and reports
errors to standard error. It reports the published manifest path to standard
error on success.

The downstream process should wait for this process to exit successfully
before reading `manifest.json`; a missing file means no manifest was published
for the current run. Coordinate concurrent runs targeting the same manifest
path externally.

The Python functions `copy_file_verified(source, destination)` and
`copy_directory_verified(source, destination)` copy one file or a directory
tree. The corresponding `move_file_verified(source, destination)` and
`move_directory_verified(source, destination)` functions move files by copying
and verifying each destination's SHA-256 hash before deleting its source.
Every function returns a `Manifest` containing `ManifestEntry` objects for the
destination files. Filesystem failures and hash mismatches are raised to the
caller; a source file is not deleted if its copy fails verification.
`Manifest.to_json()` serializes the entries as a JSON array of objects.

Compression uses Python 3.14's standard-library Zstandard support. Use
`compress.compress_file(source, archive_path)` to create a single-file `.zst`
stream, or `compress.compress_directory(source, archive_path)` to create a
recursive `.tar.zst` archive. Both use the maximum Zstandard compression level
and return a `Manifest` with an entry for each archived file. Each archive is
accompanied by a JSON sidecar named `<archive name>.manifest.json`; manifest
paths are the file names stored inside the archive.

Run the tests with:

```bash
python -m unittest discover -v
```
