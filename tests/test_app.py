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
