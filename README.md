# Verified file copy

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

The function `copy_directory_verified(source, destination)` is also available
for use from Python code. It returns a `Manifest` whose `entries` field
contains `ManifestEntry` objects. `Manifest.to_json()` serializes them as a
JSON array of objects. The function raises `CopyVerificationError` if a hash
mismatch is detected.

Run the tests with:

```bash
python -m unittest discover -v
```
