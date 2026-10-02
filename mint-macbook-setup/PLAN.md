# MacBook Air 2014 + Linux Mint XFCE (Chicago95): fix-up plan

Status: **approved and implemented.** See [README.md](README.md) for install, on/off and undo.

Extra fix found along the way: bitmap fonts that came with the theme (`cronyx-cyrillic`) claim the family name "Helvetica". Chrome picked them and drew **invisible text** on any page asking for Helvetica. They were moved out of `~/.fonts` into the backup folder.

## What I checked (2026-10-02)

| Item | Current state |
|---|---|
| OS / desktop | Linux Mint 22.3, XFCE 4.18, X11, kernel 7.0 |
| Cmd/Ctrl swap | autostart `~/.config/autostart/Swap Cmd and Ctrl.desktop` runs `setxkbmap -option ctrl:swap_lwin_lctl -option ctrl:swap_rwin_rctl` |
| Window switching | xfwm4: `Alt+Tab` = cycle windows, `Super+Tab` = switch window |
| Terminal | xfce4-terminal 1.1.3 |
| Touchpad | `bcm5974` + libinput **1.25** (`/etc/X11/xorg.conf.d/30-touchpad.conf`) |
| Gestures | touchegg 2.0.18 daemon and client both running, **no user config** (uses `/usr/share/touchegg/touchegg.conf` defaults) |
| Volume keys | handled by the panel PulseAudio plugin, `show-notifications = false` |
| F3 / F4 | the keys reach X as `XF86LaunchA` / `XF86LaunchB`, but nothing is bound to them |
| Notifications | xfce4-notifyd running |

## How the keyboard works today (your "like Windows?" question)

After the swap:

- **Cmd → Ctrl**. So Cmd works like Ctrl on a Windows PC: Cmd+C/V/X/Z/T/W all work in normal apps.
- **Physical Ctrl → Super (the Windows key)**. Tapping it alone opens the Whisker menu, and physical Ctrl+Tab is the xfwm4 `Super+Tab` switcher.
- **Option → Alt**, which is why Alt/Option+Tab is the switcher.
- **Terminal:** Cmd+C = **interrupt (SIGINT)**, Cmd+Shift+C = copy, Cmd+Shift+V = paste. That's the normal Windows/Linux terminal convention. Your physical Ctrl key does nothing useful in the terminal because it's now Super.

So nothing is actually broken. You never need a "real Ctrl" the way macOS sometimes does, because Cmd *is* Ctrl now. The one real cost is the terminal: copy needs Shift, and Cmd+C kills the running command instead of copying.

`setxkbmap` can't fix Cmd+Tab: Cmd *is* Ctrl now, so binding Cmd+Tab means binding Ctrl+Tab, which browsers and editors use for switching tabs.

---

## Part 1: Keyboard (Cmd+Tab, Ctrl behaviour, Shift+Enter)

### Option A (recommended): `keyd`, a true Mac-style remap

`keyd` is a small C daemon (~100 KB) that remaps at the kernel input level. It isn't in Mint 22's apt repos, so I'd build it from the official source (gcc/make/git are already installed) and run it as a systemd service. It **replaces** the setxkbmap autostart.

Layout:

| Physical key | Result |
|---|---|
| Cmd + letter | Ctrl + letter (copy/paste/new tab/etc. as now) |
| **Cmd + Tab** | **Alt+Tab window switcher.** Hold Cmd and press Tab repeatedly, like macOS. Cmd+Shift+Tab goes backwards |
| Cmd + ` | cycle windows of the same app (if xfwm4 allows it; optional) |
| Cmd + Space | open app launcher (Whisker menu) |
| **Ctrl** | **real Ctrl again.** Ctrl+C in the terminal interrupts, like on a Mac |
| Option | Alt (unchanged) |

Terminal-only rules (keyd's small `keyd-application-mapper` helper, which switches rules based on the focused window):

| In xfce4-terminal | Result |
|---|---|
| Cmd+C / Cmd+V | copy / paste (Ctrl+Shift+C/V), Mac-like |
| Ctrl+C | interrupt (real Ctrl) |
| **Shift+Enter** | **new line without sending** (sends `Ctrl+J` or `Alt+Enter`; I'll test which one both Claude Code and pi treat as a newline) |

Side effects I'll handle:
- libinput's "disable touchpad while typing" stops recognising keyboards behind keyd. I'll fix that with a one-line libinput quirk that marks the keyd virtual keyboard as internal.
- keyd only applies to the internal Apple keyboard (`05ac:0291`). External keyboards stay a normal PC layout (see Decisions).
- Easy undo: `sudo systemctl disable --now keyd`, then re-enable the old autostart entry.

### Option B: minimal, no new software

- Keep the swap. Rebind xfwm4 so `Ctrl+Tab` (= physical Cmd+Tab) cycles windows.
- **Cost:** Ctrl+Tab stops switching browser and editor tabs (Ctrl+PageUp/PageDown still work).
- **Shift+Enter can't be fixed in xfce4-terminal this way**, because it sends exactly the same byte as Enter and has no setting to change that. You'd have to:
  - use the built-in alternatives (`Ctrl+J`, or `\` then Enter in Claude Code), **or**
  - switch to `xterm` (very light, needs `apt install xterm`), which can be told to send a distinct Shift+Enter sequence.

**My recommendation is A.** It's the only option that gives you Cmd+Tab *and* browser Ctrl+Tab *and* Shift+Enter while keeping xfce4-terminal.

---

## Part 2: F3 / F4 keys (window switcher / launcher)

They already send `XF86LaunchA` (F3, Mission Control) and `XF86LaunchB` (F4, Launchpad). I'll confirm with `xev` (you press each key once) and then bind them in XFCE Keyboard → Application Shortcuts:

- **F3 → window list** (`xfdesktop --windowlist`). It's a Win95-style menu of all open windows, so it matches Chicago95 and costs nothing.
- **F4 → app launcher** (`xfce4-popup-whiskermenu`, or `xfce4-appfinder` if you prefer).

(A real Mac-style "Exposé" exists, `skippy-xd` or `xfdashboard`, but both need compositing and are heavier. Skipping unless you want it.)

## Part 3: Volume on-screen popup

One setting: `xfconf-query -c xfce4-panel -p /plugins/plugin-12/show-notifications -s true`. Volume keys then show a small notification bubble with the level. If the bubble looks ugly with Chicago95, I'll leave it off.

## Part 4: Trackpad

### 4-finger swipe
touchegg is running, and its defaults say 4-finger up/down should switch workspace, so something is blocking it. Steps:
1. Diagnose: you swipe with 4 fingers while I watch `libinput debug-events` (needs `sudo`). That shows whether the trackpad reports 4-finger gestures at all (the bcm5974 driver should).
2. Write a Mac-style `~/.config/touchegg/touchegg.conf`:
   - 4 fingers left/right → previous/next workspace
   - 4 fingers up → window list (same as F3)
   - 4 fingers down → show desktop
   - 2-finger pinch in browsers → zoom (kept from the defaults)
3. Restart the touchegg client and test.

### 3-finger drag ("3 finger select")
- libinput only got native 3-finger drag in version **1.27**. Mint 22 ships **1.25**, and upgrading libinput system-wide is risky.
- Plan: install **`libinput-three-finger-drag`**, a small open-source helper that turns a 3-finger move into click-and-drag. It's a single binary. I'll check the project and its release before installing.
  - It needs your user in the `input` group so it can read the trackpad. Small tradeoff: programs you run can then read raw input devices. That's normal on a single-user laptop.
  - Autostarts with the session.
- **Conflict:** touchegg's default 3-finger swipes (maximize/minimize/tile) and 3-finger pinch fight with 3-finger drag, so I'll **remove all 3-finger gestures** from the touchegg config. 3 fingers = drag, 4 fingers = gestures, the same split as macOS.
- Tap-to-click and 2-finger right-click stay as they are.

## Already fine, not touching
- Screen brightness keys
- Keyboard backlight (F5/F6)
- Tap to click, 2-finger tap right-click

---

## Order of work, safety, and undo

1. Back up every file I touch into `~/mint-macbook-backup-<date>/` (autostart entry, xfconf keyboard and panel channels, touchegg config, xorg/libinput files).
2. Part 3 (volume popup). Trivial.
3. Part 2 (F3/F4). Needs one `xev` key press from you.
4. Part 1 (keyboard). Option A needs `sudo` for `make install` and the systemd service. After this, **log out and back in** once.
5. Part 4 (trackpad). Needs `sudo` (input group, libinput debug) and a log out/in for the group change.
6. Write `mint-macbook-setup/README.md` with what was changed, the final key map, and undo steps for each part.

Things that need you physically at the keyboard: pressing F3/F4 for `xev`, swiping 4 fingers for the diagnosis, typing the `sudo` password, and logging out/in.

## Decisions (approved)

1. **Keyboard:** Option A, keyd.
2. **F3 / F4:** window list + Whisker menu.
3. **3-finger drag:** add the helper; user joins the `input` group.
4. **External keyboards:** **built-in keyboard only.** External keyboards stay a plain PC layout. This matters for games, which use Left Ctrl (e.g. sprint), Shift, Q, Tab:
   - Today the `setxkbmap` swap applies to **every** keyboard. On an external keyboard, Ctrl currently sends the Windows key, which breaks Ctrl-based game controls and can pop up the start menu mid-game. Removing the swap fixes that.
   - On the built-in keyboard, physical Ctrl becomes real Ctrl again, so Ctrl game controls work there too.
   - Dropped the `Cmd+Q → Alt+F4` idea. `Cmd+Q` just sends `Ctrl+Q`, which already quits most Linux apps and won't force-close a game window.

## Resource cost (estimates; measure after install)

| Component | RAM | CPU |
|---|---|---|
| `keyd` daemon (C) | ~1–2 MB | ~0%: sleeps until a key is pressed, microseconds per key, no noticeable latency |
| `keyd-application-mapper` (Python, terminal-only rules) | ~15–25 MB | ~0%: wakes only when window focus changes |
| 3-finger-drag helper | a few MB | small, only while fingers are on the trackpad |
| Removed: `setxkbmap` autostart | – | – |

Total ≈ 20–30 MB, on a machine with 3.8 GB RAM (~1.8 GB free at the time of checking).
