# Claude Code response banner

Brackets every Claude Code response in the terminal with a start and end rule:

```
┏━ ▶ CLAUDE START ━ 14:32:07 ━ mydrafts ━ ⎇ main ━━━━━━━━━━━━━━━━━┓

  ... Claude's response ...

┗━ ■ CLAUDE END ━ 14:32:51 ━ 44s ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
```

The rules are drawn by hooks, not by the model, so they appear on **every**
turn — they cannot be forgotten, skipped, or reworded mid-session.

## How it works

Two hooks in `settings.json` call the same script:

| Hook               | Fires when              | Draws                             |
| ------------------ | ----------------------- | --------------------------------- |
| `UserPromptSubmit` | you submit a prompt     | top rule + time, folder, branch    |
| `Stop`             | Claude finishes a turn  | bottom rule + time, turn duration  |

The script writes `{"systemMessage": "..."}` to stdout, which Claude Code
renders in the terminal. The start hook stamps the time into a temp file keyed
by session id; the end hook reads it back to compute the duration.

## Install

Needs `python3` and `jq`. From a clone of this repo:

```bash
./claude-response-banner/install.sh              # ~/.claude/settings.json  (all projects)
./claude-response-banner/install.sh --project    # .claude/settings.json    (this repo, shared)
./claude-response-banner/install.sh --local      # .claude/settings.local.json (this repo, private)
```

Then restart Claude Code, or open `/hooks` once — settings are re-read on
startup, so a running session will not pick the hooks up on its own.

The installer backs up the target file, refuses to touch it if it is not valid
JSON, and merges into whatever hooks are already there rather than replacing
them. Re-running it is safe: previous banner hooks are stripped first, so you
never end up with two.

To remove:

```bash
./claude-response-banner/install.sh --uninstall           # add --project / --local to match
```

## Customising

Set these in the `env` block of the same `settings.json`, or export them in
your shell profile:

| Variable               | Default  | Effect                                            |
| ---------------------- | -------- | ------------------------------------------------- |
| `CLAUDE_BANNER_WIDTH`  | `68`     | Total width of the rule, in columns               |
| `CLAUDE_BANNER_LABEL`  | `CLAUDE` | Text in the rule, e.g. `WORK` to tell setups apart |
| `CLAUDE_BANNER_STYLE`  | `heavy`  | `heavy`, `light`, `double`, or `ascii`             |
| `CLAUDE_BANNER_ANSI`   | off      | `1` to bold the start rule and dim the end rule    |

```jsonc
{
  "env": {
    "CLAUDE_BANNER_LABEL": "WORK",
    "CLAUDE_BANNER_STYLE": "light",
    "CLAUDE_BANNER_WIDTH": "80"
  }
}
```

`ansi` is off by default because whether raw escape codes render or print
literally depends on the client — turn it on and see. Use `ascii` if your
terminal font renders box-drawing characters at the wrong width.

Preview a style without installing anything:

```bash
echo '{}' | CLAUDE_BANNER_STYLE=double python3 claude-response-banner/banner.py start | jq -r .systemMessage
```

## Notes

- The `Stop` hook also fires on `/clear`, `/compact` and resume. Those draw a
  closing rule with no duration, since there was no matching start.
- The script never fails a session: any unexpected error exits 0 with no
  output, and the turn proceeds as if no hook were configured.
- Git branch is read straight from `.git/HEAD` (worktrees included) rather than
  shelling out to `git`, so the hook adds no measurable latency.

## Optional: consistent formatting *inside* the response

The banners frame the response. If you also want the prose inside them to
follow a house style, that part is the model's job and belongs in
`~/.claude/CLAUDE.md`:

```markdown
## Response formatting

- Open with a one-line summary of what you did or found.
- Use `##` headings only when the response has three or more distinct parts.
- Reference code as `path/to/file.py:42`.
- Close anything multi-step with a short "what changed" list.
```

Unlike the hooks, this is guidance rather than a guarantee — the model follows
it most of the time but may deviate when a response does not fit the shape.
Keep anything you need to be reliable in the hooks.
