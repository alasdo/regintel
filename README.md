# regintel

TODO: one-paragraph description.

## Setup

```bash
make setup          # needs uv: https://docs.astral.sh/uv/
cp .env.example .env
```

## Development

```bash
make check          # lint + types + tests: the definition of done
make fmt            # format and auto-fix
```

Built with the forge workflow: specs live in `specs/`, decisions in `docs/decisions/`, and `CLAUDE.md` holds project context for Claude Code.
