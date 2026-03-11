"""pytest fixtures for sshconfigmgr tests."""
from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def tmp_config(tmp_path: Path) -> Path:
    """Return a Path to a writable temp SSH config location (file does not exist yet)."""
    return tmp_path / "ssh_config"
