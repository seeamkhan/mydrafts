#!/usr/bin/env python3
"""
pi-transcript - CLI tool to browse and view pi agent session transcripts.
Lists sessions from ~/.pi/agent/sessions/, lets user select with arrow keys,
converts selected JSONL to HTML, and opens in browser.
"""

import html
import json
import os
import platform
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from tempfile import NamedTemporaryFile

# Try to use questionary for arrow key navigation, fall back to numbered input
try:
    import questionary
    USE_QUESTIONARY = True
except ImportError:
    USE_QUESTIONARY = False


SESSIONS_DIR = Path.home() / ".pi" / "agent" / "sessions"


def get_downloads_folder():
    """Get the Downloads folder path cross-platform."""
    home = Path.home()
    system = platform.system()

    if system == "Darwin":  # macOS
        return home / "Downloads"
    elif system == "Windows":
        return home / "Downloads"
    elif system == "Linux":
        # Try common Linux download locations
        for downloads_path in [
            home / "Downloads",
            home / "downloads",
            Path("/mnt/c/Users") / os.environ.get("USERNAME", "") / "Downloads",  # WSL
        ]:
            if downloads_path.exists():
                return downloads_path
        return home / "Downloads"  # Fallback
    else:
        return home / "Downloads"  # Default fallback


def open_in_browser(file_path):
    """Open file in default browser cross-platform."""
    system = platform.system()
    try:
        if system == "Darwin":  # macOS
            subprocess.run(["open", file_path])
        elif system == "Windows":
            os.startfile(file_path)  # type: ignore[attr-defined]
        elif system == "Linux":
            subprocess.run(["xdg-open", file_path])
        else:
            print(f"Unsupported platform: {system}")
            print(f"File saved to: {file_path}")
    except Exception as e:
        print(f"Could not open browser: {e}")
        print(f"File saved to: {file_path}")


def get_session_dirs():
    """Get all session directories."""
    if not SESSIONS_DIR.exists():
        print(f"Sessions directory not found: {SESSIONS_DIR}")
        sys.exit(1)
    return [d for d in SESSIONS_DIR.iterdir() if d.is_dir()]


def get_session_files(session_dir):
    """Get all JSONL files in a session directory."""
    return sorted(session_dir.glob("*.jsonl"), reverse=True)


def parse_session_info(file_path):
    """Parse session info from JSONL file to extract metadata."""
    try:
        with open(file_path, "r") as f:
            for line in f:
                if line.strip():
                    data = json.loads(line)
                    if data.get("type") == "session":
                        timestamp = data.get("timestamp", "")
                        session_id = data.get("id", "")
                        cwd = data.get("cwd", "")
                        return {
                            "timestamp": timestamp,
                            "session_id": session_id,
                            "cwd": cwd,
                        }
    except Exception as e:
        pass
    return {"timestamp": "", "session_id": "", "cwd": ""}


def format_timestamp(ts):
    """Format ISO timestamp to readable format."""
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except:
        return ts


def get_session_choices():
    """Build list of choices for the interactive menu."""
    choices = []
    session_dirs = get_session_dirs()
    counter = 1

    for session_dir in sorted(session_dirs, reverse=True):
        files = get_session_files(session_dir)
        for file_path in files:
            info = parse_session_info(file_path)
            ts = format_timestamp(info["timestamp"])
            name = file_path.name.replace(".jsonl", "")
            cwd_short = info["cwd"].split("/")[-1] if info["cwd"] else "unknown"

            label = f"{counter}. {ts} | {cwd_short} | {name[:30]}"
            if USE_QUESTIONARY:
                choices.append(questionary.Choice(label, value=str(file_path)))
            else:
                choices.append({"label": label, "value": str(file_path)})
            counter += 1

    return choices


def jsonl_to_html(jsonl_path):
    """Convert JSONL session file to readable HTML."""
    with open(jsonl_path, "r") as f:
        lines = f.readlines()

    # Parse session info for better title
    session_info = parse_session_info(jsonl_path)
    cwd_short = session_info["cwd"].split("/")[-1] if session_info["cwd"] else "unknown"
    ts_formatted = format_timestamp(session_info["timestamp"])

    html_parts = ["<!DOCTYPE html><html><head>"]
    html_parts.append("<meta charset='UTF-8'>")
    html_parts.append("<style>")
    html_parts.append("body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 1000px; margin: 40px auto; padding: 20px; line-height: 1.6; }")
    html_parts.append(".message { margin: 20px 0; border-radius: 8px; }")
    html_parts.append(".user { background: #e3f2fd; border-left: 4px solid #2196f3; }")
    html_parts.append(".assistant { background: #f5f5f5; border-left: 4px solid #757575; }")
    html_parts.append(".system { background: #fff3e0; border-left: 4px solid #ff9800; font-style: italic; }")
    html_parts.append(".meta { color: #666; font-size: 0.85em; margin-bottom: 8px; }")
    html_parts.append(".content { white-space: pre-wrap; word-wrap: break-word; padding: 15px; }")
    html_parts.append("h1 { color: #333; }")
    html_parts.append(".subtitle { color: #666; font-size: 0.9em; margin-bottom: 20px; }")
    html_parts.append("details { margin: 10px 0; }")
    html_parts.append("summary { cursor: pointer; padding: 10px 15px; font-weight: 500; user-select: none; }")
    html_parts.append("summary:hover { background: rgba(0,0,0,0.05); }")
    html_parts.append(".pagination { margin: 30px 0; padding: 20px; text-align: center; background: #f9f9f9; border-radius: 8px; }")
    html_parts.append(".pagination button { padding: 10px 20px; margin: 0 5px; font-size: 14px; cursor: pointer; border: 1px solid #ddd; background: white; border-radius: 4px; }")
    html_parts.append(".pagination button:hover { background: #e0e0e0; }")
    html_parts.append(".pagination button:disabled { opacity: 0.5; cursor: not-allowed; }")
    html_parts.append(".pagination .page-info { margin: 0 15px; font-size: 14px; color: #666; }")
    html_parts.append(".message-card { display: none; }")
    html_parts.append(".message-card.active { display: block; }")
    html_parts.append(".controls { margin: 20px 0; padding: 15px; background: #f0f8ff; border-radius: 8px; display: flex; gap: 10px; align-items: center; }")
    html_parts.append(".controls button { padding: 8px 16px; font-size: 14px; cursor: pointer; border: 1px solid #2196f3; background: white; border-radius: 4px; color: #2196f3; }")
    html_parts.append(".controls button:hover { background: #2196f3; color: white; }")
    html_parts.append("#scrollTopBtn { position: fixed; bottom: 30px; right: 30px; padding: 12px 20px; font-size: 16px; cursor: pointer; border: none; background: #2196f3; color: white; border-radius: 50%; box-shadow: 0 4px 12px rgba(0,0,0,0.15); display: none; z-index: 1000; }")
    html_parts.append("#scrollTopBtn:hover { background: #1976d2; }")
    html_parts.append("</style></head><body>")
    html_parts.append(f"<h1>{cwd_short}</h1>")
    html_parts.append(f"<div class='subtitle'>{ts_formatted}</div>")
    html_parts.append("<div class='controls'>")
    html_parts.append("<button onclick='expandAll()'>Expand All</button>")
    html_parts.append("<button onclick='collapseAll()'>Collapse All</button>")
    html_parts.append("</div>")

    message_count = 0
    for line in lines:
        if not line.strip():
            continue
        try:
            data = json.loads(line)
            if data.get("type") == "message":
                msg = data.get("message", {})
                role = msg.get("role", "unknown")
                content = msg.get("content", "")
                timestamp = data.get("timestamp", "")

                # Handle content (may be array or string)
                if isinstance(content, list):
                    content_text = "\n".join(c.get("text", "") for c in content if isinstance(c, dict))
                else:
                    content_text = str(content)

                html_parts.append(f"<div class='message {role} message-card' data-index='{message_count}'>")
                html_parts.append(f"<details open>")
                html_parts.append(f"<summary>{role.upper()} | {timestamp}</summary>")
                html_parts.append(f"<div class='content'>{html.escape(content_text)}</div>")
                html_parts.append(f"</details>")
                html_parts.append("</div>")
                message_count += 1
        except Exception as e:
            continue

    # Add pagination controls
    html_parts.append("<div class='pagination'>")
    html_parts.append("<button id='prevBtn' onclick='changePage(-1)'>Previous</button>")
    html_parts.append("<span class='page-info'>Page <span id='currentPage'>1</span> of <span id='totalPages'>1</span></span>")
    html_parts.append("<button id='nextBtn' onclick='changePage(1)'>Next</button>")
    html_parts.append("<div id='pageNumbers' style='margin-top: 15px;'></div>")
    html_parts.append("</div>")

    html_parts.append("<button id='scrollTopBtn' onclick='scrollToTop()'>↑</button>")

    html_parts.append("<script>")
    html_parts.append("const MESSAGES_PER_PAGE = 15;")
    html_parts.append("let currentPage = 1;")
    html_parts.append("const messages = document.querySelectorAll('.message-card');")
    html_parts.append("const totalPages = Math.ceil(messages.length / MESSAGES_PER_PAGE);")
    html_parts.append("")
    html_parts.append("function showPage(page) {")
    html_parts.append("  messages.forEach((msg, index) => {")
    html_parts.append("    if (index >= (page - 1) * MESSAGES_PER_PAGE && index < page * MESSAGES_PER_PAGE) {")
    html_parts.append("      msg.classList.add('active');")
    html_parts.append("    } else {")
    html_parts.append("      msg.classList.remove('active');")
    html_parts.append("    }")
    html_parts.append("  });")
    html_parts.append("  document.getElementById('currentPage').textContent = page;")
    html_parts.append("  document.getElementById('totalPages').textContent = totalPages;")
    html_parts.append("  document.getElementById('prevBtn').disabled = page === 1;")
    html_parts.append("  document.getElementById('nextBtn').disabled = page === totalPages;")
    html_parts.append("  updatePageNumbers();")
    html_parts.append("}")
    html_parts.append("")
    html_parts.append("function changePage(delta) {")
    html_parts.append("  const newPage = currentPage + delta;")
    html_parts.append("  if (newPage >= 1 && newPage <= totalPages) {")
    html_parts.append("    currentPage = newPage;")
    html_parts.append("    showPage(currentPage);")
    html_parts.append("    window.scrollTo(0, 0);")
    html_parts.append("  }")
    html_parts.append("}")
    html_parts.append("")
    html_parts.append("function goToPage(page) {")
    html_parts.append("  if (page >= 1 && page <= totalPages) {")
    html_parts.append("    currentPage = page;")
    html_parts.append("    showPage(currentPage);")
    html_parts.append("    window.scrollTo(0, 0);")
    html_parts.append("  }")
    html_parts.append("}")
    html_parts.append("")
    html_parts.append("function updatePageNumbers() {")
    html_parts.append("  const container = document.getElementById('pageNumbers');")
    html_parts.append("  container.innerHTML = '';")
    html_parts.append("  for (let i = 1; i <= totalPages; i++) {")
    html_parts.append("    const btn = document.createElement('button');")
    html_parts.append("    btn.textContent = i;")
    html_parts.append("    btn.onclick = () => goToPage(i);")
    html_parts.append("    if (i === currentPage) {")
    html_parts.append("      btn.style.background = '#2196f3';")
    html_parts.append("      btn.style.color = 'white';")
    html_parts.append("      btn.style.borderColor = '#2196f3';")
    html_parts.append("    }")
    html_parts.append("    container.appendChild(btn);")
    html_parts.append("  }")
    html_parts.append("}")
    html_parts.append("")
    html_parts.append("function expandAll() {")
    html_parts.append("  document.querySelectorAll('details').forEach(d => d.open = true);")
    html_parts.append("}")
    html_parts.append("")
    html_parts.append("function collapseAll() {")
    html_parts.append("  document.querySelectorAll('details').forEach(d => d.open = false);")
    html_parts.append("}")
    html_parts.append("")
    html_parts.append("function scrollToTop() {")
    html_parts.append("  window.scrollTo({ top: 0, behavior: 'smooth' });")
    html_parts.append("}")
    html_parts.append("")
    html_parts.append("window.onscroll = function() {")
    html_parts.append("  const btn = document.getElementById('scrollTopBtn');")
    html_parts.append("  if (document.body.scrollTop > 300 || document.documentElement.scrollTop > 300) {")
    html_parts.append("    btn.style.display = 'block';")
    html_parts.append("  } else {")
    html_parts.append("    btn.style.display = 'none';")
    html_parts.append("  }")
    html_parts.append("};")
    html_parts.append("")
    html_parts.append("showPage(1);")
    html_parts.append("</script>")

    html_parts.append("</body></html>")
    return "\n".join(html_parts)


def main():
    """Main entry point."""
    choices = get_session_choices()

    if not choices:
        print("No sessions found.")
        sys.exit(0)

    if USE_QUESTIONARY:
        selected = questionary.select(
            "Select a session to view:",
            choices=choices,
        ).ask()
        if not selected:
            print("No selection made.")
            sys.exit(0)
    else:
        print("\nAvailable sessions:")
        print("-" * 80)
        for i, choice in enumerate(choices, 1):
            print(f"{i:3d}. {choice['label']}")
        print("-" * 80)

        while True:
            try:
                selection = input(f"\nEnter session number (1-{len(choices)}) or q to quit: ").strip()
                if selection.lower() == 'q':
                    print("Cancelled.")
                    sys.exit(0)

                idx = int(selection) - 1
                if 0 <= idx < len(choices):
                    selected = choices[idx]['value']
                    break
                else:
                    print(f"Please enter a number between 1 and {len(choices)}")
            except ValueError:
                print("Please enter a valid number")
            except KeyboardInterrupt:
                print("\nCancelled.")
                sys.exit(0)

    # Convert to HTML
    html = jsonl_to_html(selected)

    # Write to temp file and open
    with NamedTemporaryFile(mode="w", suffix=".html", delete=False) as f:
        f.write(html)
        temp_path = f.name

    try:
        # Open in default browser (cross-platform)
        open_in_browser(temp_path)
        print(f"Opened session in browser: {temp_path}")

        # Ask if user wants to copy to Downloads
        if USE_QUESTIONARY:
            copy_to_downloads = questionary.confirm(
                "Copy HTML file to Downloads folder?",
                default=False
            ).ask()
        else:
            while True:
                choice = input("Copy HTML file to Downloads folder? (y/n): ").strip().lower()
                if choice in ['y', 'n']:
                    copy_to_downloads = (choice == 'y')
                    break
                print("Please enter 'y' or 'n'")

        if copy_to_downloads:
            downloads = get_downloads_folder()
            downloads.mkdir(parents=True, exist_ok=True)

            # Generate a better filename
            session_info = parse_session_info(selected)
            cwd_short = session_info["cwd"].split("/")[-1] if session_info["cwd"] else "unknown"
            ts_formatted = format_timestamp(session_info["timestamp"]).replace(" ", "_").replace(":", "-")
            filename = f"{cwd_short}_{ts_formatted}.html"
            dest_path = downloads / filename

            shutil.copy2(temp_path, dest_path)
            print(f"Copied to: {dest_path}")
    finally:
        # Clean up temp file after browser opens (browser keeps its own copy)
        pass


if __name__ == "__main__":
    main()
