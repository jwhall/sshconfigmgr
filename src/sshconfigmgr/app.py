"""Textual TUI for sshconfigmgr."""
from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

from rich.text import Text
from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.message import Message
from textual.screen import ModalScreen
from textual.widget import Widget
from textual.widgets import (
    Button,
    Checkbox,
    Footer,
    Header,
    Input,
    Label,
    OptionList,
    Static,
)
from textual.widgets.option_list import Option

from sshconfigmgr import ssh_validate
from sshconfigmgr.ssh_config import ConfigChangedError, HostEntry, SSHConfig

# ─── Styles ───────────────────────────────────────────────────────────────────

APP_CSS = """
Screen {
    background: #1c1c1c;
    color: #d4d4d4;
}

Header {
    height: 2;
    background: #202020;
    border-bottom: solid #2e2e2e;
}

HeaderTitle {
    color: #6a9fb5;
    background: #202020;
}

Footer {
    background: #202020;
    color: #505050;
    border-top: solid #2e2e2e;
}

#main {
    height: 1fr;
}

/* ── Sidebar ── */

#sidebar {
    width: 30%;
    border-right: solid #2e2e2e;
    layout: vertical;
    background: #1c1c1c;
}

.pane-title {
    background: #202020;
    color: #505050;
    padding: 0 1;
    /* Heights include the border: one row of text plus the bottom border. */
    height: 2;
    border-bottom: solid #2a2a2a;
    text-style: bold;
}

#host-list {
    background: #1c1c1c;
    height: 1fr;
    max-height: 100%;
    border: none;
    padding: 1 0;
}

#host-list:focus {
    border: none;
}

#host-list > .option-list--option {
    padding: 0 2;
    color: #888888;
}

#host-list > .option-list--option-highlighted,
#host-list:focus > .option-list--option-highlighted {
    background: #1a2e3a;
    color: #c8c8c8;
    text-style: none;
}

#host-list > .option-list--option-hover {
    background: #222222;
}

#sidebar-actions {
    background: #1e1e1e;
    border-top: solid #2a2a2a;
    height: 5;
    padding: 0 1;
    align: left middle;
}

#sidebar-actions Button {
    min-width: 12;
    background: #222222;
    border: tall #333333;
    color: #808080;
}

#sidebar-actions Button:hover {
    background: #282828;
    color: #d4d4d4;
}

/* ── Editor ── */

#editor {
    width: 70%;
    layout: vertical;
}

#editor-header {
    color: #6a9fb5;
}

#params-scroll {
    height: 1fr;
    padding: 1 1 0 1;
    background: #1c1c1c;
}

#empty-msg {
    color: #404040;
    padding: 1;
}

.param-row {
    layout: horizontal;
    height: 3;
    margin-bottom: 1;
}

.param-key {
    width: 20;
    margin-right: 1;
}

.param-val {
    width: 1fr;
    margin-right: 1;
}

.param-del {
    width: 3;
    min-width: 3;
    background: #1c1c1c;
    border: tall #2e2e2e;
    color: #5a3a3a;
}

.param-del:hover {
    background: #2a1a1a;
    border: tall #6a3030;
    color: #ac4142;
}

#add-field {
    margin: 0;
    background: transparent;
    border: tall #2a2a2a;
    color: #505050;
    width: auto;
    min-width: 12;
}

#add-field:hover {
    border: tall #4a7a90;
    color: #6a9fb5;
}

/* ── Action bar ── */

.action-bar {
    background: #1e1e1e;
    border-top: solid #2a2a2a;
    height: 5;
    padding: 0 1;
    align: right middle;
}

.action-bar Button {
    margin-left: 1;
    min-width: 10;
    background: #222222;
    border: tall #333333;
    color: #808080;
}

.action-bar Button:hover {
    background: #282828;
    color: #d4d4d4;
}

.action-bar Button.-primary {
    border: tall #2a5070;
    color: #6a9fb5;
}

.action-bar Button.-primary:hover {
    background: #1a2a38;
    color: #8ab8d0;
}

/* ── Inputs ── */

Input {
    background: #181818;
    border: tall #2e2e2e;
    color: #c8c8c8;
    height: 3;
}

Input:focus {
    border: tall #4a7a90;
    color: #d4d4d4;
}

/* ── Modal dialogs ── */

ConfirmScreen, InputScreen, UnsavedChangesScreen, SaveScreen,
ValidationFailedScreen, ValidationErrorScreen {
    align: center middle;
}

.dialog {
    background: #222222;
    border: solid #444444;
    padding: 1 2;
    width: 60;
    height: auto;
}

.dialog-title {
    text-style: bold;
    color: #6a9fb5;
    margin-bottom: 1;
}

.dialog-msg {
    color: #a0a0a0;
    margin-bottom: 0;
    /* Full width so long messages (e.g. file paths) wrap instead of clipping. */
    width: 100%;
}

.dialog-buttons {
    layout: horizontal;
    align: right middle;
    margin-top: 1;
    height: 3;
}

.dialog-buttons Button {
    margin-left: 1;
    min-width: 9;
    background: #1e1e1e;
    border: tall #333333;
    color: #808080;
}

.dialog-buttons Button.-primary {
    border: tall #2a5070;
    color: #6a9fb5;
}

.dialog-wide {
    width: 90%;
    max-width: 110;
}

#validation-output {
    height: auto;
    max-height: 15;
    background: #181818;
    border: tall #2e2e2e;
    padding: 0 1;
}

#validation-output Static {
    color: #c8c8c8;
}

#validate-ssh {
    margin-top: 1;
    background: transparent;
    border: none;
    color: #a0a0a0;
}

#validate-ssh:focus {
    color: #d4d4d4;
}

.dialog-buttons Button.-error {
    border: tall #6a2a2a;
    color: #ac4142;
}
"""

# ─── Modal screens ─────────────────────────────────────────────────────────────


class ConfirmScreen(ModalScreen[bool]):
    """A yes / no confirmation dialog."""

    BINDINGS = [
        Binding("escape", "dismiss(False)", show=False),
    ]

    def __init__(self, message: str, title: str = "Confirm") -> None:
        super().__init__()
        self._message = message
        self._title = title

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog"):
            yield Label(self._title, classes="dialog-title")
            yield Label(self._message, classes="dialog-msg")
            with Horizontal(classes="dialog-buttons"):
                yield Button("Cancel", id="cancel")
                yield Button("OK", id="ok", variant="error")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "ok")


class InputScreen(ModalScreen[Optional[str]]):
    """A single-line input dialog."""

    BINDINGS = [
        Binding("escape", "dismiss(None)", show=False),
    ]

    def __init__(self, prompt: str, title: str = "Input", default: str = "", confirm_label: str = "OK") -> None:
        super().__init__()
        self._prompt = prompt
        self._title = title
        self._default = default
        self._confirm_label = confirm_label

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog"):
            yield Label(self._title, classes="dialog-title")
            yield Label(self._prompt, classes="dialog-msg")
            yield Input(self._default, id="dialog-input")
            with Horizontal(classes="dialog-buttons"):
                yield Button("Cancel", id="cancel")
                yield Button(self._confirm_label, id="ok", variant="primary")

    def on_mount(self) -> None:
        inp = self.query_one("#dialog-input", Input)
        inp.focus()
        inp.cursor_position = len(self._default)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        value = event.value.strip()
        self.dismiss(value if value else None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "ok":
            value = self.query_one("#dialog-input", Input).value.strip()
            self.dismiss(value if value else None)
        else:
            self.dismiss(None)


VALIDATE_LABEL = "Validate config with SSH?"


def validate_checkbox(value: bool, available: bool) -> Checkbox:
    """The "Validate config with SSH?" option shown in Save and Quit dialogs."""
    if available:
        return Checkbox(VALIDATE_LABEL, value, id="validate-ssh")
    return Checkbox(f"{VALIDATE_LABEL} (ssh not found)", False, id="validate-ssh", disabled=True)


class SaveScreen(ModalScreen[bool]):
    """Confirm saving, with the option to validate with ssh first.

    Dismisses with True (save) or False (cancel); the checkbox state is
    available afterwards as ``validate``.
    """

    BINDINGS = [
        Binding("escape", "dismiss(False)", show=False),
    ]

    def __init__(self, path: Path, validate: bool, ssh_available: bool) -> None:
        super().__init__()
        self._path = path
        self.validate = validate
        self.ssh_available = ssh_available

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog"):
            yield Label("Save Changes", classes="dialog-title")
            yield Label(f"Write changes to {self._path}?", classes="dialog-msg")
            yield validate_checkbox(self.validate, self.ssh_available)
            with Horizontal(classes="dialog-buttons"):
                yield Button("Cancel", id="cancel")
                yield Button("Save", id="save", variant="primary")

    def on_mount(self) -> None:
        self.query_one("#save", Button).focus()

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        self.validate = event.value

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "save")


class UnsavedChangesScreen(ModalScreen[Optional[str]]):
    """Three-way dialog: Save / Discard / Cancel before leaving unsaved changes.

    *action* names what happens afterwards (e.g. "Quit", "Open").
    Dismisses with: "save", "discard", or None (cancel); the checkbox state
    is available afterwards as ``validate``.
    """

    BINDINGS = [
        Binding("escape", "dismiss(None)", show=False),
    ]

    def __init__(self, action: str, validate: bool = False, ssh_available: bool = False) -> None:
        super().__init__()
        self._action = action
        self.validate = validate
        self.ssh_available = ssh_available

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog"):
            yield Label("Unsaved Changes", classes="dialog-title")
            yield Label("You have unsaved changes. What would you like to do?", classes="dialog-msg")
            yield validate_checkbox(self.validate, self.ssh_available)
            with Horizontal(classes="dialog-buttons"):
                yield Button("Cancel", id="cancel")
                yield Button(f"Discard & {self._action}", id="discard", variant="error")
                yield Button(f"Save & {self._action}", id="save", variant="primary")

    def on_mount(self) -> None:
        # Keep Cancel as the default so a reflexive Enter loses nothing.
        self.query_one("#cancel", Button).focus()

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        self.validate = event.value

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "save":
            self.dismiss("save")
        elif bid == "discard":
            self.dismiss("discard")
        else:
            self.dismiss(None)


class ValidationFailedScreen(ModalScreen[Optional[str]]):
    """ssh rejected the config.  Dismisses with "show", "continue", or None
    (Escape: back to the editor without saving)."""

    BINDINGS = [
        Binding("escape", "dismiss(None)", show=False),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog"):
            yield Label("❌ Validation failed", classes="dialog-title")
            yield Label(
                "ssh reported errors in the configuration. Nothing has been written yet.",
                classes="dialog-msg",
            )
            with Horizontal(classes="dialog-buttons"):
                yield Button("Show error", id="show", variant="primary")
                yield Button("Continue anyway", id="continue", variant="error")

    def on_mount(self) -> None:
        self.query_one("#show", Button).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id)


class ValidationErrorScreen(ModalScreen[None]):
    """Shows the output of the ssh validation run."""

    BINDINGS = [
        Binding("escape", "dismiss(None)", show=False),
    ]

    def __init__(self, output: str) -> None:
        super().__init__()
        self._output = output

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog dialog-wide"):
            yield Label("SSH Validation Error", classes="dialog-title")
            with VerticalScroll(id="validation-output"):
                # Text, not str: ssh output must not be parsed as markup.
                yield Static(Text(self._output))
            with Horizontal(classes="dialog-buttons"):
                yield Button("Close", id="close", variant="primary")

    def on_mount(self) -> None:
        self.query_one("#close", Button).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(None)


# ─── SSH keyword data ──────────────────────────────────────────────────────────

# Keywords that may appear multiple times in one Host block.
SSH_KEYWORDS_MULTI: list[str] = [
    "CertificateFile",
    "DynamicForward",
    "GlobalKnownHostsFile",
    "IdentityFile",
    "LocalForward",
    "RemoteForward",
    "SendEnv",
    "SetEnv",
]

# Keywords that should appear at most once per Host block.
SSH_KEYWORDS_SINGLE: list[str] = [
    "AddKeysToAgent",
    "AddressFamily",
    "BatchMode",
    "BindAddress",
    "BindInterface",
    "CanonicalDomains",
    "CanonicalizeFallbackLocal",
    "CanonicalizeHostname",
    "CanonicalizeMaxDots",
    "CheckHostIP",
    "Ciphers",
    "ClearAllForwardings",
    "Compression",
    "ConnectTimeout",
    "ConnectionAttempts",
    "ControlMaster",
    "ControlPath",
    "ControlPersist",
    "EnableEscapeCommandline",
    "EnableSSHKeysign",
    "EscapeChar",
    "ExitOnForwardFailure",
    "FingerprintHash",
    "ForkAfterAuthentication",
    "ForwardAgent",
    "ForwardX11",
    "ForwardX11Timeout",
    "ForwardX11Trusted",
    "GSSAPIAuthentication",
    "GSSAPIDelegateCredentials",
    "HashKnownHosts",
    "HostKeyAlgorithms",
    "HostKeyAlias",
    "HostbasedAcceptedAlgorithms",
    "HostbasedAuthentication",
    "Hostname",
    "IPQoS",
    "IdentitiesOnly",
    "IdentityAgent",
    "KbdInteractiveAuthentication",
    "KexAlgorithms",
    "KnownHostsCommand",
    "LocalCommand",
    "LogLevel",
    "LogVerbose",
    "MACs",
    "NoHostAuthenticationForLocalhost",
    "NumberOfPasswordPrompts",
    "ObscureKeystrokeTiming",
    "PKCS11Provider",
    "PasswordAuthentication",
    "PermitLocalCommand",
    "PermitRemoteOpen",
    "Port",
    "PreferredAuthentications",
    "ProxyCommand",
    "ProxyJump",
    "ProxyUseFdpass",
    "PubkeyAcceptedAlgorithms",
    "PubkeyAuthentication",
    "RekeyLimit",
    "RemoteCommand",
    "RequestTTY",
    "RequiredRSASize",
    "ServerAliveCountMax",
    "ServerAliveInterval",
    "StdinNull",
    "StreamLocalBindMask",
    "StreamLocalBindUnlink",
    "StrictHostKeyChecking",
    "SyslogFacility",
    "TCPKeepAlive",
    "Tunnel",
    "TunnelDevice",
    "UpdateHostKeys",
    "User",
    "UserKnownHostsFile",
    "VerifyHostKeyDNS",
    "VisualHostKey",
    "XAuthLocation",
]

_SINGLE_LOWER: set[str] = {k.lower() for k in SSH_KEYWORDS_SINGLE}


class NoWrapOptionList(OptionList):
    """OptionList whose cursor stops at the first and last option.

    OptionList wraps around at the ends by default; ListView, which these
    lists replaced, did not.
    """

    def action_cursor_down(self) -> None:
        if self.highlighted is None or self.highlighted < self.option_count - 1:
            super().action_cursor_down()

    def action_cursor_up(self) -> None:
        if self.highlighted is None or self.highlighted > 0:
            super().action_cursor_up()


class KeywordList(NoWrapOptionList):
    """Suggestion list for AddFieldScreen; Up on the first option posts AtTop."""

    class AtTop(Message):
        pass

    def action_cursor_up(self) -> None:
        if self.highlighted in (None, 0):
            self.post_message(self.AtTop())
        else:
            super().action_cursor_up()


class AddFieldScreen(ModalScreen[Optional[str]]):
    """Modal for choosing a new SSH config keyword with live-filtered suggestions.

    Dismisses with the chosen keyword string, or None if cancelled.
    """

    BINDINGS = [
        Binding("escape", "dismiss(None)", show=False),
        Binding("down", "focus_suggestions", show=False),
    ]

    DEFAULT_CSS = """
    AddFieldScreen {
        align: center middle;
    }
    #add-field-dialog {
        background: #222222;
        border: solid #444444;
        padding: 1 2;
        width: 60;
        /* Fixed height so the list below can flex: on short terminals the
           list shrinks and the buttons stay visible. */
        height: 80%;
        max-height: 26;
    }
    #add-field-dialog .dialog-title {
        text-style: bold;
        color: #6a9fb5;
        margin-bottom: 1;
    }
    #suggestion-list {
        height: 1fr;
        min-height: 3;
        border: tall #2e2e2e;
        background: #181818;
        margin-top: 0;
        margin-bottom: 1;
    }
    #suggestion-list > .option-list--option {
        padding: 0 1;
    }
    #suggestion-list > .option-list--option-highlighted,
    #suggestion-list:focus > .option-list--option-highlighted {
        background: #1a2e3a;
        color: #c8c8c8;
        text-style: none;
    }
    #add-field-dialog .dialog-buttons {
        layout: horizontal;
        align: right middle;
        margin-top: 1;
        height: 3;
    }
    #add-field-dialog .dialog-buttons Button {
        margin-left: 1;
        min-width: 9;
        background: #1e1e1e;
        border: tall #333333;
        color: #808080;
    }
    #add-field-dialog .dialog-buttons Button.-primary {
        border: tall #2a5070;
        color: #6a9fb5;
    }
    """

    def __init__(self, existing_keys: list[str]) -> None:
        super().__init__()
        self._existing_single: set[str] = {
            k.lower() for k in existing_keys if k.lower() in _SINGLE_LOWER
        }
        self._current_matches: list[str] = []

    def _available(self) -> list[str]:
        singles = [k for k in SSH_KEYWORDS_SINGLE if k.lower() not in self._existing_single]
        return sorted(singles + SSH_KEYWORDS_MULTI)

    def _filtered(self, text: str) -> list[str]:
        pool = self._available()
        if not text:
            return pool
        tl = text.lower()
        return [k for k in pool if k.lower().startswith(tl)]

    def compose(self) -> ComposeResult:
        with Vertical(id="add-field-dialog"):
            yield Label("Add Configuration Keyword", classes="dialog-title")
            yield Input(placeholder="Type to filter…", id="kw-input")
            yield KeywordList(id="suggestion-list")
            with Horizontal(classes="dialog-buttons"):
                yield Button("Cancel", id="cancel")
                yield Button("Add", id="add-kw", variant="primary")

    def on_mount(self) -> None:
        self.query_one("#kw-input", Input).focus()
        self._refresh_list("")

    def _refresh_list(self, text: str) -> None:
        self._current_matches = self._filtered(text)
        suggestions = self.query_one("#suggestion-list", KeywordList)
        suggestions.clear_options()
        suggestions.add_options(self._current_matches)

    def _dismiss_from_input(self) -> None:
        text = self.query_one("#kw-input", Input).value.strip()
        if not text:
            return
        for m in self._current_matches:
            if m.lower() == text.lower():
                self.dismiss(m)
                return
        self.dismiss(text)

    def on_input_changed(self, event: Input.Changed) -> None:
        self._refresh_list(event.value)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self._dismiss_from_input()

    def action_focus_suggestions(self) -> None:
        # Reached via the screen's "down" binding, i.e. only when the focused
        # widget (the filter input) doesn't handle Down itself.
        suggestions = self.query_one("#suggestion-list", KeywordList)
        if suggestions.option_count:
            suggestions.focus()
            if suggestions.highlighted is None:
                suggestions.highlighted = 0

    def on_keyword_list_at_top(self, event: KeywordList.AtTop) -> None:
        self.query_one("#kw-input", Input).focus()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        if 0 <= event.option_index < len(self._current_matches):
            self.dismiss(self._current_matches[event.option_index])

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "add-kw":
            self._dismiss_from_input()
        else:
            self.dismiss(None)


# ─── Widgets ───────────────────────────────────────────────────────────────────


class ParamRow(Widget):
    """A single key / value parameter row with a delete button."""

    class Changed(Message):
        pass

    class DeleteRequested(Message):
        def __init__(self, row: "ParamRow") -> None:
            super().__init__()
            self.row = row

    def __init__(self, key: str, value: str) -> None:
        super().__init__(classes="param-row")
        self._key = key
        self._val = value

    def compose(self) -> ComposeResult:
        yield Input(self._key, placeholder="Key", classes="param-key")
        yield Input(self._val, placeholder="Value", classes="param-val")
        yield Button("×", classes="param-del")

    def load(self, key: str, value: str) -> None:
        """Show a different key/value in this row, reusing its widgets.

        Building a row's widgets is the main cost of switching hosts, so the
        editor reuses rows rather than remounting them.  Input.Changed is
        suppressed: this is a display change, not an edit.
        """
        self._key, self._val = key, value
        # Before compose there are no Inputs yet; compose() reads the fields.
        for inp in self.query(Input):
            with inp.prevent(Input.Changed):
                inp.value = key if inp.has_class("param-key") else value
            inp.cursor_position = len(inp.value)

    @property
    def key(self) -> str:
        return self._key

    @property
    def value(self) -> str:
        return self._val

    def on_input_changed(self, event: Input.Changed) -> None:
        event.stop()
        # Ignore stale events: a Changed queued before load() reused this row
        # for another host carries the previous host's value.  A real edit
        # always matches the input's current value (or is followed by a newer
        # event that does).
        if event.value != event.input.value:
            return
        if event.input.has_class("param-key"):
            self._key = event.value
        else:
            self._val = event.value
        self.post_message(self.Changed())

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        self.post_message(self.DeleteRequested(self))


# ─── Widgets (continued) ──────────────────────────────────────────────────────


class HostList(NoWrapOptionList):
    """Host list with vim-style j/k navigation.

    An OptionList renders its rows as lines rather than one widget per
    entry, so its cost doesn't grow with the number of hosts.
    """

    BINDINGS = [
        *OptionList.BINDINGS,
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
    ]


# ─── Application ──────────────────────────────────────────────────────────────


class SSHConfigApp(App[None]):
    CSS = APP_CSS
    TITLE = "sshconfigmgr"

    BINDINGS = [
        Binding("ctrl+s", "save", "^S Save", show=True),
        Binding("n", "new_host", "n New", show=True),
        Binding("d", "delete_host", "d Delete", show=True),
        Binding("o", "open_file", "o Open", show=True),
        Binding("escape", "focus_list", "Esc List", show=True),
        Binding("q", "request_quit", "q Quit", show=True),
    ]

    def __init__(self, config_path: Path) -> None:
        super().__init__()
        self._config_path = config_path
        self._config = SSHConfig(path=config_path)
        self._current_entry: Optional[HostEntry] = None
        self._modified = False
        # "Validate config with SSH?" choice; None until first set this session.
        self._validate_with_ssh: Optional[bool] = None
        # Rows of the entry being edited, in order.  Tracked explicitly rather
        # than queried from the DOM, where removed rows linger until pruned.
        self._rows: list[ParamRow] = []

    # ── Composition ──────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="main"):
            with Vertical(id="sidebar"):
                yield Static("HOSTS", classes="pane-title")
                yield HostList(id="host-list")
                with Horizontal(id="sidebar-actions"):
                    yield Button("New Host", id="btn-new")
                    yield Button("Edit Host", id="btn-edit-host")
            with Vertical(id="editor"):
                yield Static("", id="editor-header", classes="pane-title")
                with VerticalScroll(id="params-scroll"):
                    yield Static("← select a host entry", id="empty-msg")
                    yield Button("+ Add Keyword", id="add-field")
                with Horizontal(classes="action-bar"):
                    yield Button("Delete", id="btn-delete")
                    yield Button("Save", id="btn-save", variant="primary")
                    yield Button("Quit", id="btn-quit")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#add-field").display = False
        self._load_config(self._config_path)

    # ── Config I/O ───────────────────────────────────────────────────────────

    def _load_config(self, path: Path) -> None:
        self._config_path = path

        if not path.exists():
            self._config = SSHConfig(path=path)
            self.notify(f"New file — will be created on save: {path}", title="sshconfigmgr")
        else:
            self._config = SSHConfig.from_path(path)

        self._current_entry = None
        self._modified = False
        self._update_title()
        self._show_empty()
        self._rebuild_list(select=0)

    def _rebuild_list(self, select: Optional[int] = None) -> None:
        """Repopulate the host list, then select entry *select* (clamped)."""
        host_list = self.query_one("#host-list", HostList)
        host_list.clear_options()
        host_list.add_options(Option(self._entry_label(e)) for e in self._config.entries)
        if select is not None and self._config.entries:
            self._select(min(max(select, 0), len(self._config.entries) - 1))

    def _select(self, index: int) -> None:
        """Highlight entry *index* in the list and show it in the editor."""
        host_list = self.query_one("#host-list", HostList)
        if host_list.highlighted != index:
            host_list.highlighted = index
        entry = self._config.entries[index]
        if entry is not self._current_entry:
            self._sync_params_to_entry()
            self._load_entry(entry)

    @staticmethod
    def _entry_label(entry: HostEntry) -> Text:
        # Text, not str: patterns and Match criteria must not be parsed as markup.
        return Text(entry.pattern if entry.kind == "Host" else f"{entry.kind} {entry.pattern}")

    def _update_title(self) -> None:
        mod = " (unsaved)" if self._modified else ""
        self.sub_title = f"{self._config_path}{mod}"

    def _refresh_modified(self) -> None:
        """Derive the unsaved flag from content: modified means the file as it
        would be written differs from what was last loaded or saved."""
        modified = self._config.is_modified()
        if modified != self._modified:
            self._modified = modified
            self._update_title()

    # ── Editor ───────────────────────────────────────────────────────────────

    def _show_empty(self) -> None:
        self.query_one("#empty-msg").display = True
        self.query_one("#add-field").display = False
        self.query_one("#editor-header", Static).update("")
        self._clear_rows()

    def _clear_rows(self) -> None:
        for row in self._rows:
            row.remove()
        self._rows = []

    def _load_entry(self, entry: HostEntry) -> None:
        self._current_entry = entry
        self.query_one("#editor-header", Static).update(f"  {entry.kind} {entry.pattern}")
        self.query_one("#empty-msg").display = False
        add_btn = self.query_one("#add-field")
        add_btn.display = True
        # Reuse existing rows; only mount or remove the difference in count.
        params = entry.params
        reused, surplus = self._rows[: len(params)], self._rows[len(params):]
        for row in surplus:
            row.remove()
        for row, (key, value) in zip(reused, params):
            row.load(key, value)
        added = [ParamRow(key, value) for key, value in params[len(reused):]]
        if added:
            add_btn.parent.mount_all(added, before=add_btn)
        self._rows = reused + added
        self.query_one("#params-scroll").scroll_home(animate=False)

    def _sync_params_to_entry(self) -> None:
        if self._current_entry is None:
            return
        params = [
            (row.key.strip(), row.value.strip())
            for row in self._rows
            if row.key.strip()
        ]
        self._current_entry.params = params

    def _validate(self) -> list[str]:
        errors: list[str] = []
        for entry in self._config.entries:
            port = entry.get("Port")
            if port is not None:
                try:
                    p = int(port)
                    if not (1 <= p <= 65535):
                        errors.append(f"Host {entry.pattern}: Port {p} out of range (1–65535)")
                except ValueError:
                    errors.append(f"Host {entry.pattern}: Port must be integer, got {port!r}")
        return errors

    # ── Event handlers ───────────────────────────────────────────────────────

    # Only the host list: highlights in other OptionLists (e.g. the keyword
    # picker's suggestions) bubble up to the app too.
    @on(OptionList.OptionHighlighted, "#host-list")
    def host_highlighted(self, event: OptionList.OptionHighlighted) -> None:
        # Read the list's current state rather than the event's index: the
        # list may have been rebuilt since this message was posted.
        idx = self.query_one("#host-list", HostList).highlighted
        if idx is not None and idx < len(self._config.entries):
            self._select(idx)

    def on_param_row_changed(self, event: ParamRow.Changed) -> None:
        self._sync_params_to_entry()
        self._refresh_modified()

    def on_param_row_delete_requested(self, event: ParamRow.DeleteRequested) -> None:
        if event.row in self._rows:
            self._rows.remove(event.row)
        event.row.remove()
        self._sync_params_to_entry()
        self._refresh_modified()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "add-field":
            self._do_add_field()
        elif bid == "btn-new":
            self.action_new_host()
        elif bid == "btn-edit-host":
            self.action_edit_host()
        elif bid == "btn-delete":
            self.action_delete_host()
        elif bid == "btn-save":
            self.action_save()
        elif bid == "btn-quit":
            self.action_request_quit()

    # ── Actions ──────────────────────────────────────────────────────────────

    def action_focus_list(self) -> None:
        self.query_one("#host-list", HostList).focus()

    def action_new_host(self) -> None:
        def on_result(pattern: Optional[str]) -> None:
            if not pattern:
                return
            self._sync_params_to_entry()
            self._config.add_entry(pattern)
            self._rebuild_list(select=len(self._config.entries) - 1)
            self._refresh_modified()

        self.push_screen(
            InputScreen("Host pattern (e.g. myserver, bastion, *.corp)", "New Host Entry"),
            on_result,
        )

    def action_edit_host(self) -> None:
        if self._current_entry is None:
            self.notify("No host selected.", severity="warning")
            return
        entry = self._current_entry

        def on_result(new_pattern: Optional[str]) -> None:
            if not new_pattern:
                return
            entry.pattern = new_pattern
            self.query_one("#host-list", HostList).replace_option_prompt_at_index(
                self._config.entries.index(entry), self._entry_label(entry)
            )
            self.query_one("#editor-header", Static).update(f"  {entry.kind} {entry.pattern}")
            self._refresh_modified()

        self.push_screen(
            InputScreen(
                "Enter Host names or aliases separated by a space",
                "Edit Host",
                default=entry.pattern,
                confirm_label="Save",
            ),
            on_result,
        )

    def action_delete_host(self) -> None:
        if self._current_entry is None:
            self.notify("No host selected.", severity="warning")
            return
        pattern = self._current_entry.pattern

        def on_result(confirmed: bool) -> None:
            if not confirmed:
                return
            entry_to_remove = self._current_entry
            removed_at = self._config.entries.index(entry_to_remove)
            self._current_entry = None
            self._config.remove_entry(entry_to_remove)
            self._refresh_modified()
            if self._config.entries:
                # Stay at the same position: select the next host (or the
                # new last one) rather than jumping to the top.
                self._rebuild_list(select=removed_at)
            else:
                self._rebuild_list()
                self._show_empty()

        self.push_screen(
            ConfirmScreen(f'Delete Host "{pattern}"?', "Delete Entry"),
            on_result,
        )

    # ── Saving ───────────────────────────────────────────────────────────────

    def _ssh_validate_option(self) -> tuple[bool, bool]:
        """(initial checkbox value, ssh available) for Save/Quit dialogs.

        The checkbox starts checked when ssh is installed, then remembers the
        last choice for the rest of the session.
        """
        available = ssh_validate.find_ssh() is not None
        if not available:
            return False, False
        return (True if self._validate_with_ssh is None else self._validate_with_ssh), True

    def _remember_ssh_validate(self, screen: SaveScreen | UnsavedChangesScreen) -> None:
        if screen.ssh_available:
            self._validate_with_ssh = screen.validate

    def action_save(self) -> None:
        validate, available = self._ssh_validate_option()
        screen = SaveScreen(self._config_path, validate, available)

        def on_result(save: bool) -> None:
            self._remember_ssh_validate(screen)
            if save:
                self._save(validate=screen.validate)

        self.push_screen(screen, on_result)

    def _save(
        self, on_success: Optional[Callable[[], None]] = None, validate: bool = False
    ) -> None:
        """Check and write the config; call *on_success* only if it was written.

        Built-in validation errors, a failed ssh validation (unless the user
        continues anyway), write errors and declining to overwrite an external
        change all leave *on_success* uncalled.
        """
        self._sync_params_to_entry()
        errors = self._validate()
        if errors:
            self.notify("\n".join(errors), title="Validation error", severity="error", timeout=6)
            return
        if validate:
            self._ssh_validate_then_write(on_success)
        else:
            self._write_config(on_success=on_success)

    @work(exclusive=True, group="ssh-validate")
    async def _ssh_validate_then_write(self, on_success: Optional[Callable[[], None]]) -> None:
        result = await ssh_validate.validate_with_ssh(self._config)
        if result.ok:
            self.notify("✔️ Validated", timeout=2)
            self._write_config(on_success=on_success)
            return

        def on_choice(choice: Optional[str]) -> None:
            if choice == "continue":
                self._write_config(on_success=on_success)
            elif choice == "show":
                self.push_screen(ValidationErrorScreen(result.output))

        self.push_screen(ValidationFailedScreen(), on_choice)

    def _write_config(
        self, force: bool = False, on_success: Optional[Callable[[], None]] = None
    ) -> None:
        try:
            self._config.save(force=force)
        except ConfigChangedError:
            def on_result(confirmed: bool) -> None:
                if confirmed:
                    self._write_config(force=True, on_success=on_success)

            self.push_screen(
                ConfirmScreen(
                    f"{self._config_path} was modified by another program since it "
                    "was opened. Overwrite those changes?",
                    "File Changed on Disk",
                ),
                on_result,
            )
            return
        except OSError as exc:
            self.notify(str(exc), title="Save failed", severity="error")
            return
        self._refresh_modified()
        self.notify("Saved.", title="sshconfigmgr", timeout=2)
        if on_success is not None:
            on_success()

    def _confirm_leave(self, action: str, proceed: Callable[[], None]) -> None:
        """Run *proceed* now if there are no unsaved changes, otherwise only
        after the user chooses to save (successfully) or discard them."""
        if not self._modified:
            proceed()
            return

        validate, available = self._ssh_validate_option()
        screen = UnsavedChangesScreen(action, validate, available)

        def on_result(choice: Optional[str]) -> None:
            self._remember_ssh_validate(screen)
            if choice == "save":
                self._save(on_success=proceed, validate=screen.validate)
            elif choice == "discard":
                proceed()

        self.push_screen(screen, on_result)

    def action_open_file(self) -> None:
        def on_path(path_str: Optional[str]) -> None:
            if not path_str:
                return
            path = Path(path_str).expanduser().resolve()

            def load() -> None:
                self._confirm_leave("Open", lambda: self._load_config(path))

            if not path.exists():
                def on_create(confirmed: bool) -> None:
                    if confirmed:
                        load()

                self.push_screen(
                    ConfirmScreen(f"File not found. Create {path}?", "Open File"),
                    on_create,
                )
            else:
                load()

        self.push_screen(
            InputScreen("File path", "Open SSH Config", str(self._config_path)),
            on_path,
        )

    def action_request_quit(self) -> None:
        self._confirm_leave("Quit", self.exit)

    def _do_add_field(self) -> None:
        if self._current_entry is None:
            return
        existing_keys = [row.key for row in self._rows]

        def on_keyword(keyword: Optional[str]) -> None:
            if not keyword:
                return
            add_btn = self.query_one("#add-field")
            row = ParamRow(keyword, "")
            self._rows.append(row)
            add_btn.parent.mount(row, before=add_btn)
            self.call_after_refresh(lambda: row.query_one(".param-val", Input).focus())
            self._sync_params_to_entry()
            self._refresh_modified()

        self.push_screen(AddFieldScreen(existing_keys), on_keyword)
