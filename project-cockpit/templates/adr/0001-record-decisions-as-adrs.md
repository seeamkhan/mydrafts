# ADR-0001: Record big decisions as ADRs

**Status:** Accepted {{DATE}}
**Decider:** Project owner

## Context

Decisions were spread across plans, chats and commit messages. Over time the
reasons got lost and agents drifted from the original goal.

## Decision

- Big decisions are recorded here, one file each, from `0000-template.md`.
- Every ADR has a goal check against the primary goal in the README.
- A changed decision gets a new ADR that supersedes the old one.
- Agents read the log before changing a design.

## Goal check

- Serves the goal: nobody has to re-explain why something was decided.
- Cost: a few minutes per big decision, none for small ones.

## Consequences

- One more step for big decisions.
