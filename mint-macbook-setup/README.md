# Mac-style Linux Mint XFCE on a MacBook Air (2014)

Small, lightweight tweaks that make Linux Mint XFCE (X11) behave more like macOS on MacBook hardware. They're meant to sit alongside a retro theme like Chicago95, and everything can be switched off with one click.

See [PLAN.md](PLAN.md) for the reasoning behind each choice.

## What you get

| Feature | Details | On/off |
|---|---|---|
| **Mac keyboard** (built-in keyboard only) | Cmd+C/V/X/Z/T/W… shortcuts, **Cmd+Tab** window switcher, Cmd+Space launcher, Cmd+←/→ line start/end. Ctrl stays real Ctrl. | `macmode` |
| **Three-finger drag** | select text and drag windows with 3 fingers | `macmode` |
| **4-finger gestures** | ←/→ switch workspace, ↑ window list, ↓ show desktop | `macmode` |
| F3 / F4 keys | F3 = window list, F4 = app menu | always on (xfconf) |
| Volume popup | small notification when using the volume keys | always on (xfconf) |

External keyboards are **not** remapped. They keep a normal PC layout, so games' Ctrl/Shift/Q/Tab controls work as expected.

## Files

| File | Installed to |
|---|---|
| `keyd/default.conf` | `/etc/keyd/default.conf` |
| `libinput/local-overrides.quirks` | `/etc/libinput/local-overrides.quirks` (keeps disable-while-typing working) |
| `macmode` | `~/.local/bin/macmode` (on/off tool, GUI + CLI) |
| `install.sh` / `uninstall.sh` | run with `sudo` |

Dependencies: [keyd](https://github.com/rvaiya/keyd) v2.6.0 (built from source), [libinput-three-finger-drag](https://github.com/marsqing/libinput-three-finger-drag) 0.2 (release binary, checksum-verified), apt package `libxdo3`, and touchegg (already part of Mint).

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

## In the terminal

There are no terminal-specific rules (the per-app helper that provided them cost ~11% CPU constantly; see PLAN.md), so in xfce4-terminal Cmd behaves exactly like Ctrl:

- Copy / paste: **Cmd+Shift+C / Cmd+Shift+V** (the usual Linux terminal keys). Cmd+C or Ctrl+C interrupts.
- New line without sending in Claude Code: **Option+Enter** (or Ctrl+J). xfce4-terminal sends the same byte for Shift+Enter and Enter, so Shift+Enter can't be told apart.

## Gesture config

The gesture config lives in `~/.config/touchegg/touchegg.conf` and is not installed by the script; see PLAN.md. It contains no 3-finger swipes, because those would fight with three-finger drag.

## Resource use

keyd ~1–2 MB RAM and ~0% CPU; the drag helper a few MB. CPU use is effectively zero when idle.

## Troubleshooting

- **Three-finger drag too slow/fast:** edit `DRAG_SPEED` near the top of `~/.local/bin/macmode`, then run `macmode off drag && macmode on drag`.
- **Keyboard acting weird:** `macmode off keyboard` gives an instant plain layout.
- **Trackpad dead after installing keyd:** keyd grabbed it. The keyboard and trackpad share the `05ac:0291` id, so `[ids]` must list the keyboard's full id (`sudo keyd monitor` shows it), not `05ac:0291` or `k:05ac:0291`. `sudo journalctl -u keyd` should show `bcm5974` as *ignoring*.

## Undo everything

```bash
sudo ./uninstall.sh   # restores the previous setxkbmap Cmd/Ctrl swap
```
