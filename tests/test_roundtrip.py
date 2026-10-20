"""Lossless round-trip and edit-locality tests for SSHConfig."""
from __future__ import annotations

from pathlib import Path

import pytest

from sshconfigmgr.ssh_config import SSHConfig

# ─── Corpus: saving without edits must reproduce the file byte for byte ───────

CORPUS: dict[str, bytes] = {
    "empty": b"",
    "blank_only": b"\n\n\n",
    "simple": b"Host a\n    HostName 10.0.0.1\n    User x\n",
    "kitchen_sink": (
        b"# global\n"
        b"Include ~/.ssh/conf.d/*\n"
        b"\n"
        b"Host web\n"
        b"    HostName 10.0.0.1\n"
        b"    # jump via bastion\n"
        b"    ProxyJump bastion\n"
        b"    Port=2222\n"
        b"\n"
        b"Host=db\n"
        b"\tUser = admin\n"
        b"\n"
        b"Match host *.corp exec \"test -f /tmp/x\"\n"
        b"    User corpuser\n"
        b"    Include corp.conf\n"
        b"\n\n"
        b"Host *\n"
        b"    ServerAliveInterval 30\n"
        b"# trailing note\n"
    ),
    "crlf": b"Host a\r\n    User x\r\n\r\nHost b\r\n    User y\r\n",
    "mixed_eol": b"Host a\r\n    User x\n    Port 22\r\n",
    "no_final_newline": b"Host a\n    User x",
    "trailing_whitespace": b"Host a   \n    User x  \t\n  \n",
    "keyword_without_value": b"Host a\n    ForwardAgent\n    User x\n",
    "non_utf8": b"# caf\xe9\nHost a\n    User \xff\xfe\n",
    "bom": b"\xef\xbb\xbfHost a\n    User x\n",
    "indented_header": b"  Host a\n      User x\n",
}


@pytest.mark.parametrize("name", sorted(CORPUS))
def test_unmodified_save_is_byte_identical(tmp_config: Path, name: str) -> None:
    tmp_config.write_bytes(CORPUS[name])
    config = SSHConfig.from_path(tmp_config)
    config.save()
    assert tmp_config.read_bytes() == CORPUS[name]


@pytest.mark.parametrize("name", sorted(CORPUS))
def test_resyncing_identical_params_is_a_noop(tmp_config: Path, name: str) -> None:
    """The app writes params back on every keystroke; equal values must not
    dirty any line."""
    tmp_config.write_bytes(CORPUS[name])
    config = SSHConfig.from_path(tmp_config)
    for entry in config.entries:
        entry.params = list(entry.params)
    config.save()
    assert tmp_config.read_bytes() == CORPUS[name]


# ─── Parsing ──────────────────────────────────────────────────────────────────


def kitchen_sink() -> SSHConfig:
    return SSHConfig.from_text(CORPUS["kitchen_sink"].decode())


def test_equals_syntax_is_parsed() -> None:
    config = kitchen_sink()
    web, db, match, star = config.entries
    assert web.get("Port") == "2222"
    assert db.pattern == "db"
    assert db.params == [("User", "admin")]


def test_match_is_its_own_block() -> None:
    match = kitchen_sink().entries[2]
    assert match.kind == "Match"
    assert match.pattern == 'host *.corp exec "test -f /tmp/x"'
    assert match.params == [("User", "corpuser"), ("Include", "corp.conf")]


def test_comment_inside_block_stays_in_block() -> None:
    web = kitchen_sink().entries[0]
    assert web.leading_comments == []
    assert "    # jump via bastion" in [line.raw for line in web.body]


def test_trailing_comment_stays_with_last_block() -> None:
    star = kitchen_sink().entries[-1]
    assert star.body[-1].raw == "# trailing note"


# ─── Edits only touch what changed ────────────────────────────────────────────


def lines_of(config: SSHConfig) -> list[str]:
    return config.render().splitlines()


def test_value_edit_changes_only_that_line() -> None:
    config = kitchen_sink()
    before = lines_of(config)
    web = config.entries[0]
    web.params = [(k, "2200" if k == "Port" else v) for k, v in web.params]
    after = lines_of(config)
    changed = [(a, b) for a, b in zip(before, after) if a != b]
    assert changed == [("    Port=2222", "    Port=2200")]


def test_value_edit_keeps_spaced_equals_and_tab_indent() -> None:
    config = kitchen_sink()
    config.entries[1].set("User", "root")
    assert "\tUser = root" in lines_of(config)


def test_rename_keeps_header_separator() -> None:
    config = kitchen_sink()
    config.entries[1].pattern = "db db.internal"
    assert "Host=db db.internal" in lines_of(config)


def test_added_param_uses_block_style_and_follows_last_directive() -> None:
    config = SSHConfig.from_text("Host a\n\tUser=x\n\tPort=22\n# about b\nHost b\n")
    config.entries[0].set("IdentityFile", "~/.ssh/id_a")
    assert config.render() == (
        "Host a\n\tUser=x\n\tPort=22\n\tIdentityFile=~/.ssh/id_a\n# about b\nHost b\n"
    )


def test_added_param_in_empty_block_uses_default_style() -> None:
    config = SSHConfig.from_text("Host a\n")
    config.entries[0].set("User", "x")
    assert config.render() == "Host a\n    User x\n"


def test_removed_param_keeps_surrounding_comments() -> None:
    config = kitchen_sink()
    web = config.entries[0]
    web.remove_key("ProxyJump")
    text = config.render()
    assert "ProxyJump" not in text
    assert "    # jump via bastion\n    Port=2222\n" in text


def test_middle_insert_lands_in_order() -> None:
    config = SSHConfig.from_text("Host a\n    User x\n    Port 22\n")
    config.entries[0].params = [("User", "x"), ("ForwardAgent", "yes"), ("Port", "22")]
    assert config.render() == "Host a\n    User x\n    ForwardAgent yes\n    Port 22\n"


def test_new_entry_gets_one_blank_separator_and_newline_fix() -> None:
    config = SSHConfig.from_text("Host a\n    User x")
    entry = config.add_entry("b")
    entry.set("User", "y")
    assert config.render() == "Host a\n    User x\n\nHost b\n    User y\n"


def test_new_entry_uses_file_line_endings() -> None:
    config = SSHConfig.from_text("Host a\r\n    User x\r\n")
    config.add_entry("b").set("User", "y")
    assert config.render() == "Host a\r\n    User x\r\n\r\nHost b\r\n    User y\r\n"


def test_remove_entry_takes_its_leading_comments() -> None:
    config = SSHConfig.from_text(
        "Host a\n    User x\n\n# about b\nHost b\n    User y\n\nHost c\n    User z\n"
    )
    config.remove_entry(config.entries[1])
    assert config.render() == "Host a\n    User x\n\nHost c\n    User z\n"


def test_remove_last_entry_drops_dangling_separator() -> None:
    config = SSHConfig.from_text("Host a\n    User x\n\nHost b\n    User y\n")
    config.remove_entry(config.entries[1])
    assert config.render() == "Host a\n    User x\n"


def test_repeated_saves_do_not_accumulate_blank_lines(tmp_config: Path) -> None:
    tmp_config.write_bytes(CORPUS["kitchen_sink"])
    for _ in range(3):
        config = SSHConfig.from_path(tmp_config)
        config.entries[0].set("User", "u")
        config.save()
    text = tmp_config.read_text()
    assert "\n\n\n\n" not in text
    assert text.count("User u") == 1


# ─── is_modified ──────────────────────────────────────────────────────────────


@pytest.mark.parametrize("name", sorted(CORPUS))
def test_freshly_loaded_config_is_not_modified(tmp_config: Path, name: str) -> None:
    tmp_config.write_bytes(CORPUS[name])
    assert not SSHConfig.from_path(tmp_config).is_modified()


def test_new_empty_config_is_not_modified(tmp_config: Path) -> None:
    assert not SSHConfig.from_path(tmp_config).is_modified()


def test_edit_then_revert_is_not_modified() -> None:
    config = kitchen_sink()
    config.entries[0].set("Port", "2200")
    assert config.is_modified()
    config.entries[0].set("Port", "2222")
    assert not config.is_modified()


def test_structural_changes_are_modified() -> None:
    config = kitchen_sink()
    config.remove_entry(config.entries[1])
    assert config.is_modified()
    config = kitchen_sink()
    config.add_entry("new")
    assert config.is_modified()


def test_save_clears_modified(tmp_config: Path) -> None:
    tmp_config.write_bytes(CORPUS["simple"])
    config = SSHConfig.from_path(tmp_config)
    config.entries[0].set("User", "y")
    config.save()
    assert not config.is_modified()
