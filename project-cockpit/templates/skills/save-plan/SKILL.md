---
name: save-plan
description: Write or update a human+agent PLAN doc - a progressive-disclosure checklist with Goal, What today requires, an Action checklist whose items link to Detail, owners and dates, and a fenced Handover prompt. Use when the user says save plan, update the plan, /save-plan, or wants a multi-step task captured as a plan they can review. The agent-facing twin is save-context.
---

# save-plan

1. Announce: `save-plan: writing <path>; validator will verify.`
2. New file: `cockpit plan new "<topic>"` (creates `<plans_dir>/<topic>-plan.md`).
   Update: read the existing file, keep its structure, change only what moved.
3. The three rules:
   - The top is tiny and forward-looking. Goal is one line. "What today
     requires" holds only the next targets, never done items.
   - The payload lives in Detail. Every action links down: `_See [#N detail](#anchor)_`.
   - Every action names an owner and, where it has one, a date.
4. Keep the `**Status:**` line true.
5. End with a fenced `## Handover prompt`.
6. Validate and show the result: `cockpit lint <path>` must print `PASS`.
7. Action items a person must do also go on the board (`cockpit board add ...`);
   the plan links to them, it does not replace them.
