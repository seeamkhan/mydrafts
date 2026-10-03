## Project cockpit (how this repo keeps its memory)

This repo uses project-cockpit. These rules keep docs, plans, decisions, the
action board and the system map true, so nobody (human or agent) has to
re-derive anything.

- **Start here.** Read `.cockpit/index.md` (the context map, one line per doc
  with its status and load keywords). Load only the docs that match the task.
  Then check the board: `cockpit board list`.
- **Every doc says its own status.** Put a line near the top:
  `**Status:** done | in progress | todo | blocked | cancelled` (one clear
  word first, details after). Keep it true when the work moves. The dashboard
  reads it; `cockpit status` flags any doc whose label and text disagree.
- **CHANGELOG.md after every change.** One dated line: what changed and why.
- **Big decisions are ADRs** in `{{ADR_DIR}}/` (`cockpit adr new "Title"`).
  Read the log before changing a design. Never build against an Accepted ADR
  without a new ADR that supersedes it. Only the project owner accepts.
- **Action items for people go on the board, never only in a chat reply.**
  `cockpit board add "task" --priority P2 --what ... --why ... --step ... --dod ...`
  `what` must make sense cold, months later; `why` says what breaks if it is
  never done. A person marks `did`; an agent or owner checks and closes `done`.
- **Anything that runs gets a row** in `.cockpit/system-map.json` (service,
  job, cron, worker, device): a plain-English `what`, a `probe`, its `logs`
  and an `offSwitch` if it has one. A component missing from the map is
  invisible when it dies.
- **User-facing change? Update MANUAL.md** (one line is enough).
- **Handoffs.** Long or multi-session work keeps a plan
  (`{{PLANS_DIR}}/<topic>-plan.md`, the human checklist) and a context file
  (`{{PLANS_DIR}}/<topic>-context.md`, the dense state an agent resumes from).
  Both end with a fenced Handover prompt. `cockpit lint <file>` checks them.
- **Before you commit:** `cockpit check` (the pre-commit hook runs the index
  and the check for you).
- **Dashboard:** `cockpit build` writes `.cockpit/site/index.html`;
  `cockpit serve` serves it locally.

`cockpit` means `python3 <path-to>/cockpit.py --root .` (or
`python3 .cockpit/kit/cockpit.py` if the kit is vendored into this repo).
