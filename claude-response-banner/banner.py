#!/usr/bin/env python3
"""Print a start/end banner around every Claude Code response.

Wired up as two hooks:

    UserPromptSubmit -> banner.py start   (top rule, opens the block)
    Stop             -> banner.py end     (bottom rule, closes the block)

Each invocation reads the hook payload as JSON on stdin and writes a single
JSON object to stdout with a "systemMessage" field, which Claude Code renders
in the terminal.

Design rule: this script must never break a session. Any unexpected failure
exits 0 with no output, which the hook runner treats as "nothing to show".
"""

import json
import os
import sys
import tempfile
import time
from pathlib import Path

WIDTH = int(os.environ.get("CLAUDE_BANNER_WIDTH", "68"))
LABEL = os.environ.get("CLAUDE_BANNER_LABEL", "CLAUDE")
ANSI = os.environ.get("CLAUDE_BANNER_ANSI", "") not in ("", "0", "false")

# Single-column characters only -- box drawing and these glyphs are all one
# terminal cell wide, so the rules line up without a wcwidth dependency.
# Emoji are deliberately avoided: they are double-width in most terminals.
GLYPHS = {"start": "▶", "end": "■", "branch": "⎇"}
ASCII_GLYPHS = {"start": ">", "end": "#", "branch": "@"}

STYLES = {
    "heavy": {"open": "┏", "close": "┗", "fill": "━", "cap_open": "┓", "cap_close": "┛"},
    "light": {"open": "╭", "close": "╰", "fill": "─", "cap_open": "╮", "cap_close": "╯"},
    "double": {"open": "╔", "close": "╚", "fill": "═", "cap_open": "╗", "cap_close": "╝"},
    "ascii": {
        "open": "+", "close": "+", "fill": "-", "cap_open": "+", "cap_close": "+",
        "glyphs": ASCII_GLYPHS,
    },
}
STYLE = STYLES.get(os.environ.get("CLAUDE_BANNER_STYLE", "heavy"), STYLES["heavy"])
G = STYLE.get("glyphs", GLYPHS)

DIM = "\033[2m"
BOLD = "\033[1m"
RESET = "\033[0m"


def read_payload():
    """Hook input arrives as JSON on stdin. Treat anything else as empty."""
    try:
        raw = sys.stdin.read()
    except Exception:
        return {}
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def state_file(session_id):
    safe = "".join(c for c in str(session_id) if c.isalnum() or c in "-_")[:64] or "default"
    return Path(tempfile.gettempdir()) / f"claude-banner-{safe}.start"


def git_branch(cwd):
    """Read the current branch straight off disk -- no subprocess, no latency."""
    try:
        path = Path(cwd).resolve()
        for directory in [path, *path.parents]:
            dot_git = directory / ".git"
            if not dot_git.exists():
                continue
            if dot_git.is_file():
                # Worktree or submodule: ".git" is a file pointing at the real dir.
                pointer = dot_git.read_text(encoding="utf-8", errors="replace").strip()
                if not pointer.startswith("gitdir:"):
                    return None
                dot_git = Path(pointer.split(":", 1)[1].strip())
                if not dot_git.is_absolute():
                    dot_git = (directory / dot_git).resolve()
            head = (dot_git / "HEAD").read_text(encoding="utf-8", errors="replace").strip()
            if head.startswith("ref: refs/heads/"):
                return head[len("ref: refs/heads/") :]
            return head[:7] if head else None
    except Exception:
        pass
    return None


def human_duration(seconds):
    seconds = int(round(seconds))
    if seconds < 60:
        return f"{seconds}s"
    minutes, seconds = divmod(seconds, 60)
    if minutes < 60:
        return f"{minutes}m{seconds:02d}s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h{minutes:02d}m"


def ellipsize(text, limit):
    return text if len(text) <= limit else text[: max(limit - 1, 1)] + "…"


def rule(segments, opening):
    """Build one full-width rule: corner, segments, fill, end cap."""
    left = STYLE["open"] if opening else STYLE["close"]
    cap = STYLE["cap_open"] if opening else STYLE["cap_close"]
    # Room for the corner, its trailing fill char, a space either side of the
    # text, one fill char of runway, and the end cap.
    budget = WIDTH - len(left) - len(cap) - 4

    parts = [ellipsize(s, 28) for s in segments if s]
    joined = f" {STYLE['fill']} ".join(parts)
    joined = ellipsize(joined, max(budget, 1))

    head = f"{left}{STYLE['fill']} {joined} "
    fill_count = max(WIDTH - len(head) - len(cap), 1)
    line = head + STYLE["fill"] * fill_count + cap

    if ANSI:
        line = f"{DIM if not opening else BOLD}{line}{RESET}"
    return line


def emit(message):
    json.dump({"systemMessage": message, "suppressOutput": True}, sys.stdout)
    sys.stdout.write("\n")


def main():
    phase = sys.argv[1] if len(sys.argv) > 1 else "start"
    payload = read_payload()

    session_id = payload.get("session_id") or "default"
    cwd = payload.get("cwd") or os.getcwd()
    now = time.strftime("%H:%M:%S")
    marker = state_file(session_id)

    if phase == "start":
        try:
            marker.write_text(str(time.time()), encoding="utf-8")
        except Exception:
            pass

        segments = [f"{G['start']} {LABEL} START", now, Path(cwd).name or cwd]
        branch = git_branch(cwd)
        if branch:
            segments.append(f"{G['branch']} {branch}")
        emit(rule(segments, opening=True))
        return

    # phase == "end"
    elapsed = None
    try:
        started = float(marker.read_text(encoding="utf-8").strip())
        elapsed = max(time.time() - started, 0)
        marker.unlink()
    except Exception:
        # No matching start: the Stop hook also fires on /clear, /compact and
        # resume. Draw the closing rule anyway, just without a duration.
        pass

    segments = [f"{G['end']} {LABEL} END", now]
    if elapsed is not None:
        segments.append(human_duration(elapsed))
    emit(rule(segments, opening=False))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
