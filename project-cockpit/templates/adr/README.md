# Decision log (ADRs)

One file per big decision: `NNNN-short-title.md`. New one: `cockpit adr new "Title"`.

## Rules

- **Status** is one of: Proposed, Accepted, Superseded by ADR-NNNN, Rejected.
- Only the project owner accepts an ADR.
- A changed decision gets a NEW ADR that supersedes the old one. The old page
  stays, with its Status line updated.
- Every ADR has a goal check: does this serve the primary goal below? An ADR
  that works against it is rejected.
- Read this log before changing a design. Never build against an Accepted ADR.

## Primary goal

Write the project's one-line goal here. Every ADR is checked against it.

## Log

| ADR | Title | Status |
|-----|-------|--------|
| [0001](0001-record-decisions-as-adrs.md) | Record big decisions as ADRs | Accepted |
