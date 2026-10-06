"""Validate a config by having OpenSSH parse it (``ssh -G``).

``ssh -G -F <file> <host>`` parses the whole file, evaluates the Host and
Match blocks for *host*, prints the resulting settings and exits without
connecting.  It exits non-zero with ``<file>: line N: ...`` messages on
stderr for unknown keywords, missing arguments and many malformed values.

Caveats (inherent to ``ssh -G``):
- Some values are only checked in blocks that apply to the test host.
- ``Match exec`` commands are executed while evaluating Match blocks.
"""
from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from typing import Optional, Sequence

from sshconfigmgr.ssh_config import SSHConfig

# A name in the reserved .invalid TLD (RFC 2606), so only wildcard blocks
# such as "Host *" apply to it.
TEST_HOST = "sshconfigmgr-validate.invalid"
TIMEOUT_SECONDS = 10.0


@dataclass
class ValidationResult:
    ok: bool
    output: str


def find_ssh() -> Optional[str]:
    return shutil.which("ssh")


async def validate_with_ssh(
    config: SSHConfig,
    ssh_command: Optional[Sequence[str]] = None,
    timeout: float = TIMEOUT_SECONDS,
) -> ValidationResult:
    """Run ``ssh -G`` against the config as it would be written.

    *ssh_command* is the program to run (default: ``ssh`` from PATH); the
    ``-T -G -F <file> <host>`` arguments are appended to it.
    """
    if ssh_command is None:
        ssh = find_ssh()
        if ssh is None:
            return ValidationResult(False, "ssh was not found on PATH.")
        ssh_command = [ssh]

    data = config.render().encode("utf-8", errors="surrogateescape")
    fd, tmp = tempfile.mkstemp(prefix="sshconfigmgr-", suffix=".conf")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        try:
            proc = await asyncio.create_subprocess_exec(
                *ssh_command, "-T", "-G", "-F", tmp, TEST_HOST,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
        except OSError as exc:
            return ValidationResult(False, f"Could not run ssh: {exc}")
        try:
            _, stderr = await asyncio.wait_for(proc.communicate(), timeout)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            return ValidationResult(
                False,
                f"ssh did not finish within {timeout:g} seconds. "
                "A Match exec command in the config may be hanging.",
            )
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass

    # Report errors against the real file name, not the temporary copy.
    output = stderr.decode("utf-8", errors="replace").replace(tmp, str(config.path)).strip()
    if proc.returncode == 0:
        return ValidationResult(True, output)
    return ValidationResult(False, output or f"ssh exited with status {proc.returncode}.")
