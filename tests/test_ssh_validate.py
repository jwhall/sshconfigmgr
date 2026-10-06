"""Tests for validating a config with ``ssh -G``."""
from __future__ import annotations

import asyncio
import sys
import textwrap
from pathlib import Path

import pytest

from sshconfigmgr import ssh_validate
from sshconfigmgr.ssh_config import SSHConfig
from sshconfigmgr.ssh_validate import TEST_HOST, validate_with_ssh

needs_ssh = pytest.mark.skipif(ssh_validate.find_ssh() is None, reason="ssh not installed")


def fake_ssh(tmp_path: Path, body: str) -> list[str]:
    """A stand-in for ssh: a Python script run with this interpreter.
    It records its arguments and the config it was given to args.txt."""
    script = tmp_path / "fake_ssh.py"
    script.write_text(
        "import sys, pathlib\n"
        f"out = pathlib.Path({str(tmp_path)!r}) / 'args.txt'\n"
        "conf = sys.argv[sys.argv.index('-F') + 1]\n"
        "out.write_text('\\n'.join(sys.argv[1:]) + '\\n---\\n' + pathlib.Path(conf).read_text())\n"
        + textwrap.dedent(body)
    )
    return [sys.executable, str(script)]


def validate(config: SSHConfig, **kwargs) -> ssh_validate.ValidationResult:
    return asyncio.run(validate_with_ssh(config, **kwargs))


def test_passes_rendered_config_and_expected_arguments(tmp_path: Path) -> None:
    config = SSHConfig.from_text("Host a\n    User x\n", path=tmp_path / "config")
    config.entries[0].set("User", "unsaved-edit")
    result = validate(config, ssh_command=fake_ssh(tmp_path, "sys.exit(0)"))
    assert result.ok
    args, conf = (tmp_path / "args.txt").read_text().split("\n---\n")
    argv = args.splitlines()
    assert argv[:3] == ["-T", "-G", "-F"] and argv[4] == TEST_HOST
    # Validates what would be written, including edits not yet saved.
    assert conf == "Host a\n    User unsaved-edit\n"
    assert not Path(argv[3]).exists(), "temporary copy should be removed"


def test_failure_reports_errors_against_real_path(tmp_path: Path) -> None:
    config = SSHConfig.from_text("Host a\n", path=tmp_path / "config")
    body = """
        sys.stderr.write(f"{conf}: line 2: Bad configuration option: prot\\n")
        sys.exit(255)
    """
    result = validate(config, ssh_command=fake_ssh(tmp_path, body))
    assert not result.ok
    assert result.output == f"{tmp_path / 'config'}: line 2: Bad configuration option: prot"


def test_failure_without_output_reports_status(tmp_path: Path) -> None:
    config = SSHConfig.from_text("Host a\n", path=tmp_path / "config")
    result = validate(config, ssh_command=fake_ssh(tmp_path, "sys.exit(3)"))
    assert not result.ok
    assert result.output == "ssh exited with status 3."


def test_timeout(tmp_path: Path) -> None:
    config = SSHConfig.from_text("Host a\n", path=tmp_path / "config")
    result = validate(
        config, ssh_command=fake_ssh(tmp_path, "import time; time.sleep(30)"), timeout=1
    )
    assert not result.ok
    assert "did not finish within 1 seconds" in result.output


def test_unrunnable_ssh(tmp_path: Path) -> None:
    config = SSHConfig.from_text("Host a\n", path=tmp_path / "config")
    result = validate(config, ssh_command=[str(tmp_path / "no-such-ssh")])
    assert not result.ok
    assert result.output.startswith("Could not run ssh:")


def test_ssh_not_on_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ssh_validate, "find_ssh", lambda: None)
    result = validate(SSHConfig.from_text("Host a\n", path=tmp_path / "config"))
    assert not result.ok
    assert result.output == "ssh was not found on PATH."


# ─── Against the real ssh ─────────────────────────────────────────────────────


@needs_ssh
def test_real_ssh_accepts_valid_config(tmp_path: Path) -> None:
    config = SSHConfig.from_text(
        "Include does-not-matter\n\nHost web\n    HostName 10.0.0.1\n    Port=2222\n\n"
        "Host *\n    ServerAliveInterval 30\n",
        path=tmp_path / "config",
    )
    result = validate(config)
    assert result.ok, result.output


@needs_ssh
def test_real_ssh_rejects_bad_keyword_and_port(tmp_path: Path) -> None:
    config = SSHConfig.from_text(
        "Host web\n    Prot 22\n\nHost db\n    Port 99999\n", path=tmp_path / "config"
    )
    result = validate(config)
    assert not result.ok
    assert f"{tmp_path / 'config'}: line 2: Bad configuration option: prot" in result.output
    assert "line 5: Bad port '99999'" in result.output


def test_windows_escaped_temp_path_is_replaced() -> None:
    """Windows OpenSSH prints paths with doubled backslashes (seen in CI)."""
    from sshconfigmgr.ssh_validate import _report_real_path

    tmp = r"C:\Users\RUNNER~1\AppData\Local\Temp\sshconfigmgr-23be1p23.conf"
    escaped = tmp.replace("\\", "\\\\")
    output = (
        f"{escaped}: line 2: Bad configuration option: prot\n"
        f"{escaped}: terminating, 1 bad configuration options\n"
    )
    real = Path(r"C:\Users\me\.ssh\config")
    assert _report_real_path(output, tmp, real) == (
        f"{real}: line 2: Bad configuration option: prot\n"
        f"{real}: terminating, 1 bad configuration options\n"
    )


def test_plain_temp_path_is_replaced() -> None:
    from sshconfigmgr.ssh_validate import _report_real_path

    assert _report_real_path("/tmp/x.conf line 3: Bad port", "/tmp/x.conf", Path("/home/me/.ssh/config")) == (
        "/home/me/.ssh/config line 3: Bad port"
    )
