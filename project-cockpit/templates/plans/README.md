# Plans and context files

Two kinds of file live here, in pairs, one pair per long-running topic:

- `<topic>-plan.md` - the **human** checklist: goal, what today requires,
  actions that link down to detail, owners, a handover prompt.
  New: `cockpit plan new "topic"`.
- `<topic>-context.md` - the **agent** state: where things are right now,
  facts and decisions with their reasons, open questions, next actions, a
  handover prompt. New: `cockpit context new "topic"`.

Check either with `cockpit lint <file>`.
