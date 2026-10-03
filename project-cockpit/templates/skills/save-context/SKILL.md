---
name: save-context
description: Write or update an agent-first CONTEXT file - the dense state a cold session (or another AI tool) needs to resume a task. Sections State now, Facts and decisions, Open questions and risks, Key resources, Next actions, and a fenced Handover prompt. Use when the user says save context, /save-context, hand this over, or before ending a long session. The human-facing twin is save-plan.
---

# save-context

1. Announce: `save-context: writing <path>; validator will verify.`
2. New file: `cockpit context new "<topic>"` (creates `<plans_dir>/<topic>-context.md`
   from `.cockpit/templates/context.md`). Update: read the existing file first.
3. Fill it. `State now` is the most useful paragraph: where the work really is.
   Durable facts go in `Facts and decisions`, each with a one-line why.
   Dense, no hand-holding prose, real file paths.
4. Keep the `**Status:**` line true and the `load-for` keywords useful.
5. End with a fenced `## Handover prompt`: goal, state, next step, hard rules.
   It must work pasted into a fresh session with no other context.
6. Validate and show the result: `cockpit lint <path>` must print `PASS`.
7. Add a CHANGELOG line if the state changed.
