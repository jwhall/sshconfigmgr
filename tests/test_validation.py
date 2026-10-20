"""Tests for port validation logic (mirrors SSHConfigApp._validate())."""
from __future__ import annotations

from pathlib import Path

import pytest

from sshconfigmgr.ssh_config import SSHConfig


# ─── Helper: replicate app._validate() logic without the TUI ──────────────────


def validate_ports(config: SSHConfig) -> list[str]:
    """Validate Port values in all entries; returns a list of error strings.

    This replicates the logic in SSHConfigApp._validate() so it can be tested
    without instantiating the Textual app.
    """
    errors: list[str] = []
    for entry in config.entries:
        port = entry.get("Port")
        if port is not None:
            try:
                p = int(port)
                if not (1 <= p <= 65535):
                    errors.append(f"Host {entry.pattern}: Port {p} out of range (1–65535)")
            except ValueError:
                errors.append(
                    f"Host {entry.pattern}: Port must be integer, got {port!r}"
                )
    return errors


def make_config(tmp_path: Path, host: str, port: str) -> SSHConfig:
    """Build an in-memory SSHConfig with a single entry that has the given port."""
    config_path = tmp_path / "config"
    config = SSHConfig(path=config_path)
    entry = config.add_entry(host)
    entry.set("Port", port)
    return config


# ─── Valid port values ────────────────────────────────────────────────────────


@pytest.mark.parametrize("port", ["1", "22", "80", "443", "8080", "65535"])
def test_valid_port(tmp_path: Path, port: str) -> None:
    """Common valid port numbers produce no validation errors."""
    config = make_config(tmp_path, "testhost", port)
    errors = validate_ports(config)
    assert errors == [], f"Expected no errors for port {port}, got: {errors}"


def test_valid_port_boundary_low(tmp_path: Path) -> None:
    """Port 1 is the lowest valid value."""
    config = make_config(tmp_path, "testhost", "1")
    assert validate_ports(config) == []


def test_valid_port_boundary_high(tmp_path: Path) -> None:
    """Port 65535 is the highest valid value."""
    config = make_config(tmp_path, "testhost", "65535")
    assert validate_ports(config) == []


# ─── Invalid port values ──────────────────────────────────────────────────────


def test_port_zero_is_invalid(tmp_path: Path) -> None:
    """Port 0 is out of range and should produce an error."""
    config = make_config(tmp_path, "testhost", "0")
    errors = validate_ports(config)
    assert len(errors) == 1
    assert "out of range" in errors[0]
    assert "testhost" in errors[0]


def test_port_too_high_is_invalid(tmp_path: Path) -> None:
    """Port 65536 is out of range and should produce an error."""
    config = make_config(tmp_path, "testhost", "65536")
    errors = validate_ports(config)
    assert len(errors) == 1
    assert "out of range" in errors[0]


def test_port_negative_is_invalid(tmp_path: Path) -> None:
    """A negative port number is out of range."""
    config = make_config(tmp_path, "testhost", "-1")
    errors = validate_ports(config)
    assert len(errors) == 1
    assert "out of range" in errors[0]


def test_non_integer_port_string(tmp_path: Path) -> None:
    """A non-integer port string should produce a 'must be integer' error."""
    config = make_config(tmp_path, "testhost", "ssh")
    errors = validate_ports(config)
    assert len(errors) == 1
    assert "must be integer" in errors[0]
    assert "testhost" in errors[0]


def test_float_port_string(tmp_path: Path) -> None:
    """A float string like '22.5' is not a valid integer port."""
    config = make_config(tmp_path, "testhost", "22.5")
    errors = validate_ports(config)
    assert len(errors) == 1
    assert "must be integer" in errors[0]


def test_empty_port_string(tmp_path: Path) -> None:
    """An empty string for Port should be treated as a non-integer error."""
    config = make_config(tmp_path, "testhost", "")
    errors = validate_ports(config)
    assert len(errors) == 1
    assert "must be integer" in errors[0]


# ─── No port: no error ────────────────────────────────────────────────────────


def test_no_port_no_error(tmp_path: Path) -> None:
    """An entry with no Port key produces no validation errors."""
    config_path = tmp_path / "config"
    config = SSHConfig(path=config_path)
    entry = config.add_entry("noporthost")
    entry.set("Hostname", "noporthost.example.com")
    errors = validate_ports(config)
    assert errors == []


# ─── Multiple entries ─────────────────────────────────────────────────────────


def test_multiple_entries_mixed_validity(tmp_path: Path) -> None:
    """Only invalid ports produce errors; valid ones are silent."""
    config_path = tmp_path / "config"
    config = SSHConfig(path=config_path)

    good = config.add_entry("goodhost")
    good.set("Port", "22")

    bad = config.add_entry("badhost")
    bad.set("Port", "99999")

    noport = config.add_entry("noport")
    noport.set("Hostname", "noport.example.com")

    errors = validate_ports(config)
    assert len(errors) == 1
    assert "badhost" in errors[0]


def test_multiple_invalid_ports(tmp_path: Path) -> None:
    """All entries with invalid ports each contribute one error."""
    config_path = tmp_path / "config"
    config = SSHConfig(path=config_path)

    for host, port in [("host1", "0"), ("host2", "65536"), ("host3", "abc")]:
        e = config.add_entry(host)
        e.set("Port", port)

    errors = validate_ports(config)
    assert len(errors) == 3
    hostnames_in_errors = " ".join(errors)
    assert "host1" in hostnames_in_errors
    assert "host2" in hostnames_in_errors
    assert "host3" in hostnames_in_errors
