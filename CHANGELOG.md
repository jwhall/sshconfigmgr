# Changelog

All notable changes to this project will be documented in this file. This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]
### Fixed
- `Include` and other directives before the first `Host` block were deleted on save.
- `Key=Value` / `Key = Value` lines were dropped, and `Host=name` headers were merged into the previous block.
- `Match` blocks were merged into the preceding `Host` block; they are now listed as their own entries.
- Comments inside a block moved to the next block; a trailing comment at end of file was dropped.
- Blank lines accumulated by one per save.
- Non-UTF-8 bytes were replaced with U+FFFD on save.
- "Save & Quit" quit (discarding edits) when the save failed validation, failed to write, or an overwrite was declined; it now only quits after a successful save.
- Opening another file (`o`) discarded unsaved changes without asking; it now offers Save / Discard / Cancel first.

### Changed
- The parser is now lossless: an unmodified config saves byte-for-byte identical, and edits re-render only the changed lines using the block's existing indentation and separator style.
- Saves are atomic (temp file, fsync, rename), preserve the existing file mode and ownership, create new files as `0600`, and write through symlinks.
- Saving now detects if the file changed on disk since it was opened and asks before overwriting.

## [0.3.0] - 2026-03-12
### Added
- **Source Layout**: Migrated code to a `src/` directory structure for better packaging compliance.
- **CI/CD Workflow**: Added GitHub Actions to run tests automatically on Ubuntu and Windows.
- **Unit Tests**: Implemented a test suite for the SSH parser and port validation logic.
- **Package Metadata**: Added `__init__.py` and updated `pyproject.toml` with entry points and project URLs.
- **Edit Host Action**: Added the ability to rename or edit existing Host patterns within the TUI.

### Changed
- Refactored imports to use the `sshconfigmgr` namespace.
- Updated `pyproject.toml` version to 0.3.0.

## [0.2.0] - 2026-02-15
### Added
- Integrated validation logic for SSH Port ranges (1-65535).
- Implemented "Add Keyword" modal with live filtering of `ssh_config` directives.

## [0.1.0] - 2026-01-30
### Added
- Initial release with basic TUI functionality.
- Support for reading and saving standard SSH config files.
- Preamble and leading comment preservation.
