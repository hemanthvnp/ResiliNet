# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Current state

CommitCon has no application code, build system, tests, or git history yet. The only things in the repo are [OpenSpec](https://github.com/Fission-AI/OpenSpec) scaffolding: [openspec/config.yaml](openspec/config.yaml) (`schema: spec-driven`, with the optional `context` and `rules` sections still commented out) and Claude Code skills/commands under [.claude/](.claude/). Once a stack is chosen, add build, lint and test commands here, and fill in `context:` in `openspec/config.yaml` so generated artifacts know the tech stack and conventions.

## Workflow: OpenSpec (spec-driven)

Changes are meant to go through OpenSpec, driven by the slash commands in [.claude/commands/opsx/](.claude/commands/opsx/). Each command has an equivalent skill in [.claude/skills/](.claude/skills/) (`openspec-*`).

- `/opsx:explore`: think through a problem or requirements before committing to a change
- `/opsx:propose`: create a change and generate all its artifacts (proposal, design, specs, tasks) in one step
- `/opsx:apply`: implement the tasks of a change
- `/opsx:sync`: merge a change's delta specs into the main specs without archiving
- `/opsx:archive`: finalize and archive a completed change

These call the `openspec` CLI, which must be installed separately. The commands in use are `openspec list --json`, `openspec new change "<name>"`, `openspec status --change "<name>" --json`, and `openspec instructions <artifact-id|apply> --change "<name>" --json`. The `instructions` output tells you what to write for each artifact. Follow it rather than inventing the format.

The `openspec/` directory will hold the specs and changes. Only `config.yaml` exists so far. Artifact rules (for example for `proposal` and `tasks`) can be set under `rules:` in that file.
