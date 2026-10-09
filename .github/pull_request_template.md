## What and why

<!-- One or two sentences. Link the OpenSpec change: openspec/changes/<name>/ -->

## Owner and scope

- Owner (A, B, C or D):
- Folders touched:

## Checklist

- [ ] Stays inside the owner's folders (PLAN.md section 11)
- [ ] Does not touch `core/model/types.py`, `fixtures/` or the OpenAPI schema, or all four members agreed and the fixtures were updated first
- [ ] Tests added or updated; expected numbers worked by hand
- [ ] Full test suite and `check_invariants` pass locally
- [ ] No assertion weakened or deleted to make a test pass
- [ ] Rebased onto current `main`; no merge commits, `fixup!` or `wip` commits in the branch
- [ ] `sh .github/scripts/check-history.sh` passes
- [ ] `CHANGELOG.md` updated under Unreleased, if the change is visible to users
- [ ] OpenSpec tasks ticked; specs synced if the change is complete

## How to verify

<!-- Commands to run, or what to click in the UI. -->
