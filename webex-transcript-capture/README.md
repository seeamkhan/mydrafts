# Webex Transcript Capture

Captures Webex live CC (closed caption) text on locked-down Windows machines.
No admin. No audio recording. No screen recording. No security flags.

## How it works

Uses [Windows UI Automation](https://learn.microsoft.com/en-us/windows/win32/winauto/entry-uiauto-win32)
— the same accessibility API screen readers use. The script polls the Webex
caption panel every 2 seconds, reads any new text, deduplicates, and appends
to a markdown file.

No OCR. No audio taps. Just reading the text that the OS already exposes to
assistive technology.

## One-time setup

### 1. Install Python (no admin)

- Download from [python.org](https://www.python.org/downloads/)
- During install, choose **"Install for current user only"** (no admin prompt)
- Check **"Add Python to PATH"**

### 2. Create a virtual environment

Open `cmd` or PowerShell in this folder:

```
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Find the CC control (do this once)

- Open Webex and join any meeting
- Turn on **Live Captions** (CC button in meeting controls)
- With the captions visible on screen, run:

```
python find_window.py
```

Look at the output section titled **"CAPTION-LIKE DESCENDANTS"**. You should
see one or more controls whose `Name` or `AutomationId` contains `caption`,
`subtitle`, or `cc`. If it's there, you're done — `capture.py` will find it
automatically.

If nothing shows up under that section but captions are clearly on screen,
Webex is likely rendering captions on a canvas/HTML surface that doesn't
expose text via UI Automation. See **OCR fallback** below.

## Every meeting

```
venv\Scripts\activate
python capture.py
```

Transcripts are written to `transcripts/transcript_YYYY-MM-DD_HH-MM.md`.
Press **Ctrl+C** to stop.

On first match the script prints the control it latched onto, e.g.:

```
Matched CC control: PaneControl Name='Captions' AutoID='caption-panel'
```

If that doesn't look like the captions panel, rerun `find_window.py` and
add a more specific keyword to `CC_KEYWORDS` in `capture.py`.

## Troubleshooting

- **"CC panel not found"** — Captions aren't on yet, or the panel is in a
  separate popped-out window. Rerun `find_window.py` with the panel visible.
- **Duplicate lines** — Webex may be refining captions in place. Increase
  `DEDUP_BUFFER_SIZE` in `capture.py`, or accept that rolling captions
  produce a few near-duplicates.
- **Missing lines** — Drop `POLL_INTERVAL_SECONDS` to 1.
- **Garbage lines (buttons, names)** — The script latched onto a broader
  control than the CC panel. Make `CC_KEYWORDS` more specific using what
  you see in `find_window.py` output.

## OCR fallback (plan B)

Only use this if UI Automation genuinely can't see the caption text.

```
pip install mss pytesseract Pillow
```

Plus a portable [Tesseract](https://github.com/UB-Mannheim/tesseract/wiki)
install. Script for this path isn't included here — decide after confirming
UI Automation really fails on RBC's Webex build.

## Files

- `capture.py` — main transcript loop
- `find_window.py` — one-shot accessibility-tree inspector
- `requirements.txt` — single dep: `uiautomation`
- `transcripts/` — output, created on first run
