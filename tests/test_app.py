"""Headless UI tests for leaving a file with unsaved changes (quit / open)."""
from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Awaitable, Callable

from textual.pilot import Pilot
from textual.widgets import Input

from sshconfigmgr.app import (
    ConfirmScreen,
    InputScreen,
    ParamRow,
    SSHConfigApp,
    UnsavedChangesScreen,
)
from sshconfigmgr.ssh_config import SSHConfig

ORIGINAL = "Host a\n    Port 22\n"
OTHER = "Host other\n    User o\n"


def run(path: Path, script: Callable[[SSHConfigApp, Pilot], Awaitable[None]]) -> SSHConfigApp:
    app = SSHConfigApp(path.resolve())

    async def main() -> None:
        async with app.run_test() as pilot:
            await pilot.pause()
            await script(app, pilot)

    asyncio.run(main())
    return app


async def set_port(app: SSHConfigApp, pilot: Pilot, value: str) -> None:
    app.query(ParamRow).first().query_one(".param-val", Input).value = value
    await pilot.pause()
    assert app._modified


async def choose(pilot: Pilot, button_id: str) -> None:
    await pilot.click(f"#{button_id}")
    await pilot.pause()


async def open_path(app: SSHConfigApp, pilot: Pilot, path: Path) -> None:
    app.action_open_file()
    await pilot.pause()
    assert isinstance(app.screen, InputScreen)
    app.screen.query_one("#dialog-input", Input).value = str(path)
    await choose(pilot, "ok")


# ─── Quit ─────────────────────────────────────────────────────────────────────


def test_save_and_quit_with_validation_error_does_not_quit(tmp_config: Path) -> None:
    tmp_config.write_text(ORIGINAL)

    async def script(app: SSHConfigApp, pilot: Pilot) -> None:
        await set_port(app, pilot, "99999")
        app.action_request_quit()
        await pilot.pause()
        assert isinstance(app.screen, UnsavedChangesScreen)
        await choose(pilot, "save")
        assert app.is_running
        assert app._modified

    run(tmp_config, script)
    assert tmp_config.read_text() == ORIGINAL


def test_save_and_quit_saves_then_quits(tmp_config: Path) -> None:
    tmp_config.write_text(ORIGINAL)

    async def script(app: SSHConfigApp, pilot: Pilot) -> None:
        await set_port(app, pilot, "2222")
        app.action_request_quit()
        await pilot.pause()
        await choose(pilot, "save")
        assert not app.is_running

    run(tmp_config, script)
    assert tmp_config.read_text() == "Host a\n    Port 2222\n"


def test_save_and_quit_declining_overwrite_does_not_quit(tmp_config: Path) -> None:
    tmp_config.write_text(ORIGINAL)

    async def script(app: SSHConfigApp, pilot: Pilot) -> None:
        await set_port(app, pilot, "2222")
        tmp_config.write_text(OTHER)
        os.utime(tmp_config, ns=(0, 0))
        app.action_request_quit()
        await pilot.pause()
        await choose(pilot, "save")
        assert isinstance(app.screen, ConfirmScreen)
        await choose(pilot, "cancel")
        assert app.is_running
        assert app._modified

    run(tmp_config, script)
    assert tmp_config.read_text() == OTHER


def test_save_and_quit_accepting_overwrite_quits(tmp_config: Path) -> None:
    tmp_config.write_text(ORIGINAL)

    async def script(app: SSHConfigApp, pilot: Pilot) -> None:
        await set_port(app, pilot, "2222")
        tmp_config.write_text(OTHER)
        os.utime(tmp_config, ns=(0, 0))
        app.action_request_quit()
        await pilot.pause()
        await choose(pilot, "save")
        await choose(pilot, "ok")
        assert not app.is_running

    run(tmp_config, script)
    assert tmp_config.read_text() == "Host a\n    Port 2222\n"


def test_discard_and_quit_leaves_file_untouched(tmp_config: Path) -> None:
    tmp_config.write_text(ORIGINAL)

    async def script(app: SSHConfigApp, pilot: Pilot) -> None:
        await set_port(app, pilot, "2222")
        app.action_request_quit()
        await pilot.pause()
        await choose(pilot, "discard")
        assert not app.is_running

    run(tmp_config, script)
    assert tmp_config.read_text() == ORIGINAL


def test_cancel_quit_keeps_editing(tmp_config: Path) -> None:
    tmp_config.write_text(ORIGINAL)

    async def script(app: SSHConfigApp, pilot: Pilot) -> None:
        await set_port(app, pilot, "2222")
        app.action_request_quit()
        await pilot.pause()
        await choose(pilot, "cancel")
        assert app.is_running
        assert app._modified

    run(tmp_config, script)


# ─── Open ─────────────────────────────────────────────────────────────────────


def test_open_without_changes_loads_directly(tmp_config: Path, tmp_path: Path) -> None:
    tmp_config.write_text(ORIGINAL)
    other = tmp_path / "other"
    other.write_text(OTHER)

    async def script(app: SSHConfigApp, pilot: Pilot) -> None:
        await open_path(app, pilot, other)
        assert app._config_path == other.resolve()

    run(tmp_config, script)


def test_open_with_changes_prompts_and_cancel_keeps_edits(tmp_config: Path, tmp_path: Path) -> None:
    tmp_config.write_text(ORIGINAL)
    other = tmp_path / "other"
    other.write_text(OTHER)

    async def script(app: SSHConfigApp, pilot: Pilot) -> None:
        await set_port(app, pilot, "2222")
        await open_path(app, pilot, other)
        assert isinstance(app.screen, UnsavedChangesScreen)
        await choose(pilot, "cancel")
        assert app._config_path == tmp_config.resolve()
        assert app._modified
        assert app._config.entries[0].get("Port") == "2222"

    run(tmp_config, script)
    assert tmp_config.read_text() == ORIGINAL


def test_open_with_changes_discard_loads_new_file(tmp_config: Path, tmp_path: Path) -> None:
    tmp_config.write_text(ORIGINAL)
    other = tmp_path / "other"
    other.write_text(OTHER)

    async def script(app: SSHConfigApp, pilot: Pilot) -> None:
        await set_port(app, pilot, "2222")
        await open_path(app, pilot, other)
        await choose(pilot, "discard")
        assert app._config_path == other.resolve()
        assert not app._modified

    run(tmp_config, script)
    assert tmp_config.read_text() == ORIGINAL


def test_open_with_changes_save_writes_then_loads(tmp_config: Path, tmp_path: Path) -> None:
    tmp_config.write_text(ORIGINAL)
    other = tmp_path / "other"
    other.write_text(OTHER)

    async def script(app: SSHConfigApp, pilot: Pilot) -> None:
        await set_port(app, pilot, "2222")
        await open_path(app, pilot, other)
        await choose(pilot, "save")
        assert app._config_path == other.resolve()

    run(tmp_config, script)
    assert tmp_config.read_text() == "Host a\n    Port 2222\n"


def test_open_with_invalid_changes_save_stays_on_file(tmp_config: Path, tmp_path: Path) -> None:
    tmp_config.write_text(ORIGINAL)
    other = tmp_path / "other"
    other.write_text(OTHER)

    async def script(app: SSHConfigApp, pilot: Pilot) -> None:
        await set_port(app, pilot, "0")
        await open_path(app, pilot, other)
        await choose(pilot, "save")
        assert app._config_path == tmp_config.resolve()
        assert app._modified

    run(tmp_config, script)
    assert tmp_config.read_text() == ORIGINAL


def test_open_new_file_with_changes_prompts_after_create(tmp_config: Path, tmp_path: Path) -> None:
    tmp_config.write_text(ORIGINAL)
    missing = tmp_path / "missing"

    async def script(app: SSHConfigApp, pilot: Pilot) -> None:
        await set_port(app, pilot, "2222")
        await open_path(app, pilot, missing)
        assert isinstance(app.screen, ConfirmScreen)  # "Create …?"
        await choose(pilot, "ok")
        assert isinstance(app.screen, UnsavedChangesScreen)
        await choose(pilot, "discard")
        assert app._config_path == missing.resolve()

    run(tmp_config, script)


# ─── Unsaved flag ─────────────────────────────────────────────────────────────

MULTI = "Host a\n    User x\n    Port 22\n\nHost b\n    User y\n\nHost c\n    User z\n    Port 2\n"


def test_startup_and_navigation_do_not_set_modified(tmp_config: Path) -> None:
    tmp_config.write_text(MULTI)

    async def script(app: SSHConfigApp, pilot: Pilot) -> None:
        await pilot.pause()
        assert not app._modified
        for key in "jjkjj":
            await pilot.press(key)
            await pilot.pause()
            assert not app._modified, f"modified after pressing {key}"
        assert "(unsaved)" not in app.sub_title

    run(tmp_config, script)


def test_edit_then_revert_clears_modified(tmp_config: Path) -> None:
    tmp_config.write_text(ORIGINAL)

    async def script(app: SSHConfigApp, pilot: Pilot) -> None:
        await set_port(app, pilot, "2222")
        assert "(unsaved)" in app.sub_title
        await set_port_unchecked(app, pilot, "22")
        assert not app._modified
        assert "(unsaved)" not in app.sub_title

    run(tmp_config, script)


async def set_port_unchecked(app: SSHConfigApp, pilot: Pilot, value: str) -> None:
    app.query(ParamRow).first().query_one(".param-val", Input).value = value
    await pilot.pause()


def test_deleting_a_field_sets_modified_and_updates_model(tmp_config: Path) -> None:
    tmp_config.write_text(MULTI)

    async def script(app: SSHConfigApp, pilot: Pilot) -> None:
        row = app.query(ParamRow).last()
        row.post_message(ParamRow.DeleteRequested(row))
        await pilot.pause()
        assert app._modified
        assert app._config.entries[0].params == [("User", "x")]

    run(tmp_config, script)


def test_adding_a_field_sets_modified(tmp_config: Path) -> None:
    tmp_config.write_text(MULTI)

    async def script(app: SSHConfigApp, pilot: Pilot) -> None:
        app._do_add_field()
        await pilot.pause()
        await pilot.press(*"ForwardAgent", "enter")
        await pilot.pause()
        assert app._modified
        await pilot.press(*"yes")
        await pilot.pause()
        assert app._config.entries[0].get("ForwardAgent") == "yes"

    run(tmp_config, script)


def test_host_level_edits_set_modified(tmp_config: Path) -> None:
    tmp_config.write_text(MULTI)

    async def script(app: SSHConfigApp, pilot: Pilot) -> None:
        app.action_delete_host()
        await pilot.pause()
        await choose(pilot, "ok")
        assert app._modified

    run(tmp_config, script)


# ─── Host list and editor ─────────────────────────────────────────────────────

# Hosts with different numbers of params, so the editor has to grow and
# shrink its rows while navigating.
VARIED = (
    "Host zero\n"
    "\nHost three\n    User u3\n    Port 3\n    ForwardAgent yes\n"
    "\nHost one\n    User u1\n"
    "\nHost five\n" + "".join(f"    SetEnv K{i}=v{i}\n" for i in range(5))
    + "\nHost two\n    User u2\n    Port 2\n"
)


def shown_params(app: SSHConfigApp) -> list[tuple[str, str]]:
    """What the editor actually displays, read from the Input widgets."""
    shown = []
    for row in app.query(ParamRow):
        key, val = row.query(Input)
        shown.append((key.value, val.value))
    return shown


def host_list_labels(app: SSHConfigApp) -> list[str]:
    from sshconfigmgr.app import HostList

    host_list = app.query_one(HostList)
    return [str(host_list.get_option_at_index(i).prompt) for i in range(host_list.option_count)]


def test_editor_shows_each_entry_while_navigating(tmp_config: Path) -> None:
    tmp_config.write_text(VARIED)

    async def script(app: SSHConfigApp, pilot: Pilot) -> None:
        for expected in (1, 2, 3, 4, 3, 2, 1, 0):
            key = "j" if expected > app._config.entries.index(app._current_entry) else "k"
            await pilot.press(key)
            await pilot.pause()
            entry = app._config.entries[expected]
            assert app._current_entry is entry
            assert shown_params(app) == entry.params, entry.pattern

    run(tmp_config, script)


def test_editor_consistent_after_key_burst(tmp_config: Path) -> None:
    tmp_config.write_text(VARIED)

    async def script(app: SSHConfigApp, pilot: Pilot) -> None:
        await pilot.press(*"jjjjkjjkkj")  # no pause between keys
        await pilot.pause()
        entry = app._config.entries[3]
        assert app._current_entry is entry
        assert shown_params(app) == entry.params
        assert not app._modified

    run(tmp_config, script)


def test_edit_after_navigation_goes_to_the_right_entry(tmp_config: Path) -> None:
    tmp_config.write_text(VARIED)

    async def script(app: SSHConfigApp, pilot: Pilot) -> None:
        for _ in range(3):  # zero -> three -> one -> five (rows reused)
            await pilot.press("j")
            await pilot.pause()
        app.query(ParamRow).first().query(Input).last().value = "changed"
        await pilot.pause()
        five, others = app._config.entries[3], app._config.entries[:3]
        assert five.get("SetEnv") == "changed"
        original = SSHConfig.from_path(tmp_config).entries[:3]
        assert [e.params for e in others] == [e.params for e in original]

    run(tmp_config, script)


def test_match_labels_are_not_parsed_as_markup(tmp_config: Path) -> None:
    tmp_config.write_text('Host a\n\nMatch exec "[ -f /tmp/[bold]x ]"\n    User m\n')

    async def script(app: SSHConfigApp, pilot: Pilot) -> None:
        assert host_list_labels(app) == ["a", 'Match exec "[ -f /tmp/[bold]x ]"']

    run(tmp_config, script)


def test_rename_updates_list_label(tmp_config: Path) -> None:
    tmp_config.write_text(VARIED)

    async def script(app: SSHConfigApp, pilot: Pilot) -> None:
        await pilot.press("j")
        await pilot.pause()
        app.action_edit_host()
        await pilot.pause()
        app.screen.query_one("#dialog-input", Input).value = "three tres"
        await choose(pilot, "ok")
        assert host_list_labels(app)[1] == "three tres"
        assert app._current_entry is app._config.entries[1]

    run(tmp_config, script)


def test_delete_selects_the_next_host(tmp_config: Path) -> None:
    tmp_config.write_text(VARIED)

    async def script(app: SSHConfigApp, pilot: Pilot) -> None:
        await pilot.press("j", "j")
        await pilot.pause()
        app.action_delete_host()
        await pilot.pause()
        await choose(pilot, "ok")
        assert host_list_labels(app) == ["zero", "three", "five", "two"]
        assert app._current_entry.pattern == "five"
        assert shown_params(app) == app._current_entry.params

    run(tmp_config, script)


def test_delete_last_host_selects_new_last(tmp_config: Path) -> None:
    tmp_config.write_text(VARIED)

    async def script(app: SSHConfigApp, pilot: Pilot) -> None:
        await pilot.press("end")
        await pilot.pause()
        app.action_delete_host()
        await pilot.pause()
        await choose(pilot, "ok")
        assert app._current_entry.pattern == "five"

    run(tmp_config, script)


def test_new_host_is_selected(tmp_config: Path) -> None:
    tmp_config.write_text(VARIED)

    async def script(app: SSHConfigApp, pilot: Pilot) -> None:
        app.action_new_host()
        await pilot.pause()
        app.screen.query_one("#dialog-input", Input).value = "fresh"
        await choose(pilot, "ok")
        assert host_list_labels(app)[-1] == "fresh"
        assert app._current_entry.pattern == "fresh"
        assert shown_params(app) == []

    run(tmp_config, script)


def test_open_shows_first_entry_of_new_file(tmp_config: Path, tmp_path: Path) -> None:
    tmp_config.write_text(VARIED)
    other = tmp_path / "other"
    other.write_text("Host o1\n    User x\n\nHost o2\n")

    async def script(app: SSHConfigApp, pilot: Pilot) -> None:
        await open_path(app, pilot, other)
        assert host_list_labels(app) == ["o1", "o2"]
        assert app._current_entry.pattern == "o1"
        assert shown_params(app) == [("User", "x")]

    run(tmp_config, script)


def test_cursor_stops_at_list_ends(tmp_config: Path) -> None:
    tmp_config.write_text(VARIED)

    async def script(app: SSHConfigApp, pilot: Pilot) -> None:
        await pilot.press("k")
        await pilot.pause()
        assert app._current_entry.pattern == "zero"
        await pilot.press("end", "j", "down")
        await pilot.pause()
        assert app._current_entry.pattern == "two"

    run(tmp_config, script)
