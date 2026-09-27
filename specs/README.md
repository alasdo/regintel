# Specs

One file per feature: `NNNN-short-slug.md`, created with `/spec`, built with `/implement`.

Lifecycle, tracked in each file's front matter:

| status | meaning |
|---|---|
| `draft` | being written; not ready to build |
| `approved` | I've reviewed it; `/implement` may start |
| `in-progress` | being built (shown to Claude at session start) |
| `done` | all acceptance checks pass and it's merged |

A spec is the contract for the agent. If implementation reveals the spec is wrong, change the spec first, then the code.
