You are helping me get my work machine in order before my user account changes.
In about two weeks my current account (and its home folder, local files, and
possibly its access) will be closed, and I will start on a new account. I do not
want to lose anything I built. Work in phases and STOP for my approval between
phases.

HARD RULES
- Everything stays inside company-approved systems (the company GitHub org,
  company OneDrive/SharePoint, Confluence). Never upload, email, paste, or sync
  anything to a personal account or any outside service.
- Never copy secrets: tokens, passwords, API keys, .env files, private keys,
  cookies, credential stores. List them by path only, so I can re-create them.
- Never delete anything without my explicit yes, file by file or group by group.
- Read-only until I approve the plan.
- Keep your replies short: tables, not prose.

PHASE 1: INVENTORY (read-only)
Scan my home folder and the usual places, including:
- git repos anywhere under home (note: remote URL, branch, uncommitted changes,
  unpushed commits, stashes, local-only branches)
- AI setup: ~/.claude (CLAUDE.md, skills, agents, commands, hooks, settings),
  any AGENTS.md / CLAUDE.md in repos, MCP server configs and the MCP server code
  I wrote, Devin / Copilot / other agent configs, prompt files
- scripts, notebooks, dotfiles, shell aliases, terminal and editor settings
- Documents, Desktop, Downloads, notes apps exports, local markdown notes,
  diagrams, slide decks, test reports, release evidence
- browser bookmarks export (list only)
For each item give: path, type, size, last modified, and a one-line guess of what
it is. Group into: (A) my own work, (B) already safe in a remote (pushed, on
Confluence, on OneDrive), (C) junk or temp, (D) secrets, (E) not sure.
Then STOP and show me the table.

PHASE 2: PLAN
For every item in A and E, propose where it goes:
- code, skills, MCP servers, agent configs -> one private repo in the company
  GitHub org (suggest a name like <me>-workbench), with a clear folder layout
- documents and evidence -> one OneDrive folder with the same layout
- anything with uncommitted or unpushed git work -> commit and push to its own
  remote first, on a branch named backup/<date>
Also list everything that lives in the ACCOUNT, not on disk, that I must
re-create or export: email rules and folders, Webex spaces I own, calendar
series I organize, Confluence personal space, Jira filters and dashboards,
GitHub tokens, service accounts, scheduled jobs, CI secrets tied to my user.
Then STOP and wait for my yes.

PHASE 3: MOVE (only after my yes)
Do the moves exactly as approved. After each group, verify: the remote has it,
file counts and sizes match. Report a short done table.

PHASE 4: MY WORK RECORD
Write one markdown file in the new repo, WORK-RECORD.md: what I built, when,
and where the proof lives (repo links, PR links, Confluence pages, release
notes). One row per item: date, what it is, who uses it, link. Facts only, no
hype. Include: test frameworks, AI skills, MCP servers, CI pipelines, context
repos, playbooks, demos. This is my evidence of impact for my next review.

PHASE 5: RESTORE GUIDE
Write SETUP-NEW-ACCOUNT.md: the exact steps to get my new account back to
working (clone list, skill and config install, MCP setup, secrets to
re-create by name, settings). Keep it a checklist.

Start with Phase 1 now.
