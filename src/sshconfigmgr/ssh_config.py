"""SSH client configuration parser and writer.

The parser is lossless: every line of the file (comments, blank lines,
unrecognised syntax, indentation, ``Key=Value`` separators, line endings) is
kept verbatim, and saving an unmodified config reproduces the file byte for
byte.  Only lines that were actually edited are re-rendered, using the
indentation and separator style already present in their block.

Saving is atomic: the new content is written to a temporary file in the same
directory, fsynced, given the original file's permissions, then renamed over
the original.
"""
from __future__ import annotations

import os
import re
import stat
import tempfile
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path
from typing import Iterable, Optional

_BLOCK_KEYWORDS = {"host", "match"}

# Keyword, then whitespace and/or a single '=', then the value (ssh_config(5)).
_DIRECTIVE_RE = re.compile(
    r"^(?P<indent>\s*)(?P<key>[A-Za-z0-9_-]+)(?P<sep>\s*=\s*|\s+)(?P<value>.*?)\s*$"
)
_EOL_RE = re.compile(r"\r\n|\n|\r")

_DEFAULT_INDENT = "    "
_DEFAULT_SEP = " "


class ConfigChangedError(Exception):
    """The file on disk changed after it was loaded; saving would clobber it."""


class Line:
    """One physical line of the config file."""

    __slots__ = ("raw", "eol", "kind", "indent", "keyword", "sep", "value", "dirty")

    def __init__(self, raw: str, eol: Optional[str]) -> None:
        self.raw = raw
        # None means "not from the file": use the config's dominant line ending.
        self.eol = eol
        self.dirty = False
        self.indent = ""
        self.keyword = ""
        self.sep = ""
        self.value = ""
        stripped = raw.strip()
        if not stripped:
            self.kind = "blank"
        elif stripped.startswith("#"):
            self.kind = "comment"
        else:
            m = _DIRECTIVE_RE.match(raw)
            if m:
                self.kind = "directive"
                self.indent = m.group("indent")
                self.keyword = m.group("key")
                self.sep = m.group("sep")
                self.value = m.group("value")
            else:
                # Keyword with no value, or syntax we don't understand.  Kept
                # verbatim and never shown as an editable parameter.
                self.kind = "other"

    @classmethod
    def new_directive(cls, indent: str, keyword: str, sep: str, value: str) -> Line:
        line = cls("", None)
        line.kind = "directive"
        line.indent, line.keyword, line.sep = indent, keyword, sep
        line.set(keyword, value)
        line.dirty = True
        return line

    @classmethod
    def blank(cls) -> Line:
        return cls("", None)

    @property
    def is_block_header(self) -> bool:
        return self.kind == "directive" and self.keyword.lower() in _BLOCK_KEYWORDS

    def set(self, keyword: str, value: str) -> None:
        if keyword != self.keyword or value != self.value:
            self.keyword, self.value = keyword, value
            self.dirty = True

    @property
    def text(self) -> str:
        if not self.dirty:
            return self.raw
        if not self.value:
            return f"{self.indent}{self.keyword}"
        return f"{self.indent}{self.keyword}{self.sep}{self.value}"


def _split_lines(text: str) -> list[Line]:
    lines: list[Line] = []
    pos = 0
    for m in _EOL_RE.finditer(text):
        lines.append(Line(text[pos:m.start()], m.group()))
        pos = m.end()
    if pos < len(text):
        lines.append(Line(text[pos:], ""))
    return lines


def _most_common(values: Iterable[str], default: str) -> str:
    counts = Counter(values)
    return counts.most_common(1)[0][0] if counts else default


class HostEntry:
    """One ``Host`` or ``Match`` block.

    ``leading`` holds the comment lines directly above the header (no blank
    line between); they belong to this block and are removed with it.
    ``body`` holds every line after the header up to the next block's
    leading comments, including blank lines and comments.
    """

    def __init__(
        self,
        pattern: str = "",
        params: Optional[list[tuple[str, str]]] = None,
        kind: str = "Host",
    ) -> None:
        self.header = Line.new_directive("", kind, _DEFAULT_SEP, pattern)
        self.leading: list[Line] = []
        self.body: list[Line] = []
        if params:
            self.params = params

    @classmethod
    def _from_lines(cls, header: Line, leading: list[Line]) -> HostEntry:
        entry = cls.__new__(cls)
        entry.header = header
        entry.leading = leading
        entry.body = []
        return entry

    @property
    def kind(self) -> str:
        return "Match" if self.header.keyword.lower() == "match" else "Host"

    @property
    def pattern(self) -> str:
        return self.header.value

    @pattern.setter
    def pattern(self, value: str) -> None:
        self.header.set(self.header.keyword, value)

    @property
    def leading_comments(self) -> list[str]:
        return [line.raw for line in self.leading]

    def lines(self) -> list[Line]:
        return [*self.leading, self.header, *self.body]

    def _directives(self) -> list[Line]:
        return [line for line in self.body if line.kind == "directive"]

    @property
    def params(self) -> list[tuple[str, str]]:
        return [(line.keyword, line.value) for line in self._directives()]

    @params.setter
    def params(self, new: list[tuple[str, str]]) -> None:
        """Reconcile the block with *new*, touching only lines that differ.

        Unchanged directives keep their original text; changed ones keep their
        indentation and separator; removed ones are dropped; added ones are
        inserted after their nearest surviving predecessor.  Comments, blank
        lines and unparsed lines are never removed.
        """
        old = self._directives()
        old_keys = [(line.keyword.lower(), line.value) for line in old]
        new_keys = [(k.lower(), v) for k, v in new]
        indent = _most_common((line.indent for line in old), _DEFAULT_INDENT)
        sep = _most_common((line.sep for line in old), _DEFAULT_SEP)

        deleted: set[int] = set()
        after: dict[int, list[Line]] = {}  # old index -> lines inserted after it
        matcher = SequenceMatcher(None, old_keys, new_keys, autojunk=False)
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "equal":
                # Values match case-insensitively on the key; carry key casing.
                for n in range(i2 - i1):
                    old[i1 + n].set(new[j1 + n][0], new[j1 + n][1])
                continue
            paired = min(i2 - i1, j2 - j1)
            for n in range(paired):
                old[i1 + n].set(*new[j1 + n])
            deleted.update(range(i1 + paired, i2))
            extra = [Line.new_directive(indent, k, sep, v) for k, v in new[j1 + paired:j2]]
            if extra:
                after.setdefault(i1 + paired - 1, []).extend(extra)

        if not deleted and not after:
            return

        body: list[Line] = []
        before_first = after.pop(-1, [])
        index = {id(line): i for i, line in enumerate(old)}
        for line in self.body:
            i = index.get(id(line))
            if i is None:
                body.append(line)
                continue
            if i == 0:
                body.extend(before_first)
                before_first = []
            if i not in deleted:
                body.append(line)
            body.extend(after.get(i, []))
        # No existing directives: append after the header's other content.
        body.extend(before_first)
        self.body = body

    def get(self, key: str) -> Optional[str]:
        for k, v in self.params:
            if k.lower() == key.lower():
                return v
        return None

    def set(self, key: str, value: str) -> None:
        params = self.params
        for i, (k, _) in enumerate(params):
            if k.lower() == key.lower():
                params[i] = (key, value)
                break
        else:
            params.append((key, value))
        self.params = params

    def remove_key(self, key: str) -> None:
        self.params = [(k, v) for k, v in self.params if k.lower() != key.lower()]


def _disk_stamp(path: Path) -> Optional[tuple[int, int]]:
    try:
        st = path.stat()
    except FileNotFoundError:
        return None
    return (st.st_mtime_ns, st.st_size)


def _fsync_dir(directory: Path) -> None:
    if os.name != "posix":
        return
    try:
        fd = os.open(directory, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)


class SSHConfig:
    """Parsed SSH client configuration.

    ``preamble_lines`` holds everything before the first block (global
    directives such as ``Include``, comments, blank lines).
    """

    def __init__(self, path: Path, entries: Optional[list[HostEntry]] = None) -> None:
        self.path = path
        self.entries: list[HostEntry] = entries if entries is not None else []
        self.preamble_lines: list[Line] = []
        self.newline = "\n"
        # Disk state at load time; None means the file did not exist.
        self._stamp: Optional[tuple[int, int]] = None

    @property
    def preamble(self) -> list[str]:
        return [line.raw for line in self.preamble_lines]

    @classmethod
    def from_path(cls, path: Path) -> SSHConfig:
        config = cls(path=path)
        if not path.exists():
            return config

        data = path.read_bytes()
        config._stamp = _disk_stamp(path)
        # surrogateescape keeps non-UTF-8 bytes intact through a save.
        config.parse(data.decode("utf-8", errors="surrogateescape"))
        return config

    @classmethod
    def from_text(cls, text: str, path: Path = Path("config")) -> SSHConfig:
        config = cls(path=path)
        config.parse(text)
        return config

    def parse(self, text: str) -> None:
        lines = _split_lines(text)
        self.newline = _most_common((l.eol for l in lines if l.eol), "\n")
        self.entries = []
        target = self.preamble_lines = []
        for line in lines:
            if not line.is_block_header:
                target.append(line)
                continue
            leading: list[Line] = []
            while target and target[-1].kind == "comment":
                leading.insert(0, target.pop())
            entry = HostEntry._from_lines(line, leading)
            self.entries.append(entry)
            target = entry.body

    def lines(self) -> list[Line]:
        out = list(self.preamble_lines)
        for entry in self.entries:
            out.extend(entry.lines())
        return out

    def render(self) -> str:
        lines = self.lines()
        parts: list[str] = []
        last = len(lines) - 1
        for i, line in enumerate(lines):
            eol = line.eol
            # A line that had no newline (end of file) needs one once
            # something follows it; new lines use the file's dominant ending.
            if eol is None or (eol == "" and i < last):
                eol = self.newline
            parts.append(line.text + eol)
        return "".join(parts)

    def _last_container(self) -> list[Line]:
        return self.entries[-1].body if self.entries else self.preamble_lines

    def add_entry(self, pattern: str) -> HostEntry:
        lines = self.lines()
        if lines and lines[-1].kind != "blank":
            self._last_container().append(Line.blank())
        entry = HostEntry(pattern=pattern)
        self.entries.append(entry)
        return entry

    def remove_entry(self, entry: HostEntry) -> None:
        was_last = self.entries and self.entries[-1] is entry
        self.entries.remove(entry)
        if was_last:
            # Drop the separator that preceded the removed block.
            container = self._last_container()
            while container and container[-1].kind == "blank":
                container.pop()

    def changed_on_disk(self) -> bool:
        return _disk_stamp(self._target()) != self._stamp

    def _target(self) -> Path:
        # Write through symlinks (e.g. dotfile managers) rather than replacing
        # the link with a regular file.
        return self.path.resolve()

    def save(self, *, force: bool = False) -> None:
        """Atomically write the config to disk.

        Raises ConfigChangedError if the file was modified (or created) since
        it was loaded, unless *force* is true.
        """
        target = self._target()
        if not force and _disk_stamp(target) != self._stamp:
            raise ConfigChangedError(f"{target} changed on disk since it was loaded")

        data = self.render().encode("utf-8", errors="surrogateescape")
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        try:
            st: Optional[os.stat_result] = target.stat()
        except FileNotFoundError:
            st = None

        fd, tmp = tempfile.mkstemp(dir=target.parent, prefix=f".{target.name}.", suffix=".tmp")
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(data)
                f.flush()
                os.fsync(f.fileno())
            os.chmod(tmp, stat.S_IMODE(st.st_mode) if st else 0o600)
            if st is not None and hasattr(os, "chown"):
                try:
                    os.chown(tmp, st.st_uid, st.st_gid)
                except PermissionError:
                    pass
            os.replace(tmp, target)
        except BaseException:
            try:
                os.unlink(tmp)
            except FileNotFoundError:
                pass
            raise
        _fsync_dir(target.parent)

        for line in self.lines():
            if line.dirty:
                line.raw, line.dirty = line.text, False
        self._stamp = _disk_stamp(target)
