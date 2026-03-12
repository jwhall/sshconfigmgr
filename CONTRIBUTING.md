# Contributing to sshconfigmgr

Thank you for your interest in improving `sshconfigmgr`! As a project maintained by a cybersecurity professional, I value security, code quality, and clear documentation.

## How to Contribute

### Reporting Bugs
- Use the [GitHub Issues](https://github.com/jwhall/sshconfigmgr/issues) page.
- Include your OS (Ubuntu, Arch, Windows, etc.) and Python version.
- Provide a sample of the SSH config that caused the issue (redacting sensitive hostnames/IPs).

### Feature Requests
- Open an issue to discuss the feature before implementation. 
- Ensure the feature aligns with the goal of managing `ssh_config(5)` directives.

### Pull Requests
1. **Fork the repo** and create your branch from `main`.
2. **Install in editable mode** with development dependencies:
   ```sh
   pip install -e .
   pip install pytest

1. **Ensure tests pass**: Run `pytest` before submitting.
2. **Follow the layout**: Place all source code in `src/sshconfigmgr/`.
3. **Update the Changelog**: Add a brief note under the `[Unreleased]` section.

## Development Standards

- **Python Version**: Target Python 3.11+.
- **TUI Framework**: This project uses [Textual](https://textual.textualize.io/). Familiarize yourself with their widget system.
- **Code Style**: Use straightforward, readable language and keep verbiage spare in the UI.