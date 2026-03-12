# Changelog

All notable changes to this project will be documented in this file. This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
