"""SSH client configuration parser and writer.

Preserves preamble comments and per-entry leading comments.
Writing back may lose inline/trailing comments on parameter lines.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class HostEntry:
    """One Host block in an SSH config file."""

    pattern: str
    params: list[tuple[str, str]] = field(default_factory=list)
    leading_comments: list[str] = field(default_factory=list)

    def get(self, key: str) -> Optional[str]:
        for k, v in self.params:
            if k.lower() == key.lower():
                return v
        return None

    def set(self, key: str, value: str) -> None:
        for i, (k, _) in enumerate(self.params):
            if k.lower() == key.lower():
                self.params[i] = (key, value)
                return
        self.params.append((key, value))

    def remove_key(self, key: str) -> None:
        self.params = [(k, v) for k, v in self.params if k.lower() != key.lower()]


@dataclass
class SSHConfig:
    """Parsed SSH client configuration."""

    path: Path
    entries: list[HostEntry] = field(default_factory=list)
    preamble: list[str] = field(default_factory=list)

    @classmethod
    def from_path(cls, path: Path) -> SSHConfig:
        config = cls(path=path)
        if not path.exists():
            return config

        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        pending: list[str] = []
        current: Optional[HostEntry] = None
        preamble_done = False

        for line in lines:
            stripped = line.strip()

            if not stripped or stripped.startswith("#"):
                pending.append(line)
                continue

            m = re.match(r"^Host\s+(.+)$", stripped, re.IGNORECASE)
            if m:
                if current is not None:
                    config.entries.append(current)
                elif not preamble_done:
                    config.preamble = list(pending)
                    pending = []
                    preamble_done = True

                current = HostEntry(
                    pattern=m.group(1).strip(),
                    leading_comments=list(pending),
                )
                pending = []
                continue

            if not preamble_done:
                # Non-Host, non-comment line before first Host (e.g. Include)
                config.preamble.extend(pending)
                pending = []
                config.preamble.append(line)
                continue

            m2 = re.match(r"^(\w[\w-]*)\s+(.*)", stripped)
            if m2 and current is not None:
                current.params.append((m2.group(1), m2.group(2).rstrip()))

        if current is not None:
            config.entries.append(current)
        elif pending:
            config.preamble.extend(pending)

        return config

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        parts: list[str] = list(self.preamble)
        for entry in self.entries:
            if parts:
                parts.append("")
            parts.extend(entry.leading_comments)
            parts.append(f"Host {entry.pattern}")
            for key, value in entry.params:
                parts.append(f"    {key} {value}")
        self.path.write_text("\n".join(parts) + "\n", encoding="utf-8")

    def add_entry(self, pattern: str) -> HostEntry:
        entry = HostEntry(pattern=pattern)
        self.entries.append(entry)
        return entry

    def remove_entry(self, entry: HostEntry) -> None:
        self.entries.remove(entry)
