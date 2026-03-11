# sshconfigmgr

A terminal UI for managing SSH client configuration files (`~/.ssh/config`).

![sshconfigmgr screenshot](screenshot.png)

## Features

- Browse and edit all `Host` blocks in a config file from a single screen
- Add, rename, and delete host entries
- Add configuration fields with autocomplete — all `ssh_config(5)` keywords are available, filtered as you type; single-use keywords already present in the current host block are excluded
- Validates data on save (e.g. Port range)
- Preserves preamble comments and per-entry leading comments on save
- Open any SSH config file at launch or switch files at runtime
- Prompts to save, discard, or cancel on quit when there are unsaved changes

## Requirements

- Python 3.11 or later
- [pipx](https://pipx.pypa.io/) for installation (recommended)

[Textual](https://textual.textualize.io/) (≥ 0.70) is installed automatically as a dependency.

## Installation

### From GitHub (recommended)

```sh
pipx install git+https://github.com/jwhall/sshconfigmgr.git
```

### From a local clone

```sh
git clone https://github.com/jwhall/sshconfigmgr.git
pipx install ./sshconfigmgr
```

For active development, install as editable so changes to the source take effect immediately:

```sh
pipx install --editable ./sshconfigmgr
```

## Updating

```sh
pipx upgrade sshconfigmgr
```

Or, if you installed from a local editable clone, `git pull` inside the repo is sufficient — no reinstall needed.

## Usage

```sh
# Open the default SSH config
sshconfigmgr

# Open a specific config file
sshconfigmgr ~/.ssh/config.work
```

If the specified file does not exist you will be prompted to create it.

## Interface

```
┌──────────────────────────────────────────────────────────────────────┐
│ sshconfigmgr — /home/user/.ssh/config                                │
├──────────────────┬───────────────────────────────────────────────────┤
│ HOSTS            │  Host bastion                                     │
│                  │ ┌────────────────┐ ┌───────────────────────────┐  │
│  bastion         │ │ HostName       │ │ 10.0.0.1                  │  │
│  web-prod        │ └────────────────┘ └───────────────────────────┘  │
│  db-replica      │ ┌────────────────┐ ┌───────────────────────────┐  │
│                  │ │ User           │ │ admin                     │  │
│                  │ └────────────────┘ └───────────────────────────┘  │
│                  │                                                   │
│                  │  + Add Field                                      │
│                  │                                                   │
├──────────────────┤                         ┌────────┬───────┬──────┐ │
│  New Host        │                         │ Delete │ Save  │ Quit │ │
└──────────────────┴─────────────────────────┴────────┴───────┴──────┘─┘
```

### Keyboard shortcuts

| Key        | Action                              |
|------------|-------------------------------------|
| `n`        | New host entry                      |
| `d`        | Delete current host entry           |
| `Ctrl+S`   | Save                                |
| `o`        | Open a different config file        |
| `Esc`      | Return focus to the host list       |
| `q`        | Quit (prompts if unsaved changes)   |
| `j` / `k`  | Move down / up in the host list     |

### Adding a configuration field

Click **+ Add Field** or press it from the keyboard to open the field picker. Start typing a keyword name to filter the list — for example, typing `Lo` narrows it to `LocalCommand`, `LocalForward`, and `LogLevel`. Navigate with the arrow keys, or click to select. Press `Enter` to confirm, `Esc` to cancel.

Keywords that may only appear once per host block (the majority of `ssh_config(5)` directives) are removed from the list once they are already present in the current entry. Keywords that may repeat (`IdentityFile`, `LocalForward`, `RemoteForward`, `DynamicForward`, `CertificateFile`, `SendEnv`, `SetEnv`, `GlobalKnownHostsFile`) remain available.

Custom or non-standard keywords can be typed freely and accepted without selecting from the list.

## License

MIT
