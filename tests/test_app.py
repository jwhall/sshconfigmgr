"""Headless UI tests for leaving a file with unsaved changes (quit / open)."""
from __future__ import annotations

import asyncio
import os
from pathlib import Path
from time import monotonic
from typing import Awaitable, Callable

import pytest

from textual.pilot import Pilot
from textual.message import Message
from textual.message_pump import MessagePump
from textual.widgets import Input

from sshconfigmgr.app import (
    ConfirmScreen,
    InputScreen,
    ParamRow,
    SSHConfigApp,
    UnsavedChangesScreen,
)
from sshconfigmgr.ssh_config import SSHConfig
from sshconfigmgr import ssh_validate


@pytest.fixture(autouse=True)
def no_ssh(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tests don't depend on whether ssh is installed; validation tests
    opt in with the fake_validation fixture."""
    monkeypatch.setattr(ssh_validate, "find_ssh", lambda: None)

ORIGINAL = "Host a\n    Port 22\n"
OTHER = "Host other\n    User o\n"


# Messages currently being handled, across all message pumps; maintained by
# the track_dispatch fixture and read by settle().
_IN_FLIGHT = [0]


@pytest.fixture(autouse=True)
def track_dispatch(monkeypatch: pytest.MonkeyPatch) -> None:
    original = MessagePump._dispatch_message

    async def tracked(self: MessagePump, message: Message) -> object:
        _IN_FLIGHT[0] += 1
        try:
            return await original(self, message)
        finally:
            _IN_FLIGHT[0] -= 1

    monkeypatch.setattr(MessagePump, "_dispatch_message", tracked)


async def settle(pilot: Pilot, timeout: float = 10.0) -> None:
    """Wait until the app has finished processing everything in flight.

    Pilot.pause() decides the app is idle from CPU time, so on slow or
    coarse-timer runners (Windows CI) it can return while messages are still
    queued or being handled.  This waits until no message is being handled,
    every message queue in the app is empty, and any workers have finished,
    on two consecutive checks.
    """
    app = pilot.app
    deadline = monotonic() + timeout
    quiet = 0
    while quiet < 2 and app.is_running:
        await pilot.pause()
        await app.workers.wait_for_complete()
        pumps = [app]
        for screen in app.screen_stack:
            pumps.extend(screen.walk_children(with_self=True))
        busy = _IN_FLIGHT[0] > 0 or any(not pump._message_queue.empty() for pump in pumps)
        quiet = 0 if busy else quiet + 1
        assert monotonic() < deadline, "app did not settle"


def run(path: Path, script: Callable[[SSHConfigApp, Pilot], Awaitable[None]]) -> SSHConfigApp:
    app = SSHConfigApp(path.resolve())

    async def main() -> None:
        async with app.run_test() as pilot:
            await settle(pilot)
            await script(app, pilot)

    asyncio.run(main())
    return app


async def set_port(app: SSHConfigApp, pilot: Pilot, value: str) -> None:
    app.query(ParamRow).first().query_one(".param-val", Input).value = value
    await settle(pilot)
    assert app._modified


async def choose(pilot: Pilot, button_id: str) -> None:
    await pilot.click(f"#{button_id}")
    await settle(pilot)


async def open_path(app: SSHConfigApp, pilot: Pilot, path: Path) -> None:
    app.action_open_file()
    await settle(pilot)
    assert isinstance(app.screen, InputScreen)
    app.screen.query_one("#dialog-input", Input).value = str(path)
    await choose(pilot, "ok")


# ─── Quit ─────────────────────────────────────────────────────────────────────


def test_save_and_quit_with_validation_error_does_not_quit(tmp_config: Path) -> None:
    tmp_config.write_text(ORIGINAL)

    async def script(app: SSHConfigApp, pilot: Pilot) -> None:
        await set_port(app, pilot, "99999")
        app.action_request_quit()
        await settle(pilot)
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
        await settle(pilot)
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
        await settle(pilot)
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
        await settle(pilot)
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
        await settle(pilot)
        await choose(pilot, "discard")
        assert not app.is_running

    run(tmp_config, script)
    assert tmp_config.read_text() == ORIGINAL


def test_cancel_quit_keeps_editing(tmp_config: Path) -> None:
    tmp_config.write_text(ORIGINAL)

    async def script(app: SSHConfigApp, pilot: Pilot) -> None:
        await set_port(app, pilot, "2222")
        app.action_request_quit()
        await settle(pilot)
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
        await settle(pilot)
        assert not app._modified
        for key in "jjkjj":
            await pilot.press(key)
            await settle(pilot)
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
    await settle(pilot)


def test_deleting_a_field_sets_modified_and_updates_model(tmp_config: Path) -> None:
    tmp_config.write_text(MULTI)

    async def script(app: SSHConfigApp, pilot: Pilot) -> None:
        row = app.query(ParamRow).last()
        row.post_message(ParamRow.DeleteRequested(row))
        await settle(pilot)
        assert app._modified
        assert app._config.entries[0].params == [("User", "x")]

    run(tmp_config, script)


def test_adding_a_field_sets_modified(tmp_config: Path) -> None:
    tmp_config.write_text(MULTI)

    async def script(app: SSHConfigApp, pilot: Pilot) -> None:
        app._do_add_field()
        await settle(pilot)
        await pilot.press(*"ForwardAgent", "enter")
        await settle(pilot)
        assert app._modified
        await pilot.press(*"yes")
        await settle(pilot)
        assert app._config.entries[0].get("ForwardAgent") == "yes"

    run(tmp_config, script)


def test_host_level_edits_set_modified(tmp_config: Path) -> None:
    tmp_config.write_text(MULTI)

    async def script(app: SSHConfigApp, pilot: Pilot) -> None:
        app.action_delete_host()
        await settle(pilot)
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
            await settle(pilot)
            entry = app._config.entries[expected]
            assert app._current_entry is entry
            assert shown_params(app) == entry.params, entry.pattern

    run(tmp_config, script)


def test_editor_consistent_after_key_burst(tmp_config: Path) -> None:
    tmp_config.write_text(VARIED)

    async def script(app: SSHConfigApp, pilot: Pilot) -> None:
        await pilot.press(*"jjjjkjjkkj")  # no pause between keys
        await settle(pilot)
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
            await settle(pilot)
        app.query(ParamRow).first().query(Input).last().value = "changed"
        await settle(pilot)
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
        await settle(pilot)
        app.action_edit_host()
        await settle(pilot)
        app.screen.query_one("#dialog-input", Input).value = "three tres"
        await choose(pilot, "ok")
        assert host_list_labels(app)[1] == "three tres"
        assert app._current_entry is app._config.entries[1]

    run(tmp_config, script)


def test_delete_selects_the_next_host(tmp_config: Path) -> None:
    tmp_config.write_text(VARIED)

    async def script(app: SSHConfigApp, pilot: Pilot) -> None:
        await pilot.press("j", "j")
        await settle(pilot)
        app.action_delete_host()
        await settle(pilot)
        await choose(pilot, "ok")
        assert host_list_labels(app) == ["zero", "three", "five", "two"]
        assert app._current_entry.pattern == "five"
        assert shown_params(app) == app._current_entry.params

    run(tmp_config, script)


def test_delete_last_host_selects_new_last(tmp_config: Path) -> None:
    tmp_config.write_text(VARIED)

    async def script(app: SSHConfigApp, pilot: Pilot) -> None:
        await pilot.press("end")
        await settle(pilot)
        app.action_delete_host()
        await settle(pilot)
        await choose(pilot, "ok")
        assert app._current_entry.pattern == "five"

    run(tmp_config, script)


def test_new_host_is_selected(tmp_config: Path) -> None:
    tmp_config.write_text(VARIED)

    async def script(app: SSHConfigApp, pilot: Pilot) -> None:
        app.action_new_host()
        await settle(pilot)
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
        await settle(pilot)
        assert app._current_entry.pattern == "zero"
        await pilot.press("end", "j", "down")
        await settle(pilot)
        assert app._current_entry.pattern == "two"

    run(tmp_config, script)


# ─── Keyword picker ───────────────────────────────────────────────────────────


async def open_picker(app: SSHConfigApp, pilot: Pilot):
    from sshconfigmgr.app import AddFieldScreen

    app._do_add_field()
    await settle(pilot)
    assert isinstance(app.screen, AddFieldScreen)
    return app.screen


def suggestions(screen) -> list[str]:
    from sshconfigmgr.app import KeywordList

    kl = screen.query_one(KeywordList)
    return [str(kl.get_option_at_index(i).prompt) for i in range(kl.option_count)]


def test_picker_filters_and_hides_used_single_keywords(tmp_config: Path) -> None:
    tmp_config.write_text("Host a\n    LogLevel INFO\n    LocalForward 1 h:2\n")

    async def script(app: SSHConfigApp, pilot: Pilot) -> None:
        screen = await open_picker(app, pilot)
        await pilot.press(*"Lo")
        await settle(pilot)
        # LogLevel is single-use and already present; LocalForward may repeat.
        assert suggestions(screen) == ["LocalCommand", "LocalForward", "LogVerbose"]

    run(tmp_config, script)


def test_picker_keyboard_navigation(tmp_config: Path) -> None:
    from sshconfigmgr.app import KeywordList

    tmp_config.write_text("Host a\n")

    async def script(app: SSHConfigApp, pilot: Pilot) -> None:
        screen = await open_picker(app, pilot)
        await pilot.press(*"Loc")
        await pilot.press("down")
        await settle(pilot)
        kl = screen.query_one(KeywordList)
        assert screen.focused is kl and kl.highlighted == 0
        await pilot.press("down", "down", "down")  # stops at the last option
        await settle(pilot)
        assert kl.highlighted == 1
        await pilot.press("up", "up")  # past the top returns to the input
        await settle(pilot)
        assert screen.focused is screen.query_one("#kw-input", Input)
        await pilot.press("down", "down", "enter")
        await settle(pilot)
        assert app._current_entry.params == [("LocalForward", "")]

    run(tmp_config, script)


def test_picker_enter_in_input_uses_canonical_case_or_free_text(tmp_config: Path) -> None:
    tmp_config.write_text("Host a\n")

    async def script(app: SSHConfigApp, pilot: Pilot) -> None:
        await open_picker(app, pilot)
        await pilot.press(*"proxyjump", "enter")
        await settle(pilot)
        await open_picker(app, pilot)
        await pilot.press(*"XCustomThing", "enter")
        await settle(pilot)
        assert [k for k, _ in app._current_entry.params] == ["ProxyJump", "XCustomThing"]

    run(tmp_config, script)


def test_picker_click_selects(tmp_config: Path) -> None:
    from sshconfigmgr.app import KeywordList

    tmp_config.write_text("Host a\n")

    async def script(app: SSHConfigApp, pilot: Pilot) -> None:
        screen = await open_picker(app, pilot)
        await pilot.press(*"Port")
        await settle(pilot)
        assert suggestions(screen) == ["Port"]
        await pilot.click(KeywordList, offset=(3, 1))
        await settle(pilot)
        assert app._current_entry.params == [("Port", "")]

    run(tmp_config, script)


def test_picker_escape_cancels(tmp_config: Path) -> None:
    tmp_config.write_text("Host a\n")

    async def script(app: SSHConfigApp, pilot: Pilot) -> None:
        await open_picker(app, pilot)
        await pilot.press(*"Port", "escape")
        await settle(pilot)
        assert app._current_entry.params == []
        assert not app._modified

    run(tmp_config, script)


# ─── Save dialog and ssh validation ───────────────────────────────────────────

from sshconfigmgr.app import (  # noqa: E402
    SaveScreen,
    ValidationErrorScreen,
    ValidationFailedScreen,
)
from sshconfigmgr.ssh_validate import ValidationResult  # noqa: E402
from textual.widgets import Button, Checkbox, Static  # noqa: E402


class FakeValidation:
    def __init__(self) -> None:
        self.result = ValidationResult(True, "")
        self.validated: list[str] = []

    async def __call__(self, config: SSHConfig, **kwargs) -> ValidationResult:
        self.validated.append(config.render())
        return self.result


@pytest.fixture
def fake_validation(monkeypatch: pytest.MonkeyPatch) -> FakeValidation:
    fake = FakeValidation()
    monkeypatch.setattr(ssh_validate, "find_ssh", lambda: "/usr/bin/ssh")
    monkeypatch.setattr(ssh_validate, "validate_with_ssh", fake)
    return fake


def notifications(app: SSHConfigApp) -> list[str]:
    return [n.message for n in app._notifications]


def checkbox(app: SSHConfigApp) -> Checkbox:
    return app.screen.query_one("#validate-ssh", Checkbox)


async def open_save(app: SSHConfigApp, pilot: Pilot) -> None:
    await pilot.press("ctrl+s")
    await settle(pilot)
    assert isinstance(app.screen, SaveScreen)


def test_ctrl_s_opens_save_dialog_and_cancel_does_not_write(tmp_config: Path) -> None:
    tmp_config.write_text(ORIGINAL)

    async def script(app: SSHConfigApp, pilot: Pilot) -> None:
        await set_port(app, pilot, "2222")
        await open_save(app, pilot)
        await choose(pilot, "cancel")
        assert app._modified

    run(tmp_config, script)
    assert tmp_config.read_text() == ORIGINAL


def test_save_dialog_enter_saves(tmp_config: Path) -> None:
    tmp_config.write_text(ORIGINAL)

    async def script(app: SSHConfigApp, pilot: Pilot) -> None:
        await set_port(app, pilot, "2222")
        await open_save(app, pilot)
        await pilot.press("enter")
        await settle(pilot)
        assert not app._modified

    run(tmp_config, script)
    assert tmp_config.read_text() == "Host a\n    Port 2222\n"


def test_checkbox_disabled_without_ssh(tmp_config: Path) -> None:
    tmp_config.write_text(ORIGINAL)

    async def script(app: SSHConfigApp, pilot: Pilot) -> None:
        await open_save(app, pilot)
        box = checkbox(app)
        assert box.disabled and not box.value
        assert "ssh not found" in str(box.label)

    run(tmp_config, script)


def test_checkbox_defaults_on_and_is_remembered(
    tmp_config: Path, fake_validation: FakeValidation
) -> None:
    tmp_config.write_text(ORIGINAL)

    async def script(app: SSHConfigApp, pilot: Pilot) -> None:
        await open_save(app, pilot)
        assert checkbox(app).value and not checkbox(app).disabled
        await pilot.click("#validate-ssh")
        await settle(pilot)
        assert not checkbox(app).value
        await choose(pilot, "cancel")
        # Remembered in the next Save dialog ...
        await open_save(app, pilot)
        assert not checkbox(app).value
        await pilot.click("#validate-ssh")
        await choose(pilot, "cancel")
        # ... and shared with the Quit dialog.
        await set_port(app, pilot, "2222")
        app.action_request_quit()
        await settle(pilot)
        assert isinstance(app.screen, UnsavedChangesScreen)
        assert checkbox(app).value

    run(tmp_config, script)


def test_unchecked_save_skips_validation(tmp_config: Path, fake_validation: FakeValidation) -> None:
    tmp_config.write_text(ORIGINAL)

    async def script(app: SSHConfigApp, pilot: Pilot) -> None:
        await set_port(app, pilot, "2222")
        await open_save(app, pilot)
        await pilot.click("#validate-ssh")
        await choose(pilot, "save")

    run(tmp_config, script)
    assert fake_validation.validated == []
    assert tmp_config.read_text() == "Host a\n    Port 2222\n"


def test_validation_success_shows_message_and_saves(
    tmp_config: Path, fake_validation: FakeValidation
) -> None:
    # Bytes, not write_text(): this test compares the exact text validated,
    # and write_text() would give the file \r\n line endings on Windows.
    tmp_config.write_bytes(ORIGINAL.encode())

    async def script(app: SSHConfigApp, pilot: Pilot) -> None:
        await set_port(app, pilot, "2222")
        await open_save(app, pilot)
        await choose(pilot, "save")
        await settle(pilot)
        assert "✔️ Validated" in notifications(app)
        assert not app._modified

    run(tmp_config, script)
    assert fake_validation.validated == ["Host a\n    Port 2222\n"]
    assert tmp_config.read_text() == "Host a\n    Port 2222\n"


def test_validation_failure_continue_anyway_saves(
    tmp_config: Path, fake_validation: FakeValidation
) -> None:
    tmp_config.write_text(ORIGINAL)
    fake_validation.result = ValidationResult(False, "config: line 2: Bad configuration option: prot")

    async def script(app: SSHConfigApp, pilot: Pilot) -> None:
        await set_port(app, pilot, "2222")
        await open_save(app, pilot)
        await choose(pilot, "save")
        await settle(pilot)
        assert isinstance(app.screen, ValidationFailedScreen)
        await choose(pilot, "continue")
        assert not app._modified

    run(tmp_config, script)
    assert tmp_config.read_text() == "Host a\n    Port 2222\n"


def test_validation_failure_show_error_then_close_returns_to_editor(
    tmp_config: Path, fake_validation: FakeValidation
) -> None:
    tmp_config.write_text(ORIGINAL)
    error = "config: line 2: Bad configuration option: [prot]"
    fake_validation.result = ValidationResult(False, error)

    async def script(app: SSHConfigApp, pilot: Pilot) -> None:
        await set_port(app, pilot, "2222")
        await open_save(app, pilot)
        await choose(pilot, "save")
        await settle(pilot)
        await choose(pilot, "show")
        assert isinstance(app.screen, ValidationErrorScreen)
        shown = str(app.screen.query_one("#validation-output Static", Static).render())
        assert shown == error  # brackets shown literally, not parsed as markup
        assert [b.id for b in app.screen.query(Button)] == ["close"]
        await choose(pilot, "close")
        assert app.screen is app.screen_stack[0]  # back to the editor
        assert app._modified

    run(tmp_config, script)
    assert tmp_config.read_text() == ORIGINAL


def test_validation_failure_escape_returns_to_editor(
    tmp_config: Path, fake_validation: FakeValidation
) -> None:
    tmp_config.write_text(ORIGINAL)
    fake_validation.result = ValidationResult(False, "bad")

    async def script(app: SSHConfigApp, pilot: Pilot) -> None:
        await set_port(app, pilot, "2222")
        await open_save(app, pilot)
        await choose(pilot, "save")
        await settle(pilot)
        await pilot.press("escape")
        await settle(pilot)
        assert app.screen is app.screen_stack[0]

    run(tmp_config, script)
    assert tmp_config.read_text() == ORIGINAL


def test_quit_validation_success_saves_and_quits(
    tmp_config: Path, fake_validation: FakeValidation
) -> None:
    tmp_config.write_text(ORIGINAL)

    async def script(app: SSHConfigApp, pilot: Pilot) -> None:
        await set_port(app, pilot, "2222")
        app.action_request_quit()
        await settle(pilot)
        await choose(pilot, "save")
        await settle(pilot)
        assert not app.is_running

    run(tmp_config, script)
    assert len(fake_validation.validated) == 1
    assert tmp_config.read_text() == "Host a\n    Port 2222\n"


def test_quit_validation_failure_show_error_stays_open(
    tmp_config: Path, fake_validation: FakeValidation
) -> None:
    tmp_config.write_text(ORIGINAL)
    fake_validation.result = ValidationResult(False, "bad")

    async def script(app: SSHConfigApp, pilot: Pilot) -> None:
        await set_port(app, pilot, "2222")
        app.action_request_quit()
        await settle(pilot)
        await choose(pilot, "save")
        await settle(pilot)
        await choose(pilot, "show")
        await choose(pilot, "close")
        assert app.is_running
        assert app._modified

    run(tmp_config, script)
    assert tmp_config.read_text() == ORIGINAL


def test_quit_validation_failure_continue_anyway_saves_and_quits(
    tmp_config: Path, fake_validation: FakeValidation
) -> None:
    tmp_config.write_text(ORIGINAL)
    fake_validation.result = ValidationResult(False, "bad")

    async def script(app: SSHConfigApp, pilot: Pilot) -> None:
        await set_port(app, pilot, "2222")
        app.action_request_quit()
        await settle(pilot)
        await choose(pilot, "save")
        await settle(pilot)
        await choose(pilot, "continue")
        assert not app.is_running

    run(tmp_config, script)
    assert tmp_config.read_text() == "Host a\n    Port 2222\n"


def test_quit_unchecked_does_not_validate(tmp_config: Path, fake_validation: FakeValidation) -> None:
    tmp_config.write_text(ORIGINAL)

    async def script(app: SSHConfigApp, pilot: Pilot) -> None:
        await set_port(app, pilot, "2222")
        app.action_request_quit()
        await settle(pilot)
        await pilot.click("#validate-ssh")
        await choose(pilot, "save")
        assert not app.is_running

    run(tmp_config, script)
    assert fake_validation.validated == []


def test_picker_highlights_do_not_reach_host_selection(tmp_config: Path) -> None:
    """OptionHighlighted from the picker bubbles to the app; only the host
    list's highlights may select hosts."""
    tmp_config.write_text(VARIED)

    async def script(app: SSHConfigApp, pilot: Pilot) -> None:
        selected: list[int] = []
        original = app._select
        app._select = lambda index: (selected.append(index), original(index))[1]
        await open_picker(app, pilot)
        await pilot.press(*"Pro", "down", "down", "up")
        await settle(pilot)
        assert selected == []

    run(tmp_config, script)


def test_stale_input_event_after_row_reuse_is_ignored(tmp_config: Path) -> None:
    """A Changed event queued before a row was reused for another host must
    not write the old host's value into the new host (seen with fast
    navigation on a slow runner)."""
    tmp_config.write_text(VARIED)

    async def script(app: SSHConfigApp, pilot: Pilot) -> None:
        await pilot.press("j", "j")  # zero -> three -> one: rows reused
        await settle(pilot)
        key_input = app.query(ParamRow).first().query(Input).first()
        assert key_input.value == "User"
        # Simulate the queued event from when this row showed Host three.
        key_input.post_message(Input.Changed(key_input, "Port"))
        await settle(pilot)
        assert app._config.entries[2].params == [("User", "u1")]
        assert not app._modified

    run(tmp_config, script)
