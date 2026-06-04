#!/usr/bin/env bash
# =============================================================================
#  install.sh  —  one-click terminal setup for macOS and Ubuntu/Linux
# -----------------------------------------------------------------------------
#  What it does (no admin / sudo required):
#    1. Copies unified-shell.sh to ~/.config/unified-shell/unified-shell.sh
#    2. Adds ONE guarded `source` line to your ~/.zshrc (macOS) or ~/.bashrc
#       (Linux). Safe to run repeatedly — it never adds the line twice.
#    3. Creates the ~/src/github.com/<user> project folder structure.
#    4. Backs up your shell rc file before touching it.
#
#  Usage:
#    bash install.sh                 # uses default GitHub user "seeam"
#    GH_USER=yourname bash install.sh
# =============================================================================
set -euo pipefail

GH_USER="${GH_USER:-seeam}"
SRC_ROOT="$HOME/src/github.com/$GH_USER"

# Resolve where this script lives so we can find unified-shell.sh next to it.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_FILE="$SCRIPT_DIR/shell/unified-shell.sh"

CONFIG_DIR="$HOME/.config/unified-shell"
INSTALLED_FILE="$CONFIG_DIR/unified-shell.sh"

MARKER="# >>> unified-shell >>>"
MARKER_END="# <<< unified-shell <<<"

say() { printf '  \033[32m✓\033[0m %s\n' "$1"; }
info() { printf '  \033[34mℹ\033[0m %s\n' "$1"; }

echo "── Unified terminal setup ───────────────────────────────"

# --- sanity check -----------------------------------------------------------
if [ ! -f "$SOURCE_FILE" ]; then
  echo "Error: cannot find $SOURCE_FILE" >&2
  echo "Run this script from inside the terminal-setup folder." >&2
  exit 1
fi

# --- 1. copy the shared config ----------------------------------------------
mkdir -p "$CONFIG_DIR"
cp "$SOURCE_FILE" "$INSTALLED_FILE"
say "Installed shared config -> $INSTALLED_FILE"

# --- 2. pick the right rc file ----------------------------------------------
case "${SHELL:-}" in
  *zsh)  RC="$HOME/.zshrc"  ;;
  *bash) RC="$HOME/.bashrc" ;;
  *)
    # Fall back on OS default: zsh on macOS, bash on Linux.
    if [ "$(uname -s)" = "Darwin" ]; then RC="$HOME/.zshrc"; else RC="$HOME/.bashrc"; fi
    ;;
esac
touch "$RC"

# --- 3. add the guarded source block (idempotent) ---------------------------
if grep -qF "$MARKER" "$RC"; then
  info "Source line already present in $RC — leaving it as is."
else
  cp "$RC" "$RC.backup.$(date +%Y%m%d%H%M%S)"
  say "Backed up $RC"
  {
    echo ""
    echo "$MARKER"
    echo "# Loads the shared cross-machine terminal config. Edit GH_USER below to taste."
    echo "export GH_USER=\"$GH_USER\""
    echo "[ -f \"$INSTALLED_FILE\" ] && source \"$INSTALLED_FILE\""
    echo "$MARKER_END"
  } >> "$RC"
  say "Wired up $RC to load the config"
fi

# --- 4. create the project folder structure ---------------------------------
mkdir -p "$SRC_ROOT"
say "Project folder ready -> $SRC_ROOT"

echo "─────────────────────────────────────────────────────────"
echo ""
info "Done! Reload your shell to see the new look:"
echo "      source $RC"
echo ""
info "Then try:  ll   |   ghp   |   cd into a git repo to see the branch"
echo ""
info "For the full Ubuntu purple terminal look, see THEMES.md"
