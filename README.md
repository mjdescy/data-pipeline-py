# Verified file copy

Copy files recursively from one directory to another and verify each copied
file by comparing its SHA-256 digest before and after the copy. On success,
the command writes a JSON array of destination file paths to standard output.

```bash
python copy_verify.py /path/to/folder-a /path/to/folder-b
```

The utility preserves paths relative to the source directory and overwrites
files with matching destination paths. It prints the number of verified files
when successful and exits with a non-zero status if copying fails or any hash
does not match. The destination cannot be the source directory or a directory
inside it.

The function `copy_directory_verified(source, destination)` is also available
for use from Python code. It returns a `Manifest` whose `paths` field contains
the verified destination paths. `Manifest.to_json()` serializes those paths as
a JSON array of strings. The function raises `CopyVerificationError` if a hash
mismatch is detected.

Run the tests with:

```bash
python -m unittest
```
