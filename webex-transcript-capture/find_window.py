"""
Run this while the Webex CC / Live Captions panel is visible on screen.

It prints:
  1. All top-level windows
  2. Any Webex/Cisco window, with a recursive tree of its descendants
  3. Any descendant control (at any depth) whose name/AutomationId/ClassName
     contains caption/subtitle/cc keywords

You are looking for a descendant control whose Name or AutomationId contains
"caption", "subtitle", or "cc". That is almost always the panel we want.
Copy its Name keyword (or AutomationId) and paste into capture.py's
CC_WINDOW_TITLE_KEYWORDS if needed.
"""

import sys

try:
    # Make emojis/unicode safe on legacy Windows consoles.
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import uiautomation as auto


CC_KEYWORDS = ("caption", "subtitle", "cc", "live caption", "closed caption")
WEBEX_KEYWORDS = ("webex", "cisco")
MAX_DEPTH = 8


def _props(ctrl):
    name = ctrl.Name or ""
    class_name = ctrl.ClassName or ""
    auto_id = ctrl.AutomationId or ""
    ctrl_type = ctrl.ControlTypeName or ""
    return name, class_name, auto_id, ctrl_type


def list_all_windows():
    print("=== TOP LEVEL WINDOWS ===\n")
    desktop = auto.GetRootControl()
    for ctrl in desktop.GetChildren():
        name, class_name, auto_id, _ = _props(ctrl)
        print(f"Name: {name!r:50} | Class: {class_name!r:40} | AutoID: {auto_id!r}")


def print_tree(ctrl, depth=0, max_depth=MAX_DEPTH):
    if depth > max_depth:
        return
    indent = "  " * depth
    name, class_name, auto_id, ctrl_type = _props(ctrl)
    print(f"{indent}[{ctrl_type}] Name={name!r:40} Class={class_name!r:30} AutoID={auto_id!r}")
    try:
        for child in ctrl.GetChildren():
            print_tree(child, depth + 1, max_depth)
    except Exception:
        pass


def deep_search_webex():
    print("\n=== WEBEX/CISCO WINDOWS (full tree) ===\n")
    desktop = auto.GetRootControl()
    found_any = False
    for ctrl in desktop.GetChildren():
        name = (ctrl.Name or "").lower()
        if any(k in name for k in WEBEX_KEYWORDS):
            found_any = True
            print(f"\n>>> WEBEX WINDOW: {ctrl.Name!r}")
            print_tree(ctrl)
    if not found_any:
        print("(no top-level window with 'webex' or 'cisco' in the title)")


def _matches_cc(ctrl):
    name, class_name, auto_id, _ = _props(ctrl)
    blob = f"{name} {class_name} {auto_id}".lower()
    return any(k in blob for k in CC_KEYWORDS)


def find_caption_descendants():
    """Walk the entire accessibility tree and print every control that looks caption-ish."""
    print("\n=== CAPTION-LIKE DESCENDANTS (anywhere on the desktop) ===\n")
    desktop = auto.GetRootControl()
    hits = []

    def walk(ctrl, depth):
        if depth > MAX_DEPTH:
            return
        try:
            if _matches_cc(ctrl):
                hits.append((depth, ctrl))
            for child in ctrl.GetChildren():
                walk(child, depth + 1)
        except Exception:
            pass

    # Only descend into Webex/Cisco top-level windows — descending the entire
    # desktop is slow and noisy.
    for top in desktop.GetChildren():
        tname = (top.Name or "").lower()
        if any(k in tname for k in WEBEX_KEYWORDS):
            walk(top, 0)

    if not hits:
        print("(no caption-like controls found inside Webex windows)")
        print("If CC is on-screen but nothing shows here, Webex may be rendering")
        print("captions on a canvas/HTML element. Fall back to the OCR plan (see README).")
        return

    for depth, ctrl in hits:
        name, class_name, auto_id, ctrl_type = _props(ctrl)
        indent = "  " * depth
        print(f"{indent}[{ctrl_type}] Name={name!r} Class={class_name!r} AutoID={auto_id!r}")


if __name__ == "__main__":
    list_all_windows()
    deep_search_webex()
    find_caption_descendants()
    print("\nDone. If you found a caption-like control, note its Name keyword")
    print("and (if needed) update CC_WINDOW_TITLE_KEYWORDS in capture.py.")
    input("Press Enter to exit...")
