# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Current state

The project is Network Rerouter, a steady-state fluid simulator of a campus network with a centralized routing controller, built by four members (A, B, C, D) in a 24-hour plan. [PLAN.md](PLAN.md) is the source of truth; cite its section numbers.

**Read [AGENTS.md](AGENTS.md) first.** It holds the rules shared by all four members' agents (PLAN.md section 11). If it conflicts with this file, raise the conflict instead of picking one.

The repo holds the plan, the [OpenSpec](https://github.com/Fission-AI/OpenSpec) config and changes under [openspec/](openspec/), the workflow tooling described below, and the `core/` Python package. The stack is fixed by PLAN.md section 6: Python 3.11+, pydantic v2, networkx, FastAPI, pytest + hypothesis; React + Vite + TypeScript.

## Commands

```
python -m venv .venv
.venv/Scripts/activate            # Windows; on Linux/macOS: source .venv/bin/activate
pip install -e ".[dev]"           # pinned versions from pyproject.toml
pytest                            # unit tests in core/<module>/tests/, D's suites in tests/
```

No linter is configured yet. Frontend commands are added when `frontend/` exists.

## Setup (once per clone)

```
git config core.hooksPath .githooks
```

This turns on the hooks in [.githooks/](.githooks/). They must be committed as executable (`git add --chmod=+x .githooks/*`).

## Team rules (PLAN.md section 11)

- **Stay in the owner's folders.** A: `routing/`, `explain/`. B: `model/`, `gen/`, `sim/`, `metrics/`. C: `frontend/`. D: `api/`, `tests/`, `cli/`. If it is not clear which member a session is working for, ask. A change needed in another owner's folder is requested from that person, not made.
- **The contract is edited by humans only.** Never edit `core/model/types.py`, `fixtures/` or the OpenAPI schema after the H1.5 freeze. A change needs all four members to agree, and the fixtures change first.
- **The core stays pure.** Nothing under `core/` imports FastAPI or frontend code.
- **Determinism.** All randomness goes through an explicit `random.Random(seed)`; sort by id wherever order could matter; never depend on dict or set ordering.
- **After the H16 feature freeze**, only fixes and docs.

## Git rules

[.claude/settings.json](.claude/settings.json) prompts before every commit, push, merge, rebase, tag, PR and release, and strips Claude attribution. The hooks block direct commits on `main`, bad commit messages, and force-pushes to `main`.

- **Never commit without approval.** Show the staged diff summary and the proposed commit message, then wait for an explicit yes. Approval covers that one commit only. The same applies to push, merge, rebase, tag and opening or merging a PR.
- **Author only.** Commits carry the configured git author and nothing else: no `Co-Authored-By` trailer, no "Generated with Claude Code" line, in commits or PR descriptions.
- **Never work on `main` directly.** Branch from an up-to-date `main` first: `feat/<name>`, `fix/<name>`, `docs/<name>`, `chore/<name>`, `refactor/<name>` or `test/<name>`. For an OpenSpec change, `<name>` is the change name.
- **One logical change per commit.** Each commit builds and passes tests on its own. Subject line in the imperative, 72 characters or fewer, no trailing period (`Add flow allocation solver`); add a body explaining why when the reason is not obvious. No `wip` or `fix typo` commits in the final history: fold them in with `git commit --fixup` and `git rebase --autosquash` before the branch is merged.
- **Rebase to stay current.** Update a feature branch with `git rebase main`, never by merging `main` into it. Rebase only branches that are yours alone; if a rebased branch was already pushed, push with `--force-with-lease`, never `--force`.
- **Merge to integrate.** A finished branch reaches `main` through a pull request (below). Use a merge commit (`--no-ff`) when the branch has several commits, so the feature stays grouped; rebase-merge a single-commit branch. Do not squash-merge. Never rebase or force-push `main`, and never rewrite history that others have pulled.
- **Never bypass the hooks** with `--no-verify`.
- Delete the branch after it is merged.

## Pull requests

- Open one PR per branch, filled in from [.github/pull_request_template.md](.github/pull_request_template.md), with every checklist item true or explained.
- Before opening: rebase onto `main`, run the tests, and run `sh .github/scripts/check-history.sh` (checks every commit in `main..HEAD`).
- Keep a PR to one OpenSpec change or one fix. Unrelated cleanups get their own branch.
- CI must be green before merge. A red check is fixed in the branch, not overridden.
- Address review comments with `fixup!` commits while the review is open, then autosquash before merge.

## SDLC rules

Every change moves through these phases in order. Do not start a phase until the previous one is done, and say which phase the work is in.

1. **Requirements**: clarify what is needed and why (`/opsx:explore`). No code yet.
2. **Design**: write the proposal, design, specs and tasks (`/opsx:propose`), and get them approved before implementing.
3. **Implementation**: on a feature branch, work through the tasks (`/opsx:apply`). Stay within the approved scope; a scope change goes back to the design artifacts first.
4. **Testing**: follow the testing rules below. Run the full suite before proposing a commit, and report failures as they are.
5. **Review**: present the diff for review before commit, and open a PR before merge to `main`.
6. **Integration**: rebase onto `main`, rerun the tests, then merge as described above.
7. **Closure**: sync the specs and archive the change (`/opsx:sync`, `/opsx:archive`), update [CHANGELOG.md](CHANGELOG.md), and update this file and other docs when commands or conventions change.

## Testing rules (PLAN.md sections 9 and 11)

- Every behavior change comes with tests in the same branch. Each member tests their own module.
- **Expected numbers are worked by hand** and written before the code. Never generate both an implementation and the values it is tested against; ask the owner for the hand-worked numbers.
- **Never weaken or delete an assertion** to make a test pass. A failing test is fixed in the code. If the test itself is wrong, say so and let the owner decide.
- Run `check_invariants` (I1 to I11) on every snapshot in tests, once it exists.
- A property test that fails must print its seed and parameters so the case can be replayed.
- Same scenario, config and seed must give an identical snapshot sequence (I8). Treat a flaky test as a determinism bug, not as noise.

## Hotfixes

For a defect on `main` that blocks the team or the demo:

1. Branch `fix/<name>` from current `main`.
2. Write a failing test that reproduces the defect, then make the smallest change that passes it. No refactoring or features ride along.
3. Run the full suite, then PR and merge as usual. Approval is still required.
4. Afterwards, update the affected OpenSpec specs, and tell the other three members to rebase.
5. An algorithm fix made after the benchmark has run invalidates its tables: flag that the benchmark must be rerun (PLAN.md section 12).

## Releases

- Versions follow semantic versioning and are annotated tags on `main` only: `git tag -a vX.Y.Z -m "..."`.
- Tag a milestone once its exit criteria in PLAN.md section 12 pass: `v0.1.0` for M1, `v0.2.0` for M2, `v0.3.0` for M3, `v0.4.0` for the H16 feature freeze, `v1.0.0` for the final submission. Fixes between milestones bump the patch number.
- Before tagging: all tests green on `main`, and the `Unreleased` entries in [CHANGELOG.md](CHANGELOG.md) moved under the new version with its date.
- Never move or delete a pushed tag. A bad release gets a new patch version.

## CI

[.github/workflows/ci.yml](.github/workflows/ci.yml) runs on every PR and on pushes to `main`: a commit-history check (PRs only), the backend tests and the frontend build. The backend and frontend jobs skip their steps until `pyproject.toml` or `requirements.txt`, and `frontend/package.json`, exist.

## Workflow: OpenSpec (spec-driven)

Changes are meant to go through OpenSpec, driven by the slash commands in [.claude/commands/opsx/](.claude/commands/opsx/). Each command has an equivalent skill in [.claude/skills/](.claude/skills/) (`openspec-*`).

- `/opsx:explore`: think through a problem or requirements before committing to a change
- `/opsx:propose`: create a change and generate all its artifacts (proposal, design, specs, tasks) in one step
- `/opsx:apply`: implement the tasks of a change
- `/opsx:sync`: merge a change's delta specs into the main specs without archiving
- `/opsx:archive`: finalize and archive a completed change

These call the `openspec` CLI, which must be installed separately. The commands in use are `openspec list --json`, `openspec new change "<name>"`, `openspec status --change "<name>" --json`, and `openspec instructions <artifact-id|apply> --change "<name>" --json`. The `instructions` output tells you what to write for each artifact. Follow it rather than inventing the format.

Project context and per-artifact rules for generated artifacts are set in [openspec/config.yaml](openspec/config.yaml) under `context:` and `rules:`.
