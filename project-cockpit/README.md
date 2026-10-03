# project-cockpit

Docs, plans, decisions, an action board, a system map, logs and one dashboard,
for **any** repository. One Python file, standard library only, nothing leaves
your machine.

```
            your repo                                   .cockpit/site/
  ┌──────────────────────────┐   cockpit build   ┌───────────────────────────┐
  │ *.md (each with Status:) │ ────────────────► │ Overview   counts, alerts │
  │ docs/adr/NNNN-*.md       │                   │ Board      open/review/done│
  │ plans/*-plan|context.md  │                   │ System     up/down probes │
  │ .cockpit/board.json      │                   │ Logs       tails, redacted│
  │ .cockpit/system-map.json │                   │ Decisions  ADR log        │
  │ CHANGELOG.md  MANUAL.md  │                   │ Docs       every .md page │
  └──────────────────────────┘                   └───────────────────────────┘
        ▲            │ cockpit index / check (pre-commit hook)
        │            ▼
     agents read .cockpit/index.md first (the context map)
```

It packages a way of running a project that keeps humans and AI agents from
re-deriving things: every doc says its own status, every decision has a
record, every action item has a why, and everything that runs is written down
with a way to check it is alive.

## Quick start

```sh
# 1. scaffold (detects what the repo has; never overwrites a file)
python3 cockpit.py init --root /path/to/repo

# 2. fill the "REPLACE ME" lines it wrote into .cockpit/system-map.json

# 3. see it
python3 cockpit.py build --root /path/to/repo --probe
open /path/to/repo/.cockpit/site/index.html        # or: cockpit.py serve --root ...

# 4. make the repo self-contained (teammates, CI, the git hook)
python3 cockpit.py vendor --root /path/to/repo     # copies the kit to .cockpit/kit/
```

`init --dry-run` shows what it would create first. `init --ci` also adds a
GitHub Actions workflow. `--no-skills` / `--no-hooks` skip those parts.

## What `init` creates

Only what is missing. An existing `AGENTS.md` / `CLAUDE.md` gets a section
appended between `<!-- cockpit:start -->` markers; nothing else is touched.

| File | What it is for |
|---|---|
| `AGENTS.md` (+ `CLAUDE.md` -> `@AGENTS.md`) | The operating rules for agents and people (start here, status lines, changelog, ADRs, board, system map, handoffs) |
| `.cockpit/index.md` | Generated context map: one line per doc with its status and load keywords. Agents read it first and load only what matches |
| `CHANGELOG.md` | One dated line per change: the current high-level state |
| `MANUAL.md` | Front door for people who use the project |
| `docs/adr/` | Decision log: README with the primary goal, a template, ADR-0001 |
| `plans/` | Pairs of `<topic>-plan.md` (human checklist) and `<topic>-context.md` (agent resume file) |
| `.cockpit/board.json` | The action board |
| `.cockpit/system-map.json` | Everything that runs, pre-filled from what was detected |
| `.cockpit/status.json` | Optional status overrides (usually empty) |
| `.cockpit/templates/` | Plan and context templates you can edit |
| `.claude/skills/` | `cockpit`, `save-plan`, `save-context`, `adr` skills for Claude Code (plain markdown, readable by any agent) |
| `.githooks/pre-commit` | Refreshes the index and runs `check` before each commit |
| `.gitignore` | Adds `.cockpit/state/` and `.cockpit/site/` |

What it detects for the system map: docker compose services (with ports),
Dockerfiles (`EXPOSE`), Procfile processes, `npm start/serve/dev`, systemd
units, launchd plists, Kubernetes Deployments/CronJobs, scheduled GitHub
workflows, crontab files, and log files or `logs/` folders.

## The ideas, one by one

**1. Every doc says its own status.** A line near the top:

```md
**Status:** done
**Status:** in progress, waiting on the API key
## Status: cancelled 2026-03-01
```

The dashboard shows ✅ done, 🟡 started, ⬜ todo, ⛔ blocked, ❌ cancel, and 📘
living (README, CHANGELOG, MANUAL: never "finished"). Only clear words decide;
anything vague is no opinion, never a guess. The label comes from, first match
wins: an exact path in `.cockpit/status.json`, the doc's own Status line, a
folder key in `status.json`, then the default. `cockpit status` lists every doc
and flags **drift**: a `status.json` label that disagrees with what the doc
says inside. `check` fails on drift.

**2. Action items live on a board, never only in a chat reply.** Every row
needs `priority` (P1-P5), `task`, `what` (makes sense cold, months later),
`why` (what breaks if it never happens), `steps` and `dod`. A row missing any
of them is refused. A person moves a row to `review` ("I did it"); whoever
checks moves it to `done`, or `back` with a reason.

```sh
cockpit board add "Rotate the DB password" --priority P1 \
  --what "The password showed up in logs/app.log on Oct 1." \
  --why "Anyone with log access can open the database." \
  --step "Change it" --step "Update the secret store" \
  --dod "The old password is rejected" --owner "Ops"
cockpit board did rotate-the-db-password "changed it"
cockpit board done rotate-the-db-password "verified the old one fails"
```

**3. Anything that runs is in the system map.** One row per service, job,
worker, cron or device, with a plain-English `what`. A component missing from
the map is invisible the day it dies. Probes:

```json
{"type": "http", "url": "http://127.0.0.1:8080/health", "timeout": 2}
{"type": "tcp", "host": "127.0.0.1", "port": 5432}
{"type": "file", "path": "logs/worker.log", "expectedEvery": "24h"}
{"type": "process", "match": "celery worker"}
{"type": "command", "run": "systemctl is-active worker.service"}
```

Add `"logs": ["logs/worker.log", "var/log/"]` and `"offSwitch"` where they
exist. `cockpit system probe` checks them all; `cockpit logs worker --grep error`
tails them.

**4. Big decisions are ADRs.** `cockpit adr new "Use Postgres for orders"`.
Each one has a goal check against the primary goal in the ADR README. Only
the owner accepts. A changed decision gets a new ADR that supersedes the old
one; nothing is deleted.

**5. Long work has a plan and a context file.** The plan is for the human
(goal, what today requires, actions linking down to detail, owners). The
context file is for the next agent (state now, facts with reasons, open
questions, next actions). Both end with a fenced handover prompt that works
pasted into a fresh session. `cockpit lint <file>` checks the shape.

**6. CHANGELOG after every change, MANUAL after every user-facing change.**

## Commands

| Command | Does |
|---|---|
| `init [--dry-run] [--ci] [--no-skills] [--no-hooks]` | Detect and scaffold |
| `detect` | Print what was found, as JSON |
| `index` | Rewrite `.cockpit/index.md` |
| `status [--json]` | Every doc's status, plus drift (exit 1 on drift) |
| `board list [--all]` / `add` / `did` / `done` / `back` / `check` | The action board |
| `system check` / `system probe` | Validate the map / probe every component |
| `logs [ID] [-n N] [--grep TEXT]` | Tail logs from the map |
| `adr new "Title"` | Next numbered ADR |
| `plan new TOPIC` / `context new TOPIC` | New plan or context file |
| `lint FILE...` | Check plan/context shape |
| `check [--strict]` | Everything; exit 1 on errors (`--strict`: warnings too) |
| `build [--out DIR] [--probe]` | Static dashboard |
| `serve [--port 8765] [--probe] [--rebuild-every SECONDS]` | Build and serve on localhost |
| `vendor` | Copy the kit into `.cockpit/kit/` |

Every command takes `--root DIR` (default: current folder).

## Configuration

`.cockpit/config.json`:

| Key | Default | Meaning |
|---|---|---|
| `project` | folder name | Title on the dashboard |
| `docs_exclude` | `[]` | Extra paths to hide, added to the built-in list (`node_modules/`, `vendor/`, `dist/`, `.cockpit/`, `.claude/` ...) |
| `default_status` | `started` | Label for a doc with no status anywhere |
| `adr_dir` | `docs/adr` (or an existing ADR folder) | Where decisions live |
| `plans_dir` | `plans` | Where plan and context files go |
| `site_out` | `.cockpit/site` | Dashboard output |
| `logs_in_site` | `true` | Put log tails on the dashboard |
| `log_tail_lines` | `200` | Lines per log |
| `renderer` | `auto` | `auto` uses the `markdown` package if installed, `builtin` always uses the bundled renderer |

## Using it at work

- Nothing is sent anywhere: no network calls except the probes you configure.
- In a git repo only tracked and unignored markdown is shown, so gitignored
  scratch never reaches the dashboard.
- Log lines that look like passwords, tokens, API keys or bearer headers are
  redacted. That is best effort: for sensitive projects set
  `"logs_in_site": false` and use `cockpit logs` in a terminal.
- The dashboard is a folder of static HTML. Keep it local, or publish it
  somewhere access-controlled (the CI template uploads it as a build artifact,
  not to a public page).

## Requirements and tests

Python 3.9+, standard library only. Optional: the `markdown` package.

```sh
python3 -m unittest discover -s tests
```
