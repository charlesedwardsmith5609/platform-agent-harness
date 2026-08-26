# Repository status

> **Adapt this file** to your actual infrastructure repository before using the harness.
> Agents read this file to understand the current state before starting work.

## Current production state

[Describe what is running in production today. What services does this repo manage?
What is their reliability/maturity level?]

## Active initiatives

[List the 1–3 things currently being actively worked on.]

## Lane ownership (current)

| Lane | Active owner | Current focus |
|---|---|---|
| `lane:foundation` | Coordinator | [current foundation work] |
| `lane:compute` | [worker or unassigned] | [focus] |
| `lane:networking` | [worker or unassigned] | [focus] |
| `lane:identity` | [worker or unassigned] | [focus] |
| `lane:observability` | [worker or unassigned] | [focus] |
| `lane:ci-cd` | [worker or unassigned] | [focus] |

## Milestones

- **Phase 1: Foundational** — [status]
- **Phase 2: Developer Experience** — [status]

## Validation commands

```bash
terraform validate
terraform fmt -check -recursive
tflint --recursive
pytest tests/ -v
make integration-test
```
