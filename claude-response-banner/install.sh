#!/usr/bin/env bash
# Install (or remove) the Claude Code response banner hooks.
#
#   ./install.sh                 -> ~/.claude/settings.json        (all projects)
#   ./install.sh --project       -> ./.claude/settings.json        (this repo, shared)
#   ./install.sh --local         -> ./.claude/settings.local.json  (this repo, private)
#   ./install.sh --uninstall     -> remove the hooks from the same target
#
# Re-running is safe: existing banner hooks are stripped before the new ones
# are added, and every other setting in the file is left untouched.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BANNER="$SCRIPT_DIR/banner.py"
MARKER="banner.py"

TARGET="$HOME/.claude/settings.json"
UNINSTALL=0

while [ $# -gt 0 ]; do
  case "$1" in
    --project)   TARGET="$PWD/.claude/settings.json" ;;
    --local)     TARGET="$PWD/.claude/settings.local.json" ;;
    --settings)  shift; TARGET="${1:?--settings needs a path}" ;;
    --uninstall) UNINSTALL=1 ;;
    -h|--help)   awk 'NR>1 && !/^#/{exit} NR>1{sub(/^# ?/,""); print}' "${BASH_SOURCE[0]}"; exit 0 ;;
    *)           echo "unknown option: $1" >&2; exit 2 ;;
  esac
  shift
done

command -v jq >/dev/null 2>&1 || { echo "error: jq is required" >&2; exit 1; }
[ -f "$BANNER" ] || { echo "error: banner.py not found next to install.sh" >&2; exit 1; }

PY="$(command -v python3 || true)"
[ -n "$PY" ] || { echo "error: python3 is required" >&2; exit 1; }
chmod +x "$BANNER" 2>/dev/null || true

mkdir -p "$(dirname "$TARGET")"
[ -f "$TARGET" ] || echo '{}' > "$TARGET"

if ! jq empty "$TARGET" 2>/dev/null; then
  echo "error: $TARGET is not valid JSON -- fix it first, or Claude Code will" >&2
  echo "       silently ignore every setting in it." >&2
  exit 1
fi

BACKUP="$TARGET.bak.$(date +%Y%m%d%H%M%S)"
cp "$TARGET" "$BACKUP"

START_CMD="$PY $BANNER start"
END_CMD="$PY $BANNER end"

# Strip any hooks we installed previously, then drop groups left empty. This is
# what makes both install and uninstall idempotent.
STRIP='
  def clean:
    (. // [])
    | map(.hooks |= map(select((.command // "") | contains($marker) | not)))
    | map(select((.hooks | length) > 0));
  .hooks = (.hooks // {})
  | .hooks.UserPromptSubmit = (.hooks.UserPromptSubmit | clean)
  | .hooks.Stop = (.hooks.Stop | clean)
'

ADD='
  | .hooks.UserPromptSubmit += [{hooks: [{type: "command", command: $start, timeout: 5}]}]
  | .hooks.Stop            += [{hooks: [{type: "command", command: $end,   timeout: 5}]}]
'

# Leave no empty arrays behind on uninstall.
TIDY='
  | .hooks |= with_entries(select((.value | length) > 0))
  | if (.hooks | length) == 0 then del(.hooks) else . end
'

if [ "$UNINSTALL" -eq 1 ]; then
  PROGRAM="$STRIP $TIDY"
else
  PROGRAM="$STRIP $ADD"
fi

TMP="$(mktemp)"
jq --arg marker "$MARKER" --arg start "$START_CMD" --arg end "$END_CMD" \
   "$PROGRAM" "$TARGET" > "$TMP"
mv "$TMP" "$TARGET"

if [ "$UNINSTALL" -eq 1 ]; then
  echo "Removed banner hooks from $TARGET"
else
  echo "Installed banner hooks in $TARGET"
  echo
  jq '.hooks | {UserPromptSubmit, Stop}' "$TARGET"
  echo
  echo "Preview:"
  echo '{}' | "$PY" "$BANNER" start | jq -r .systemMessage
  echo "  ... your response renders here ..."
  echo '{}' | "$PY" "$BANNER" end | jq -r .systemMessage
fi

echo
echo "Backup of the previous file: $BACKUP"
echo "Restart Claude Code (or open /hooks once) to pick up the change."
