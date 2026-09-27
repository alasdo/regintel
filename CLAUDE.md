# regintel

<!-- Project-specific context for Claude. The global ~/.claude/CLAUDE.md already covers
     general working style and Python standards; only put things here that are true of
     THIS repo. Keep it under ~100 lines. Delete these comments once filled in. -->

rigor: standard   <!-- or: regulated (see global CLAUDE.md) -->

## Overview

<!-- 2-4 sentences: what this does, who uses it, where its data comes from and goes. -->
TODO

## Commands

| Task | Command |
|---|---|
| Install / sync deps | `make setup` |
| Format | `make fmt` |
| Lint + types + tests (definition of done) | `make check` |
| Tests only | `make test` or `uv run pytest tests/path -k name` |
| Run | TODO |

## Layout

- `src/regintel/`: package code
- `tests/`: pytest suite; fixtures in `tests/fixtures/`
- `specs/`: feature specs (`/spec` creates, `/implement` consumes)
- `docs/decisions/`: decision records for choices that aren't obvious from the code

## Conventions

<!-- Only what differs from the global defaults, e.g. "use polars, not pandas". -->
- UI work follows DESIGN.md.
- TODO

## Domain rules

<!-- Facts about the domain the code must respect: units, time zones, identifiers,
     business rules, regulatory constraints. These are what an agent can't infer. -->
- TODO

## Gotchas

<!-- Add a line each time something bites. /learn helps with this. -->
- TODO
