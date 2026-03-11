# sshconfigmgr – Development Progress

## v0.1.0 – Initial release

Functional TUI built with [Textual](https://textual.textualize.io/) (≥ 0.70, tested on 8.1.1 via linuxbrew).

- Parse and write `~/.ssh/config` (or any path supplied on the CLI) via `ssh_config.py`
- Sidebar list of `Host` blocks with vim-style `j`/`k` navigation
- Right-hand editor with per-parameter key/value rows and delete buttons
- Add / delete host entries, add / remove parameters
- Inline validation (Port range check)
- Save (`ctrl+s`) and open-file (`o`) keybindings
- Footer key-hint bar

---

## v0.2.0 – UX improvements

### Title bar — app name + file + unsaved indicator

`SSHConfigApp.TITLE` is now `"SSH Client Configuration Manager"`.
`sub_title` is updated on every load/save to `<path>` or `<path> (unsaved)` so the
Textual `Header` widget displays:

```
SSH Client Configuration Manager – /home/jwhall/.ssh/config (unsaved)
```

### Quit button with Save / Discard / Cancel dialog

A **Quit** button was added to the action bar alongside New Host, Delete, and Save.
Pressing it (or the `q` keybinding) when there are unsaved changes opens a new
`QuitConfirmScreen` modal offering three choices:

| Button | Behaviour |
|--------|-----------|
| **Save & Quit** | Saves the file then exits |
| **Discard** | Exits without saving |
| **Cancel** | Returns to the editor |

### Autocomplete for Add Field

Clicking **+ Add Field** now opens an `AddFieldScreen` modal instead of inserting
a blank row.  The modal contains:

- A live-filtered **Input** — typing narrows the suggestion list instantly
- A scrollable **ListView** of matching SSH config keywords (all keywords from
  `ssh_config(5)` are included)
- Keyboard workflow: type in the Input → `↓` to move into the list → `↑` from
  the top of the list returns focus to the Input → `Enter` or click to confirm
- Only keywords that may appear **multiple times** per host (`IdentityFile`,
  `LocalForward`, `RemoteForward`, `DynamicForward`, `CertificateFile`,
  `SendEnv`, `SetEnv`, `GlobalKnownHostsFile`) remain available after the first
  use.  All other single-instance keywords are **hidden from the list** once they
  are already present in the current host block.
- Arbitrary/custom keyword names can still be entered by typing freely and
  pressing Enter when no exact match is selected.
- After a keyword is confirmed the cursor moves to the **value** field of the new
  row so the user can type the value without further clicks.
