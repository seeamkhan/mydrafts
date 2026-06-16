# Terminal Theme — the "Ubuntu vibe"

The install scripts handle the **text** (colors, prompt, aliases). The
**background color and window look** can't be scripted reliably across every
terminal app, so set those by hand once per machine. It takes ~30 seconds.

The classic Ubuntu colors:

| Setting          | Value                         |
|------------------|-------------------------------|
| Background       | dark purple `#300A24`         |
| Text             | near-white `#EEEEEC`          |
| Opacity          | ~95% (slight blur, optional)  |

Prefer a modern feel? Use a deep charcoal background `#1E1E1E` instead.

---

## macOS — Terminal.app

1. **Terminal** menu → **Settings** → **Profiles**.
2. Pick a profile (e.g. **Basic**) or duplicate one.
3. **Background** color → set to `#300A24`.
4. **Opacity** slider → ~95%.
5. Click **Default** so new windows use it.

## macOS — Ghostty

Edit `~/.config/ghostty/config`:

```
background = 300a24
foreground = eeeeec
background-opacity = 0.95
```

## macOS / Linux — iTerm2

**Settings → Profiles → Colors** → set **Background** to `#300A24`.

---

## Ubuntu — GNOME Terminal

1. Open the menu (☰) → **Preferences**.
2. Select your profile → **Colors** tab.
3. Uncheck **Use colors from system theme**.
4. Set **Background** to `#300A24`, **Text** to `#EEEEEC`.
5. (Optional) **Transparent background** → ~5%.

---

## Windows — Windows Terminal

1. Open **Settings** (Ctrl+,) → your profile → **Appearance**.
2. **Color scheme** → choose one, or open `settings.json` and add:

```json
{
  "name": "Ubuntu",
  "background": "#300A24",
  "foreground": "#EEEEEC"
}
```

3. Set it as the profile's color scheme.
4. (Optional) **Transparency / Acrylic** → ~95% opacity.

> No admin needed — Windows Terminal settings are per-user.
