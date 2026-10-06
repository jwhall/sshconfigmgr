"""Tests for atomic, permission-preserving saves."""
from __future__ import annotations

import os
import stat
import sys
from pathlib import Path

import pytest

from sshconfigmgr import ssh_config
from sshconfigmgr.ssh_config import ConfigChangedError, SSHConfig

posix_only = pytest.mark.skipif(sys.platform == "win32", reason="POSIX permissions/symlinks")


def leftovers(directory: Path) -> list[str]:
    return sorted(p.name for p in directory.iterdir() if p.name.endswith(".tmp"))


@posix_only
def test_new_file_is_private(tmp_config: Path) -> None:
    config = SSHConfig.from_path(tmp_config)
    config.add_entry("a")
    config.save()
    assert stat.S_IMODE(tmp_config.stat().st_mode) == 0o600


@posix_only
def test_existing_mode_is_preserved(tmp_config: Path) -> None:
    tmp_config.write_text("Host a\n")
    os.chmod(tmp_config, 0o640)
    config = SSHConfig.from_path(tmp_config)
    config.entries[0].set("User", "x")
    config.save()
    assert stat.S_IMODE(tmp_config.stat().st_mode) == 0o640


@posix_only
def test_symlink_is_written_through(tmp_path: Path) -> None:
    real = tmp_path / "dotfiles" / "ssh_config"
    real.parent.mkdir()
    real.write_text("Host a\n")
    link = tmp_path / "config"
    link.symlink_to(real)
    config = SSHConfig.from_path(link)
    config.entries[0].set("User", "x")
    config.save()
    assert link.is_symlink()
    assert real.read_text() == "Host a\n    User x\n"


def test_no_temp_file_left_behind(tmp_config: Path) -> None:
    tmp_config.write_text("Host a\n")
    SSHConfig.from_path(tmp_config).save()
    assert leftovers(tmp_config.parent) == []


def test_failed_replace_keeps_original_and_cleans_up(
    tmp_config: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tmp_config.write_text("Host a\n    User original\n")
    config = SSHConfig.from_path(tmp_config)
    config.entries[0].set("User", "changed")

    def boom(src: str, dst: str) -> None:
        raise OSError("disk on fire")

    monkeypatch.setattr(ssh_config.os, "replace", boom)
    with pytest.raises(OSError, match="disk on fire"):
        config.save()
    assert tmp_config.read_text() == "Host a\n    User original\n"
    assert leftovers(tmp_config.parent) == []


def test_external_modification_is_detected(tmp_config: Path) -> None:
    tmp_config.write_text("Host a\n")
    config = SSHConfig.from_path(tmp_config)
    tmp_config.write_text("Host a\n    User someone-else\n")
    os.utime(tmp_config, ns=(0, 0))  # mtime granularity can hide the change
    assert config.changed_on_disk()
    with pytest.raises(ConfigChangedError):
        config.save()
    assert "someone-else" in tmp_config.read_text()
    config.save(force=True)
    assert tmp_config.read_text() == "Host a\n"


def test_file_created_after_load_is_detected(tmp_config: Path) -> None:
    config = SSHConfig.from_path(tmp_config)
    tmp_config.write_text("Host other\n")
    with pytest.raises(ConfigChangedError):
        config.save()


def test_consecutive_saves_do_not_conflict(tmp_config: Path) -> None:
    config = SSHConfig.from_path(tmp_config)
    config.add_entry("a")
    config.save()
    config.entries[0].set("User", "x")
    config.save()
    assert tmp_config.read_text() == "Host a\n    User x\n"
