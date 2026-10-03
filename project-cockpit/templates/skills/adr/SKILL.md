---
name: adr
description: Record or update an architecture decision record (ADR). Use when a big or hard-to-reverse decision is being made or changed (a framework, a data model, a vendor, a public interface, a rule everyone must follow), when the user says ADR, decision record, or "why did we decide", or before changing a design that an Accepted ADR covers.
---

# adr

1. Read the log first: the ADR folder's README and any ADR that touches the area.
   If an Accepted ADR covers it, you may not build against it: write a new ADR
   that supersedes it.
2. `cockpit adr new "Short title"` creates the next numbered file from the template.
3. Fill Context (facts), Options (at least two, each with good and bad),
   Decision (one or two sentences), Goal check (against the README's primary
   goal), Consequences.
4. Status stays `Proposed <date>`. Only the project owner changes it to Accepted.
   Put the question to them as a board item if they are not in the session.
5. Add the row to the log table in the README, and a CHANGELOG line.
6. When superseding: new ADR says `Supersedes ADR-NNNN`; the old one's Status
   becomes `Superseded by ADR-MMMM`. Never delete an old ADR.
