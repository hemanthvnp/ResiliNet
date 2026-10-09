# AGENTS.md

Shared rules for every AI coding agent working in this repository, whichever tool runs it (PLAN.md section 11). Each tool's own instruction file (for example `CLAUDE.md`) points here. If a tool's file conflicts with this one, raise the conflict with the team instead of picking one.

[PLAN.md](PLAN.md) is the source of truth. Prompt with the relevant section, not from memory: section 5 for the allocator, section 7 for types, section 8 for metrics, section 10 for the UI.

## Stack

Python 3.11+, pydantic v2, networkx, FastAPI, pytest + hypothesis (backend); React + Vite + TypeScript, Cytoscape.js, Recharts (frontend). REST only. No database, containers, ML or WebSocket. Dependency versions are pinned in `pyproject.toml`; do not change a pin without the team.

## Commands

```
python -m venv .venv
.venv/Scripts/activate            # Windows; on Linux/macOS: source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

## Folder ownership

| Member | Folders |
|---|---|
| A: routing | `core/routing/`, `core/explain/` |
| B: simulation, model, metrics | `core/model/`, `core/gen/`, `core/sim/`, `core/metrics/` |
| C: frontend | `frontend/` |
| D: integration and QA | `api/`, `tests/`, `cli/` |
| Cycle 2 (nithiishsd) | `ext/`, `examples/` ([PLAN-CYCLE2.md](PLAN-CYCLE2.md) section 7) |

An agent edits only its owner's folders. A change needed in another member's folder is requested from that member, not made. Unit tests live beside each module in `core/<module>/tests/`; the top-level `tests/` holds D's cross-module suites.

## The contract

**Never edit `core/model/types.py`, `fixtures/` or the OpenAPI schema.** They are frozen at H1.5 and edited by humans only, after all four members agree, and the fixtures change first. Never "fix" a type to make your own code pass.

## Core purity

Nothing under `core/` imports FastAPI, the API or frontend code.

## Determinism (PLAN.md section 7)

- All randomness goes through an explicit `random.Random(seed)` passed in. No module-level `random`, no clocks in results.
- Sort by id wherever iteration order could matter. Never depend on dict or set ordering.
- Dijkstra tie-break is `(cost, hops, node ids)`. Costs are integers.
- `RoutingPolicy.route` is pure: no globals, no unseeded randomness; `prev` is copied into the log and never influences the allocation.

## Tests

- Expected numbers are worked by hand by the owner before the code exists. An agent never generates both an implementation and the values it is tested against.
- Never weaken or delete an assertion to make a test pass. Fix the code; if the test is wrong, tell the owner.
- Run `check_invariants` (I1 to I11) on every snapshot in tests, once it exists.
- A failing property test prints its seed and parameters.

## Git

Never commit, push, merge, rebase or tag without the owner's explicit approval. Work on a branch (`feat/<change-name>` for an OpenSpec change), never on `main`. Commits carry the git author only, with no AI attribution. Never bypass the hooks with `--no-verify`.
