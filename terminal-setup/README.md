# Unified Terminal Setup

Make every machine you use — **macOS**, **Ubuntu/Linux**, and **Windows** —
look and feel the *same*: the same colored prompt, the same git-branch
indicator, the same aliases, and the same project-folder layout.

This started as a pile of scattered terminal tips. It's now one tidy,
reusable setup you can drop onto any new machine.

> **Standalone tool.** This folder is self-contained and unrelated to anything
> else in the repo. You can copy just this `terminal-setup/` folder anywhere.

---

## What you get

| Feature | Looks like |
|---------|-----------|
| Colored prompt | `seeam@laptop:~/src/myrepo (main)$` |
| Prompt colors | user@host **green** · path **blue** · git branch **yellow** |
| Colorized `ls` | folders/files colored, same on every OS |
| Aliases | `ll` (detailed list), `la` (hidden), `l` (short), `..`, `...` |
| Git shortcuts | `gs` = status, `gb` = branch, `gl` = pretty log |
| `ghp` shortcut | jumps to your projects folder (`ghp myrepo` jumps into a repo) |
| Folder layout | `~/src/github.com/<username>/` for all your repos |

No admin / root / `sudo` is required on **any** of the three OSes. Everything
is written into your own user config files.

---

## Quick start (one click)

> First, get the files onto the machine — clone the repo, or just copy the
> `terminal-setup/` folder over.

### macOS and Ubuntu/Linux

```bash
cd terminal-setup
bash install.sh
source ~/.zshrc     # macOS   (or:  source ~/.bashrc  on Ubuntu)
```

Using a different GitHub username? Pass it in:

```bash
GH_USER=yourname bash install.sh
```

### Windows (PowerShell — no admin)

```powershell
cd terminal-setup
./install.ps1
# then open a NEW PowerShell window
```

That's it. Open a fresh terminal and you'll see the new prompt. `cd` into any
git repo and the branch shows up in yellow.

---

## What the installer does

It's deliberately boring and safe:

1. **Backs up** your shell config (`~/.zshrc`, `~/.bashrc`, or PowerShell
   `$PROFILE`) before changing anything.
2. Adds the config inside a clearly-marked block:
   `# >>> unified-shell >>>` … `# <<< unified-shell <<<`.
3. Is **idempotent** — run it as many times as you want; it never duplicates
   itself.
4. Creates `~/src/github.com/<username>/`.

To change your username later, edit the `GH_USER` line in your shell config
(or the `$GHUser` variable at the top of the Windows profile) and reload.

---

## File map

```
terminal-setup/
├── README.md                  # you are here
├── THEMES.md                  # how to set the Ubuntu purple background per OS
├── install.sh                 # one-click installer  (macOS + Ubuntu/Linux)
├── install.ps1                # one-click installer  (Windows, no admin)
├── shell/
│   └── unified-shell.sh       # the actual zsh + bash config (auto-detects)
└── windows/
    └── profile.ps1            # the actual PowerShell config
```

The "real" config lives in **two** files — `shell/unified-shell.sh` (covers
both macOS zsh and Ubuntu bash) and `windows/profile.ps1`. Edit those if you
want to tweak behavior; the installers just place them and wire them up.

---

## The project folder layout (and `ghp`)

Your repos go in `~/src/github.com/<username>/`. Why the long path?

- **Scales cleanly** once you have lots of repos — no messy flat `~/src`.
- **Multi-account friendly** — add `~/src/github.com/work-username/` later.
- **Tool-friendly** — mirrors the repo URL; many Go/DevOps tools expect it.

`ghp` makes the long path painless:

```bash
ghp            # cd ~/src/github.com/<username>
ghp kikitalk   # cd ~/src/github.com/<username>/kikitalk
```

Moving existing projects into the structure (optional, do it once):

```bash
# macOS / Linux
mkdir -p ~/src/github.com/seeam
mv ~/src/kikitalk ~/src/github.com/seeam/
mv ~/src/maestro  ~/src/github.com/seeam/
```

---

## Manual install (if you'd rather not run a script)

Everything the installer does, by hand:

**macOS / Ubuntu** — add this to `~/.zshrc` (macOS) or `~/.bashrc` (Ubuntu):

```bash
export GH_USER="yourname"
source /path/to/terminal-setup/shell/unified-shell.sh
```

Then `source ~/.zshrc` (or `~/.bashrc`).

**Windows** — append the contents of `windows/profile.ps1` to your profile
(find it by running `echo $PROFILE`), then open a new window. You may need:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

---

## Uninstall

Delete the marked block (`# >>> unified-shell >>>` … `# <<< unified-shell <<<`)
from your shell config / PowerShell profile, or restore the `.backup.*` file
the installer made. Reload the shell.

---

## Background color / theme

The scripts cover prompt + aliases. For the full **Ubuntu purple** window look
(`#300A24`), see [THEMES.md](./THEMES.md) — quick per-OS instructions for
Terminal.app, Ghostty, iTerm2, GNOME Terminal, and Windows Terminal.
