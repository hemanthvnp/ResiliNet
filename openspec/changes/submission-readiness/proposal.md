## Why

The CommitCon rulebook requires README content that the cycle-1 README plan (PLAN.md §15, change `add-cli-benchmark` tasks 5.1 to 5.6) does not include:
- team name and members, external resources, and AI-tool use (§8, §6.5)
- the ability to explain challenges met (§9.4)

Judges may also ask for a demo with different inputs (§9.5), and the UI cannot edit flows. Missing README fields fail a submission requirement outright, whatever the code quality.

## What Changes

- Add a **judge kit**: editable scenario files under `examples/`, each runnable with one documented command under every cycle-1 policy.
- Draft the missing README sections and hand them to D, who owns the README:
  - team name and members
  - problem statement
  - external resources with licenses
  - AI tools used per member, and what for
  - Challenges

## Capabilities

### New Capabilities
- `judge-kit`: ready-to-edit example scenarios that judges can change and run live.

### Modified Capabilities
None.

## Owner and scope

- **Owner:** nithiish, as a cycle-2 contributor. This needs team agreement (PLAN-CYCLE2.md §8). D merges the README text.
- **Folders:** `examples/` (new). The README is edited only by D.
- **Plan sections:** PLAN-CYCLE2.md §3.0. Rulebook §6.5, §8, §9.4, §9.5.
- **Frozen contract:** not touched. Examples live outside `fixtures/` and use the existing `Scenario` format.

## Non-goals

- No UI flow editor. It is suggested to C but not required.
- No new CLI or API behaviour. The kit uses `python -m cli run` and `POST /runs` as they are.

## Impact

- **New data:** `examples/*.json` and a test that runs them.
- **Docs:** README sections delivered to D as text.
- **No code in any member's folder.**
