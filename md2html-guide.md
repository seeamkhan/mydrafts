# md2html — Usage Guide

Converts any `.md` file into a clean, self-contained `.html` file.
Renders tables, task checkboxes (with browser-side persistence), and code blocks.

---

## Prerequisites: install `uv`

`uv` is a fast Python package runner. It auto-installs the script's dependencies — no venv or pip needed.

| OS | Install command |
|----|-----------------|
| **Mac / Linux** | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| **Windows (PowerShell)** | `powershell -c "irm https://astral.sh/uv/install.ps1 \| iex"` |

After installing, restart your terminal (or run `source ~/.bashrc` / `source ~/.zshrc`).

Verify: `uv --version`

---

## Step 1 — get the script

### Option A: clone the repo (recommended)

```bash
git clone https://github.com/seeamkhan/mydrafts.git
```

The script is at `mydrafts/md2html`.

### Option B: download just the file

```bash
# Mac / Linux
curl -O https://raw.githubusercontent.com/seeamkhan/mydrafts/main/md2html

# Windows (PowerShell)
Invoke-WebRequest -Uri "https://raw.githubusercontent.com/seeamkhan/mydrafts/main/md2html" -OutFile "md2html"
```

---

## Step 2 — put it on your PATH

### Mac / Linux

```bash
cp md2html ~/.local/bin/md2html
chmod +x ~/.local/bin/md2html
```

Make sure `~/.local/bin` is in your PATH (add to `~/.zshrc` or `~/.bashrc` if not):

```bash
export PATH="$HOME/.local/bin:$PATH"
```

Then reload: `source ~/.zshrc` (or open a new terminal).

### Windows

1. Copy `md2html` to a folder you control, e.g. `C:\Users\you\tools\`
2. Add that folder to your `PATH`:
   - Search "Edit environment variables" in Start
   - Under "User variables" → `Path` → Edit → New → paste the folder path
3. Rename the file to `md2html.py` if you want to call it as `python md2html.py` instead

> **Windows note:** the shebang line (`#!/usr/bin/env -S uv run --script`) is ignored on Windows.
> Run it as: `uv run md2html` or `python md2html` (with `uv` handling deps automatically).

---

## Step 3 — use it

```bash
# Basic: creates document.html next to document.md
md2html document.md

# Custom output path
md2html document.md /path/to/output.html
```

### Windows equivalent

```powershell
uv run md2html document.md
uv run md2html document.md output.html
```

---

## What the output looks like

- Clean GitHub-style typography
- Tables with alternating row shading
- Task checkboxes (`- [ ]` / `- [x]`) rendered as real HTML checkboxes
  - Checkbox state is saved in the browser's `localStorage` per page title
  - Never touches your `.md` file
- Syntax-highlighted code blocks
- In-page anchor links on all headings

---

## Updating

```bash
cd mydrafts
git pull
cp md2html ~/.local/bin/md2html   # Mac/Linux
```

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `command not found: md2html` | Check `~/.local/bin` is in PATH, then reopen terminal |
| `command not found: uv` | Re-run the uv install command above |
| Windows: script doesn't run | Use `uv run md2html yourfile.md` |
| Output missing tables | Make sure `.md` uses `|` pipe-style tables |
