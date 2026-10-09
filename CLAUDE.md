# Platform Engineering Agent Harness

> **Read this file first** before doing anything in this repository.
> Agents: also read `docs/STATUS.md` and the skills relevant to your task before starting work.

---

## Repository identity

This repository is the **platform engineering agent harness** (coordination layer): issue
taxonomy, claim protocol, portable permissions, and workflow skills that agents load before
touching infrastructure work. It is currently in a **dogfood trial on itself** — see
`docs/STATUS.md` and `docs/guides/trial-install.md`.

When copied into a real infra org repo, adapt this section to that org's compute, networking,
identity, observability, CI/CD, and developer platform ownership. Blast radius there is
org-wide; in this harness repo, blast radius is agent workflow and GitHub hygiene only.

---

## Development arc

**Current state:** Taxonomy-bound `repo_issue.py`, portable permissions, fail-closed claims, harness-ci.
**Active work:** Dogfood trial (labels/milestones/first issues via wrappers); P1 packaging/split.
**Next milestone:** Phase 2 developer experience — install checklist proven, `pyproject.toml`, cleaner CLI.

---

## Architecture overview

```
setup/            Issue wrappers, taxonomy, permissions, wrapper catalog
.github/skills/   Workflow + coding skills agents must load before changes
.github/workflows/Harness CI (unittest + taxonomy/permission sanity)
docs/             STATUS, guides, review ledger, test scenarios
tests/            Unit tests for taxonomy, permissions, claim races
foundation/       (reserved when this harness is installed into a fleet repo)
```

Validation commands (run these before opening any PR):
```bash
python -m unittest discover -s tests -v
python setup/apply_permissions.py --dry-run
```

---

## Core model: who does what

Platform infrastructure work requires **human approval of product/security decisions** and
**agent execution of implementation**. Never blur these.

| Human owns | Coordinator owns | Worker owns |
|---|---|---|
| Product direction, security architecture decisions, cost budget approvals, SLO target setting | Backlog, triage, sequencing, lane assignment, shared foundation, PR review + merge, competing-model review | One lane — claims issues in it, implements, validates locally, opens PRs, appends acceptance scenarios |
| May describe an initiative or file a blank issue | Converts intent into classified issues, identifies foundation changes needed, proposes lane structure | Never touches the shared foundation without coordinator sign-off |
| Validates any change affecting external service contracts | Serializes high-blast-radius work so the human can review before it lands in production | Never self-merges |

**GitHub is the coordination layer.** Decisions, blockers, claims, and handoffs live on issues and
PRs — not in conversation. Any agent on any machine can read the state and continue.

---

## Shared foundation (coordinator-owned — no exceptions)

These are the load-bearing contracts the entire platform depends on. Editing them from two branches
simultaneously is how parallel work causes production incidents.

**Foundation files/contracts:**
- `foundation/terraform/modules/` — shared Terraform module interfaces and outputs
- `foundation/oidc-trust/` — OIDC workload identity trust model, IAM role bindings
- `foundation/base-images/` — base container image specifications and tags
- `foundation/slo-framework/` — SLO/SLI standards, alerting thresholds, error budget rules
- `foundation/network-policy/` — cluster-wide network policies, ingress rules

**The rule:** any change to the shared foundation lands on the coordinator's branch **first**,
before any worker branch that depends on it. Workers that need a foundation change **propose it
in an issue comment** and wait for the coordinator to land it. Then rebase. This is non-negotiable —
a foundation change mid-flight in a worker branch is the primary way parallel platform work corrupts
the environment.

---

## Lanes

A lane is a platform subsystem with its own ownership. Every issue gets **exactly one `lane:*` label**
at the moment it is filed — not after triage — so it is immediately routable.

| Lane | Scope | Validation | Blast radius | Owner |
|---|---|---|---|---|
| `lane:foundation` | Shared Terraform modules, OIDC trust model, base images, SLO framework, network policy | 🟡 terraform validate + integration | **ORG-WIDE — coordinator only** | Coordinator |
| `lane:compute` | EKS cluster config, node groups, Karpenter, resource quotas, Kubernetes version upgrades | 🟡 cluster validation + integration | HIGH (all workloads) | Worker |
| `lane:networking` | Envoy Proxy, API gateway config, service mesh, TLS/mTLS, ingress, DNS | 🟡 traffic validation | HIGH (service-to-service) | Worker |
| `lane:identity` | OIDC issuer, workload identity, secrets management platform, cert rotation, RBAC | 🟡 identity validation | HIGH (security boundary) | Worker |
| `lane:observability` | OTel collectors, metrics pipeline, SLO alert rules, dashboards, on-call routing | 🟢 alert rule tests + integration | MEDIUM | Worker |
| `lane:ci-cd` | Deployment pipelines, release automation, artifact management, build infrastructure | 🟢 pipeline tests | MEDIUM (deploy velocity) | Worker |
| `lane:platform-api` | Internal developer APIs, service onboarding automation, self-service tooling | 🔴 human acceptance testing | MEDIUM (developer experience) | Worker — serial through coordinator for external-facing changes |
| `lane:cost` | Cost attribution labels, FinOps dashboards, budget alerts, chargeback tooling | 🟢 unit + integration | LOW | Worker |

**Validation modes:**
- 🟢 Machine-validated: tests close it, minimal human review needed
- 🟡 Infra-validated: requires cluster/cloud validation, not just tests
- 🔴 Human acceptance: requires a human to verify the behavior before merge

---

## Issue taxonomy

Every issue gets **one type + one priority + one lane + optional concerns** at creation.

**Type:**
- `bug` — something is broken in production or will break on next deploy. **P0/P1 only.**
- `feature` — new platform capability that doesn't exist yet
- `enhancement` — improving an existing, working capability
- `hardening` — not broken, but needs defensive improvement: missing validation, weak error handling,
  tech debt, security defense-in-depth. *If you're tempted to file a P2+ bug, it's almost always this.*

**Concerns (add alongside type):**
- `security` — has a security dimension; on a `bug` = fix immediately
- `blocked` — waiting on a dependency; add `Blocked by #N` in the body
- `incident-follow-up` — created from an incident postmortem; prioritize above normal enhancement work

**Priority:**
- `P0` — production incident or imminent security exploit. Drop everything.
- `P1` — every other bug; or non-bug work blocking another team's delivery
- `P2` — important non-bug work; complete within current sprint/cycle
- `P3` — lower priority; schedule when capacity allows
- `P4` — nice to have; backlog

**Attack order:** `P0` bugs → `P1` bugs → `security` non-bugs → `incident-follow-up` → everything else by priority.

---

## Skills to load

Load the relevant skills before doing work in that area. Skills are in `.github/skills/`.

| Task | Skills to read |
|---|---|
| Any code/config change | `coding/platform-engineering.md` + `coding/security-hardening.md` |
| Compute / Kubernetes / Terraform | `coding/platform-engineering.md` + `coding/security-hardening.md` (lane-specific skills TBD) |
| Observability/SLO work | `coding/observability.md` |
| Filing or triaging issues | `workflow/issue-triage.md` + `setup/wrapper-catalog.md` |
| Multi-agent parallel work | `workflow/multi-agent-coordination.md` |
| PR review | `workflow/code-review-agent.md` |
| User-acceptance scenarios | `workflow/human-test-scenarios.md` |

---

## Agent workflows

Consult `setup/wrapper-catalog.md` before using GitHub issue commands. Issue create, list, view,
classify, hierarchy, claim, release, and in-review go through `python setup/repo_issue.py`.

### Filing a new issue

Apply the full taxonomy at creation — type + priority + lane + concerns. Leave milestone empty
(empty milestone = untriaged signal). The coordinator's triage sweep adds the milestone and rationale.

Write the body to a Git-ignored file first (`*.issue-body.local.md`), then:

```bash
python setup/repo_issue.py create \
  --title "concise description of the problem" \
  --body-file scratch.issue-body.local.md \
  --type hardening \
  --priority P2 \
  --lane lane:observability
# Repeat --concern security or --concern blocked when applicable
# Do NOT pass --milestone (intentionally left empty until triage)
```

### Claiming an issue (the lock — applied as one wrapper)

```bash
python setup/repo_issue.py claim \
  --issue <n> \
  --lane lane:observability \
  --worker <handle> \
  --branch issue/<n>-<slug>
```

The wrapper posts a structured CLAIM comment first (unique id), re-reads to elect the earliest
active claim, then adds `status:wip`. Losers fail closed and RELEASE themselves. An issue is
grabbable iff: open, correct `lane:*`, not `status:wip`/`status:in-review`/`blocked`, no active
structured CLAIM marker.

### Worker loop

1. Find highest-priority grabbable issue in your lane
2. `git fetch origin && git switch -c issue/<n>-<slug> origin/main`
3. Claim (§above)
4. Read the relevant skills before coding
5. Implement, following platform engineering principles and security hardening guidelines
6. Validate locally — run each validation command as its own call, never chain with `&&`
7. Open PR: `gh pr create --base main --title "<summary> (#<n>)" --body "Closes #<n>\n\n<what/why + validation results>"`
8. `python setup/repo_issue.py in-review --issue <n>`
9. Append human acceptance scenarios to `docs/test-scenarios/pending.md` if the change needs human verification
10. Hand off to coordinator. **Never self-merge.**
11. Re-triage your lane before declaring it empty — issues are filed while you work.

### Coordinator duties per PR

1. Rebase check — branch current with `main`; if it touched the foundation, verify it went through the foundation process
2. Review diff for correctness + platform engineering principles + security hardening
3. For meaningful code changes: run the competing-model review (see `workflow/code-review-agent.md`)
4. Merge: `gh pr merge <n> --squash --delete-branch`
5. Confirm issue auto-closed; strip `status:*` labels
6. Serialize human-acceptance / high-blast-radius work — don't let multiple foundation or networking changes land faster than the human can review

---

## Guardrails (never violate)

- Never grab an issue that is `status:wip` / `status:in-review` / `blocked` / already CLAIMed, or outside your lane
- Never touch the **shared foundation** from a worker branch — propose in a comment, wait for coordinator to land it, then rebase
- Never self-merge
- Validate locally before the PR; never open a PR that fails its own validation
- `lane:foundation` is coordinator-only, always
- Emit one status event after the meaningful milestone (PR opened or merged)

---

## Branch conventions

- Worker branches: `issue/<n>-<short-slug>`
- Coordinator/foundation branches: `foundation/<slug>`
- One issue per PR where practical
- `Closes #<n>` in the PR body — merging to `main` auto-closes
- Squash-merge only (coordinator): keeps `main` history clean

---

## Status reporting

After each meaningful milestone (PR opened, PR merged, incident resolved), emit a brief status event
on the issue (what changed, blast radius, next risk). Keep status on issues/PRs — not in hidden
conversation. Optional weekly rollups can be added later; there is no separate status playbook yet.
