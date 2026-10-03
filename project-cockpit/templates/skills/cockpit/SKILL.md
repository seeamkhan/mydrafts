---
name: cockpit
description: Operate this repo's project-cockpit - the context map, doc statuses, action board, system map, logs, ADRs and dashboard. Use at the start of a session, when asked what state the project is in, to add an action item for a person, to record that something new runs, to check logs or whether a service is up, before committing, or when the user says cockpit, dashboard, board, system map, status drift, or context map.
---

# cockpit - run the project's memory

`cockpit` below means `python3 .cockpit/kit/cockpit.py` (vendored) or the path
in `$COCKPIT`. All commands take `--root <repo>`; the default is the current folder.

## Session start (do this first)

1. Read `.cockpit/index.md`. Load only the docs whose keywords match the task.
2. `cockpit board list`. Anything in `review` is a person saying "I did it":
   verify it, then `cockpit board done <id> "how you checked"` or
   `cockpit board back <id> "what is still missing"`.

## While working

| You did this | Then do this |
|---|---|
| Changed anything | One dated line in `CHANGELOG.md` |
| Made a big decision | `cockpit adr new "Title"`, fill it, status Proposed; the owner accepts |
| A person must do or decide something | `cockpit board add "task" --priority P2 --what "..." --why "..." --step "..." --step "..." --dod "..."` |
| Added something that runs | A row in `.cockpit/system-map.json`: id, name, plain `what`, group, probe, logs, offSwitch |
| Finished or parked a doc's work | Update its `**Status:**` line (done, in progress, todo, blocked, cancelled) |
| Changed a user-facing feature | One line in `MANUAL.md` |

`what` must make sense to someone reading it cold in six months. `why` says
what breaks if it never happens. Never leave an action item only in a reply.

## Checking

- `cockpit status` - every doc's status; DRIFT lines mean the label and the doc disagree. Fix the wrong side.
- `cockpit system probe` - is each component up. `cockpit logs <id> --grep error` - its recent log lines.
- `cockpit check` - everything; run before every commit (the pre-commit hook does).
- `cockpit build` then open `.cockpit/site/index.html`, or `cockpit serve`.

## Rules

- Never hand-edit `.cockpit/index.md` or anything under `.cockpit/site/`; they are generated.
- Never put secrets in the board, the system map or a doc. Logs on the dashboard are
  redacted on a best-effort basis only; set `logs_in_site: false` in `.cockpit/config.json`
  for sensitive projects.
