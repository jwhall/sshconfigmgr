"""Textual TUI for sshconfigmgr."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.message import Message
from textual.screen import ModalScreen
from textual.widget import Widget
from textual.widgets import (
    Button,
    Footer,
    Header,
    Input,
    Label,
    ListItem,
    ListView,
    Static,
)

from ssh_config import HostEntry, SSHConfig

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
    height: 1;
    border-bottom: solid #2a2a2a;
    text-style: bold;
}

ListView {
    background: #1c1c1c;
    height: 1fr;
    border: none;
    padding: 1 0;
}

ListItem {
    padding: 0 2;
    color: #888888;
    height: 1;
}

ListItem.--highlight {
    background: #1a2e3a;
    color: #c8c8c8;
}

ListItem > Label {
    width: 100%;
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
    background: #202020;
    color: #6a9fb5;
    padding: 0 1;
    height: 1;
    border-bottom: solid #2a2a2a;
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

ConfirmScreen, InputScreen {
    align: center middle;
}

.dialog {
    background: #222222;
    border: solid #444444;
    padding: 1 2;
    width: 52;
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

    def __init__(self, prompt: str, title: str = "Input", default: str = "") -> None:
        super().__init__()
        self._prompt = prompt
        self._title = title
        self._default = default

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog"):
            yield Label(self._title, classes="dialog-title")
            yield Label(self._prompt, classes="dialog-msg")
            yield Input(self._default, id="dialog-input")
            with Horizontal(classes="dialog-buttons"):
                yield Button("Cancel", id="cancel")
                yield Button("OK", id="ok", variant="primary")

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


class QuitConfirmScreen(ModalScreen[Optional[str]]):
    """Three-way dialog: Save / Discard / Cancel when quitting with unsaved changes.

    Dismisses with: "save", "discard", or None (cancel).
    """

    BINDINGS = [
        Binding("escape", "dismiss(None)", show=False),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog"):
            yield Label("Unsaved Changes", classes="dialog-title")
            yield Label("You have unsaved changes. What would you like to do?", classes="dialog-msg")
            with Horizontal(classes="dialog-buttons"):
                yield Button("Cancel", id="cancel")
                yield Button("Discard", id="discard", variant="error")
                yield Button("Save & Quit", id="save", variant="primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "save":
            self.dismiss("save")
        elif bid == "discard":
            self.dismiss("discard")
        else:
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


class AddFieldScreen(ModalScreen[Optional[str]]):
    """Modal for choosing a new SSH config keyword with live-filtered suggestions.

    Dismisses with the chosen keyword string, or None if cancelled.
    """

    BINDINGS = [
        Binding("escape", "dismiss(None)", show=False),
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
        height: auto;
        max-height: 80vh;
    }
    #add-field-dialog .dialog-title {
        text-style: bold;
        color: #6a9fb5;
        margin-bottom: 1;
    }
    #suggestion-list {
        height: 10;
        border: tall #2e2e2e;
        background: #181818;
        margin-top: 0;
        margin-bottom: 1;
    }
    #suggestion-list ListItem {
        padding: 0 1;
    }
    #suggestion-list ListItem.--highlight {
        background: #1a2e3a;
        color: #c8c8c8;
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
            yield Label("Add Configuration Field", classes="dialog-title")
            yield Input(placeholder="Type to filter…", id="kw-input")
            yield ListView(id="suggestion-list")
            with Horizontal(classes="dialog-buttons"):
                yield Button("Cancel", id="cancel")
                yield Button("Add", id="add-kw", variant="primary")

    def on_mount(self) -> None:
        self.query_one("#kw-input", Input).focus()
        self._refresh_list("")

    def _refresh_list(self, text: str) -> None:
        self._current_matches = self._filtered(text)
        lv = self.query_one("#suggestion-list", ListView)
        lv.clear()
        for kw in self._current_matches:
            lv.append(ListItem(Label(kw)))

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

    def on_key(self, event) -> None:
        if event.key == "down":
            self.query_one("#suggestion-list", ListView).focus()
            event.prevent_default()
        elif event.key == "up":
            lv = self.query_one("#suggestion-list", ListView)
            if lv.index == 0:
                self.query_one("#kw-input", Input).focus()
                event.prevent_default()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        lv = self.query_one("#suggestion-list", ListView)
        idx = lv.index
        if idx is not None and 0 <= idx < len(self._current_matches):
            self.dismiss(self._current_matches[idx])

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

    @property
    def key(self) -> str:
        return self.query_one(".param-key", Input).value

    @property
    def value(self) -> str:
        return self.query_one(".param-val", Input).value

    def on_input_changed(self, event: Input.Changed) -> None:
        event.stop()
        self.post_message(self.Changed())

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        self.post_message(self.DeleteRequested(self))


# ─── Widgets (continued) ──────────────────────────────────────────────────────


class HostListView(ListView):
    """ListView with vim-style j/k navigation."""

    BINDINGS = [
        *ListView.BINDINGS,
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
        self._loading = False        # guard against spurious Highlighted events
        self._loading_entry = False  # guard against Input.Changed fired on mount

    # ── Composition ──────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="main"):
            with Vertical(id="sidebar"):
                yield Static("HOSTS", classes="pane-title")
                yield HostListView(id="host-list")
                with Horizontal(id="sidebar-actions"):
                    yield Button("New Host", id="btn-new")
            with Vertical(id="editor"):
                yield Static("", id="editor-header", classes="pane-title")
                with VerticalScroll(id="params-scroll"):
                    yield Static("← select a host entry", id="empty-msg")
                    yield Button("+ Add Field", id="add-field")
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
        self._loading = True
        self._config_path = path

        if not path.exists():
            self._config = SSHConfig(path=path)
            self.notify(f"New file — will be created on save: {path}", title="sshconfigmgr")
        else:
            self._config = SSHConfig.from_path(path)

        self._current_entry = None
        self._modified = False
        self._rebuild_list()
        self._update_title()
        self._show_empty()
        self._loading = False

        # Select first entry if any
        if self._config.entries:
            lv = self.query_one("#host-list", HostListView)
            lv.index = 0

    def _rebuild_list(self) -> None:
        lv = self.query_one("#host-list", HostListView)
        lv.clear()
        for entry in self._config.entries:
            lv.append(ListItem(Label(entry.pattern)))

    def _update_title(self) -> None:
        mod = " (unsaved)" if self._modified else ""
        self.sub_title = f"{self._config_path}{mod}"

    def _mark_modified(self) -> None:
        if not self._modified:
            self._modified = True
            self._update_title()

    # ── Editor ───────────────────────────────────────────────────────────────

    def _show_empty(self) -> None:
        self.query_one("#empty-msg").display = True
        self.query_one("#add-field").display = False
        self.query_one("#editor-header", Static).update("")
        for row in self.query(ParamRow):
            row.remove()

    def _load_entry(self, entry: HostEntry) -> None:
        self._loading_entry = True
        self._current_entry = entry
        self.query_one("#editor-header", Static).update(f"  Host {entry.pattern}")
        for row in self.query(ParamRow):
            row.remove()
        self.query_one("#empty-msg").display = False
        self.query_one("#add-field").display = True
        add_btn = self.query_one("#add-field")
        for key, value in entry.params:
            add_btn.parent.mount(ParamRow(key, value), before=add_btn)
        self.call_after_refresh(
            lambda: self.call_after_refresh(
                lambda: setattr(self, "_loading_entry", False)
            )
        )

    def _sync_params_to_entry(self) -> None:
        if self._current_entry is None:
            return
        params = [
            (row.key.strip(), row.value.strip())
            for row in self.query(ParamRow)
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

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        if self._loading or event.item is None:
            return
        lv = self.query_one("#host-list", HostListView)
        idx = lv.index
        if idx is None or idx >= len(self._config.entries):
            return
        new_entry = self._config.entries[idx]
        if new_entry is self._current_entry:
            return
        self._sync_params_to_entry()
        self._load_entry(new_entry)

    def on_param_row_changed(self, event: ParamRow.Changed) -> None:
        self._sync_params_to_entry()
        if not self._loading_entry:
            self._mark_modified()

    def on_param_row_delete_requested(self, event: ParamRow.DeleteRequested) -> None:
        event.row.remove()
        self._sync_params_to_entry()
        self._mark_modified()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "add-field":
            self._do_add_field()
        elif bid == "btn-new":
            self.action_new_host()
        elif bid == "btn-delete":
            self.action_delete_host()
        elif bid == "btn-save":
            self.action_save()
        elif bid == "btn-quit":
            self.action_request_quit()

    # ── Actions ──────────────────────────────────────────────────────────────

    def action_focus_list(self) -> None:
        self.query_one("#host-list", HostListView).focus()

    def action_new_host(self) -> None:
        def on_result(pattern: Optional[str]) -> None:
            if not pattern:
                return
            self._sync_params_to_entry()
            entry = self._config.add_entry(pattern)
            self._loading = True
            self._rebuild_list()
            self._loading = False
            self._load_entry(entry)
            lv = self.query_one("#host-list", HostListView)
            lv.index = len(self._config.entries) - 1
            self._mark_modified()

        self.push_screen(
            InputScreen("Host pattern (e.g. myserver, bastion, *.corp)", "New Host Entry"),
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
            self._current_entry = None
            self._config.remove_entry(entry_to_remove)
            self._loading = True
            self._rebuild_list()
            self._loading = False
            self._mark_modified()
            if self._config.entries:
                lv = self.query_one("#host-list", HostListView)
                lv.index = 0
                self._load_entry(self._config.entries[0])
            else:
                self._show_empty()

        self.push_screen(
            ConfirmScreen(f'Delete Host "{pattern}"?', "Delete Entry"),
            on_result,
        )

    def action_save(self) -> None:
        self._sync_params_to_entry()
        errors = self._validate()
        if errors:
            self.notify("\n".join(errors), title="Validation error", severity="error", timeout=6)
            return
        try:
            self._config.save()
            self._modified = False
            self._update_title()
            self.notify("Saved.", title="sshconfigmgr", timeout=2)
        except OSError as exc:
            self.notify(str(exc), title="Save failed", severity="error")

    def action_open_file(self) -> None:
        def on_path(path_str: Optional[str]) -> None:
            if not path_str:
                return
            path = Path(path_str).expanduser().resolve()
            if not path.exists():
                def on_create(confirmed: bool) -> None:
                    if confirmed:
                        self._load_config(path)

                self.push_screen(
                    ConfirmScreen(f"File not found. Create {path}?", "Open File"),
                    on_create,
                )
            else:
                self._load_config(path)

        self.push_screen(
            InputScreen("File path", "Open SSH Config", str(self._config_path)),
            on_path,
        )

    def action_request_quit(self) -> None:
        if not self._modified:
            self.exit()
            return

        def on_result(choice: Optional[str]) -> None:
            if choice == "save":
                self.action_save()
                self.exit()
            elif choice == "discard":
                self.exit()

        self.push_screen(QuitConfirmScreen(), on_result)

    def _do_add_field(self) -> None:
        if self._current_entry is None:
            return
        existing_keys = [row.key for row in self.query(ParamRow)]

        def on_keyword(keyword: Optional[str]) -> None:
            if not keyword:
                return
            add_btn = self.query_one("#add-field")
            row = ParamRow(keyword, "")
            add_btn.parent.mount(row, before=add_btn)
            self.call_after_refresh(lambda: row.query_one(".param-val", Input).focus())
            self._mark_modified()

        self.push_screen(AddFieldScreen(existing_keys), on_keyword)
