## Context

See proposal.md for the motivation. The cycle-1 CLI already runs a scenario file (`run --scenario <file|id>`), and `POST /runs` accepts an inline scenario. `fixtures/` is part of the frozen contract, and the README belongs to D.

## Goals / Non-Goals

**Goals:**
- Every README field required by the rulebook is present at submission.
- A judge's "try it with this input" request takes one file edit and one command.

**Non-Goals:**
- A UI editor, new endpoints, or a scenario builder.

## Decisions

**Examples live in `examples/`, not `fixtures/`.**
- *Rejected: `fixtures/`.* Adding files there after H1.5 needs all four members to agree, and fixtures carry hand-worked assertions that judge-editable files cannot have.

**Examples reference the campus template and node ids by name**, and are written after B's template is final (the H8 to H10 tuning in PLAN.md §12).
- *Rejected: writing them earlier.* Template ids may change during tuning, and the examples would break.

**README text goes to D as a pull-request comment or a file D pastes in. It is not committed to the README by anyone but D.**
- *Rejected: editing the README directly.* D writes it during H16 to H22 (change `add-cli-benchmark` tasks 5.1 to 5.6), and two writers would conflict.

**The AI disclosure lists each member's tools and what each was used for.** It is collected from every member, not written by one person.
- The team's commit rules strip AI attribution from commits, so the README is the only disclosure the rulebook's §6.5 receives.

**Determinism.** Examples carry explicit seeds wherever a generator is used, so a judge's run reproduces the same numbers.

## Risks / Trade-offs

- **[The campus template's ids change late]** → The judge-kit test fails in CI, and the examples are fixed before the H22 tag.
- **[A member does not report their AI use]** → D's README task blocks the final tag until every member has added a line.
