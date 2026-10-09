# Repository status

> **Trial mode:** this file describes the dogfood trial of the coordination
> harness on itself (`platform-agent-harness`), not a live compute fleet.

## Current production state

This repository is the **coordination harness** for platform engineering agents:
taxonomy-bound issue wrappers (`setup/repo_issue.py`), portable permissions,
workflow skills, and CI for harness tests. There is no Kubernetes/Terraform fleet
here — blast radius is limited to agent workflow and GitHub project hygiene.

Maturity: early. Issue lifecycle + fail-closed claims + harness-ci are on `main`.
Adoption on a real infra repo has not started yet.

## Active initiatives

1. **Dogfood trial** — sandbox
   [`acme-platform-infra-sandbox`](https://github.com/charlesedwardsmith5609/acme-platform-infra-sandbox)
   completed worker loop on issue #1. Harness issues #2/#5 closed.
2. **P1 harness quality** — done.
3. **Phase 3 reliability** — #9 in progress (mutation mocks, project sync stub, claim drill).
4. **Adoption kit** — trial-install guide + Windows `.ps1` launchers in place.

## Backlog (Phase 4+)

- Multi-region / multi-repo rollout playbooks
- Optional weekly status rollup (out of scope unless requested)

## Trial notes / friction

- `gh` was missing on the trial machine at first; install via winget before label/issue steps.
- `gh auth login` rejected the git-credential token (`missing required scope 'read:org'`);
  `GH_TOKEN` from git credentials works for `gh api` / issue wrappers in this environment.
- **Bug found in trial:** `gh issue view --json ...subIssues` returns `{nodes,totalCount}`, not a
  list. `normalize_issue` crashed after create; issue #2 was still created. Fixed by accepting both
  shapes.
- Taxonomy lanes still use fleet names (`lane:compute`, …). For harness-only work,
  map wrappers/DX → `lane:platform-api`, CI → `lane:ci-cd`, taxonomy/claim contracts → `lane:foundation`.
- Validation is `python -m unittest discover -s tests -v` (pytest not required).
- First trial issue: [#2](https://github.com/charlesedwardsmith5609/platform-agent-harness/issues/2)
  (packaging / split `repo_issue`).

## Lane ownership (current)

| Lane | Active owner | Current focus |
|---|---|---|
| `lane:foundation` | Coordinator | Taxonomy + claim protocol contracts |
| `lane:compute` | unassigned | n/a in this repo |
| `lane:networking` | unassigned | n/a in this repo |
| `lane:identity` | unassigned | Permissions allowlist / OIDC guidance in skills |
| `lane:observability` | unassigned | Skills only; no OTel pipeline here |
| `lane:ci-cd` | Coordinator | `harness-ci` workflow |
| `lane:platform-api` | Worker-ready | Issue wrappers, wrapper catalog, DX |
| `lane:cost` | unassigned | n/a in this repo |

## Milestones

- **Phase 1: Foundational** — in progress (wrappers, portable permissions, fail-closed claims, CI)
- **Phase 2: Developer Experience** — next (trial install, packaging, install checklist)
- **Phase 3: Reliability** — later (mocked gh coverage expansion, claim concurrency drills)
- **Phase 4: Scale** — later (multi-repo rollout)

## Validation commands

```bash
python -m unittest discover -s tests -v
python setup/apply_permissions.py --dry-run
```
