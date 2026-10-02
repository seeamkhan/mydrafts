# Mac-style Linux Mint XFCE on a MacBook Air (2014)

Small, lightweight tweaks that make Linux Mint XFCE (X11) behave more like macOS on MacBook hardware. They're meant to sit alongside a retro theme like Chicago95, and everything can be switched off with one click.

See [PLAN.md](PLAN.md) for the reasoning behind each choice.

## What you get

| Feature | Details | On/off |
|---|---|---|
| **Mac keyboard** (built-in keyboard only) | Cmd+C/V/X/Z/T/W… shortcuts, **Cmd+Tab** window switcher, Cmd+Space launcher, Cmd+←/→ line start/end. Ctrl stays real Ctrl. | `macmode` |
| **Mac-style terminal** (xfce4-terminal) | Cmd+C/V copy/paste, Cmd+T/W/N tabs and windows, Ctrl+C interrupts, **Shift+Enter inserts a newline** in Claude Code / pi | part of keyboard |
| **Three-finger drag** | select text and drag windows with 3 fingers | `macmode` |
| **4-finger gestures** | ←/→ switch workspace, ↑ window list, ↓ show desktop | `macmode` |
| F3 / F4 keys | F3 = window list, F4 = app menu | always on (xfconf) |
| Volume popup | small notification when using the volume keys | always on (xfconf) |

External keyboards are **not** remapped. They keep a normal PC layout, so games' Ctrl/Shift/Q/Tab controls work as expected.

## Files

| File | Installed to |
|---|---|
| `keyd/default.conf` | `/etc/keyd/default.conf` |
| `keyd/app.conf` | `~/.config/keyd/app.conf` (terminal-only rules) |
| `libinput/local-overrides.quirks` | `/etc/libinput/local-overrides.quirks` (keeps disable-while-typing working) |
| `macmode` | `~/.local/bin/macmode` (on/off tool, GUI + CLI) |
| `install.sh` / `uninstall.sh` | run with `sudo` |

Dependencies: [keyd](https://github.com/rvaiya/keyd) v2.6.0 (built from source), [libinput-three-finger-drag](https://github.com/marsqing/libinput-three-finger-drag) 0.2 (release binary, checksum-verified), apt packages `libxdo3` and `python3-xlib`, and touchegg (already part of Mint).

## Install

```bash
sudo ./install.sh
# then log out and back in
```

## Turning things on and off

- **GUI:** menu → Settings → **Mac Mode**. Tick what you want on; untick everything for plain PC mode (gaming, or when you need maximum performance).
- **CLI:**
  ```bash
  macmode status
  macmode off            # everything off
  macmode on keyboard    # just the keyboard back on
  macmode off drag gestures
  ```

Choices survive reboots. With the keyboard off, every keyboard is a plain PC layout (Cmd = Windows/Super key).

## Gesture config

The gesture config lives in `~/.config/touchegg/touchegg.conf` and is not installed by the script; see PLAN.md. It contains no 3-finger swipes, because those would fight with three-finger drag.

## Resource use

keyd ~1–2 MB RAM; the terminal-rules helper ~15–25 MB; the drag helper a few MB. CPU use is effectively zero when idle.

## Troubleshooting

- **Shift+Enter still submits in some app:** in `~/.config/keyd/app.conf` change `shift.enter = A-enter` to `shift.enter = C-j`. The mapper reloads the file automatically.
- **Three-finger drag too slow/fast:** edit `DRAG_SPEED` near the top of `~/.local/bin/macmode`, then run `macmode off drag && macmode on drag`.
- **See which window class the terminal rules match:** `tail -f ~/.config/keyd/app.log`.
- **Keyboard acting weird:** `macmode off keyboard` gives an instant plain layout.

## Undo everything

```bash
sudo ./uninstall.sh   # restores the previous setxkbmap Cmd/Ctrl swap
```
