"""
Webex Live CC Transcript Capture
---------------------------------
Reads the Webex CC/caption panel using Windows UI Automation.
No admin needed. No audio. No security flags.
Writes transcript to transcripts/transcript_YYYY-MM-DD_HH-MM.md

BEFORE FIRST RUN:
1. Open Webex, join a meeting, enable Live Captions (CC button).
2. Run `python find_window.py` to discover the caption control. Look under
   "CAPTION-LIKE DESCENDANTS" in the output.
3. If the keywords below don't match what you saw, add one.
4. Run: `python capture.py`
"""

import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import datetime
import os
import time
from collections import deque

import uiautomation as auto

# ─────────────────────────────────────────────
# ⚙️  CONFIGURE THESE after running find_window.py
# ─────────────────────────────────────────────

# Preferred keywords — we look for a *descendant* control whose Name,
# AutomationId, or ClassName contains one of these. Order matters: more
# specific first.
CC_KEYWORDS = [
    "closed caption",
    "live caption",
    "caption",
    "subtitle",
    "cc",
]

# Top-level windows we are willing to search inside.
WEBEX_WINDOW_KEYWORDS = ["webex", "cisco"]

POLL_INTERVAL_SECONDS = 2       # how often to check for new text
DEDUP_BUFFER_SIZE = 200         # last N lines remembered (exact-match dedup)
MAX_SEARCH_DEPTH = 8            # how deep we walk the UI tree
OUTPUT_DIR = "transcripts"

# ─────────────────────────────────────────────


def _name_blob(ctrl):
    name = (ctrl.Name or "").lower()
    class_name = (ctrl.ClassName or "").lower()
    auto_id = (ctrl.AutomationId or "").lower()
    return f"{name} {class_name} {auto_id}"


def _find_cc_descendant(ctrl, depth=0):
    """DFS for a descendant whose name/id/class contains any CC keyword."""
    if depth > MAX_SEARCH_DEPTH:
        return None
    try:
        blob = _name_blob(ctrl)
        for kw in CC_KEYWORDS:
            if kw in blob:
                return ctrl
        for child in ctrl.GetChildren():
            found = _find_cc_descendant(child, depth + 1)
            if found is not None:
                return found
    except Exception:
        pass
    return None


def find_cc_control():
    """
    Find the CC panel. Strategy:
      1. Enumerate top-level Webex/Cisco windows.
      2. For each, recursively look for a descendant with a CC keyword.
      3. Return the first specific match. Don't fall back to the whole
         Webex window — extracting every button/label from it produces
         noise, not a transcript.
    """
    desktop = auto.GetRootControl()
    for top in desktop.GetChildren():
        top_name = (top.Name or "").lower()
        if not any(k in top_name for k in WEBEX_WINDOW_KEYWORDS):
            continue
        cc = _find_cc_descendant(top)
        if cc is not None:
            return cc
    return None


def extract_text_from_control(ctrl):
    """Recursively collect visible text from a control and its descendants."""
    texts = []

    def walk(c, depth=0):
        if depth > MAX_SEARCH_DEPTH:
            return
        try:
            if c.Name and c.Name.strip():
                texts.append(c.Name.strip())
            for child in c.GetChildren():
                walk(child, depth + 1)
        except Exception:
            pass

    walk(ctrl)
    return texts


def looks_like_transcript_line(text):
    """Filter obvious UI chrome. Keep almost everything else."""
    if len(text) < 2:
        return False
    lower = text.strip().lower()
    noise = {
        "close", "minimize", "maximize", "settings", "webex", "cisco",
        "button", "panel", "captions", "subtitles", "live captions",
        "closed captions", "cc", "on", "off", "mute", "unmute",
    }
    if lower in noise:
        return False
    return True


def make_output_path(output_dir):
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M")
    return os.path.join(output_dir, f"transcript_{timestamp}.md")


def _append_lines(path, new_lines):
    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
    with open(path, "a", encoding="utf-8") as f:
        for line in new_lines:
            f.write(f"**[{timestamp}]** {line}\n\n")
            print(f"[{timestamp}] {line}")


def run_capture():
    output_path = make_output_path(OUTPUT_DIR)
    seen = deque(maxlen=DEDUP_BUFFER_SIZE)
    seen_set = set()            # fast lookup alongside the deque
    line_count = 0
    matched_ctrl_desc = None    # printed once so user can verify

    print("🎙️  Webex Transcript Capture")
    print(f"📄  Output: {output_path}")
    print("🔍  Looking for CC panel inside Webex window...")
    print("⏹️  Press Ctrl+C to stop.\n")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("# Webex Transcript\n")
        f.write(f"**Date:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n")
        f.write("---\n\n")

    while True:
        try:
            cc_ctrl = find_cc_control()

            if cc_ctrl is None:
                print("⚠️  CC panel not found. Is Webex open with Live Captions enabled?")
                time.sleep(5)
                continue

            # Announce the match once so the user can sanity-check.
            desc = f"{cc_ctrl.ControlTypeName} Name={cc_ctrl.Name!r} AutoID={cc_ctrl.AutomationId!r}"
            if desc != matched_ctrl_desc:
                print(f"✅ Matched CC control: {desc}\n")
                matched_ctrl_desc = desc

            all_texts = extract_text_from_control(cc_ctrl)
            new_lines = []

            for text in all_texts:
                if not looks_like_transcript_line(text):
                    continue
                if text in seen_set:
                    continue
                if len(seen) == seen.maxlen:
                    # deque will drop the oldest; mirror that in the set.
                    seen_set.discard(seen[0])
                seen.append(text)
                seen_set.add(text)
                new_lines.append(text)

            if new_lines:
                _append_lines(output_path, new_lines)
                line_count += len(new_lines)

            time.sleep(POLL_INTERVAL_SECONDS)

        except KeyboardInterrupt:
            print(f"\n✅ Stopped. {line_count} lines captured.")
            print(f"📄 Saved to: {output_path}")
            break
        except Exception as e:
            print(f"❌ Error: {e}")
            time.sleep(3)


if __name__ == "__main__":
    run_capture()
