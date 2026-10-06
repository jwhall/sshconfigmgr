# Changelog

All notable changes to this project will be documented in this file. This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]
### Added
- Save (`Ctrl+S` / Save button) opens a Save dialog.
- "Validate config with SSH?" option in the Save and Unsaved Changes dialogs: runs `ssh -G` on the config as it would be written, then saves (showing "✔️ Validated"), or on failure offers "Show error" (view ssh's output and return to the editor) or "Continue anyway". The option starts checked when `ssh` is installed and is remembered for the session.

### Fixed
- `Include` and other directives before the first `Host` block were deleted on save.
- `Key=Value` / `Key = Value` lines were dropped, and `Host=name` headers were merged into the previous block.
- `Match` blocks were merged into the preceding `Host` block; they are now listed as their own entries.
- Comments inside a block moved to the next block; a trailing comment at end of file was dropped.
- Blank lines accumulated by one per save.
- Non-UTF-8 bytes were replaced with U+FFFD on save.
- The "HOSTS" pane title and the editor header (current host name) were blank: a `height: 1` box with a bottom border has no room for text.
- "Save & Quit" quit (discarding edits) when the save failed validation, failed to write, or an overwrite was declined; it now only quits after a successful save.
- Opening another file (`o`) discarded unsaved changes without asking; it now offers Save / Discard / Cancel first.
- Moving through the host list (and sometimes just launching) marked the file as unsaved. The unsaved flag is now derived from content — it is set only when the file as it would be written differs from what was last loaded or saved, so undoing an edit by hand also clears it.

### Changed
- The parser is now lossless: an unmodified config saves byte-for-byte identical, and edits re-render only the changed lines using the block's existing indentation and separator style.
- Saves are atomic (temp file, fsync, rename), preserve the existing file mode and ownership, create new files as `0600`, and write through symlinks.
- Saving now detects if the file changed on disk since it was opened and asks before overwriting.
- The host list is now an `OptionList`, which draws rows as lines instead of one widget per host: startup with 1,000 hosts drops from ~4.4 s to ~0.25 s, and moving between hosts no longer slows down as the list grows.
- Switching hosts reuses the editor's existing parameter rows instead of rebuilding them, so moving between hosts costs the same regardless of how many parameters each has.
- Deleting a host now selects the next host instead of jumping to the top of the list.
- Excludes Textual 2.0.0 and 2.0.1, whose `OptionList` does not display added options.
- The keyword picker's suggestion list is now an `OptionList` (no longer rebuilds ~80 widgets per keystroke), and it grows or shrinks with the terminal so its Cancel/Add buttons stay visible on short terminals.

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
