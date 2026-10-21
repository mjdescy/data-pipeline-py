# Verified file copy and move

Copy files recursively from one directory to another and verify each copied
file by comparing its SHA-256 digest before and after the copy. The command
atomically publishes a JSON manifest of files copied successfully.

```bash
python main.py /path/to/folder-a /path/to/folder-b
```

By default, the manifest is written to `manifest.json` in the current working
directory. Set `--manifest /path/to/manifest.json` to choose another location.
The manifest is first written and flushed to a temporary file in the same
directory, then atomically renamed into place. A previous manifest at that
path is removed when a run starts, so a failed run cannot leave an older
manifest looking like the result of the current run. If individual file
operations fail, a manifest of successful copies is still published and the
command exits with a non-zero status. The manifest path must not be inside the
source or destination directory.

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
`move_file_verified(source, destination)` operate on one file and return a
`Manifest`. The directory functions `copy_directory_verified(source,
destination)` and `move_directory_verified(source, destination)` return a
`DirectoryOperationResult` with a `manifest` of successfully copied
destinations and an `errors` list. They attempt every source file, reporting
filesystem failures and hash mismatches in that list. A move deletes a source
file only after its destination copy is verified. Once files are processed,
empty directories beneath the source are removed; the source directory itself
is preserved. The CLI writes the manifest of successful copies and exits
non-zero if any file operation failed. `Manifest.to_json()` serializes entries
as a JSON array of objects.

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
