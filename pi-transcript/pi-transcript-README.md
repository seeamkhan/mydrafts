# pi-transcript

CLI tool to browse and view pi agent session transcripts.

## Installation

The script is already installed as a symlink in your PATH:
- Location: `~/.local/bin/pi-transcript`
- Source: `<your-script-path>/pi-transcript`

## Usage

Run the command:
```bash
pi-transcript
```

This will:
1. List all sessions from `~/.pi/agent/sessions/`
2. Show them with timestamp, project name, and session ID
3. Let you select by number (enter the number and press Enter)
4. Convert the selected JSONL to HTML
5. Open it in your default browser
6. Exit

## Features

- Lists all pi agent sessions
- Shows readable timestamps and project names
- Converts JSONL to styled HTML with color-coded messages:
  - Blue: User messages
  - Gray: Assistant messages
  - Orange: System messages
- Opens in browser automatically
- Works without external dependencies (questionary is optional)

## Optional: Arrow Key Navigation

If you want arrow key navigation instead of numbered input:
```bash
pipx install questionary
```

Then the tool will use an interactive menu with up/down arrows.
