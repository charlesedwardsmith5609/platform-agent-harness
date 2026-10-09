# platform-agent-harness

An issue-driven, agent-first development harness for platform engineering teams running one or
more Claude Code agents on infrastructure repositories — without making chat history, one machine,
or one agent's memory the source of truth.

Adapted from an agentic development coordination system originally built for game engine development.
This port applies the same coordination principles to platform engineering work: Kubernetes, Terraform,
observability pipelines, secrets management, CI/CD, and internal developer tooling.

---

## What this solves

Platform infrastructure repositories have a specific challenge that product feature repos don't:
**changes here affect every engineering team in the company.** A misconfigured Terraform module or
OIDC trust policy doesn't break one feature — it can break all of production.

Running AI coding agents on infrastructure without coordination is dangerous. This harness provides:

- **Issue-driven coordination** — every task is a GitHub issue with type, priority, lane, and
  blast radius before any agent touches it
- **Coordinator/worker role separation** — one agent manages the backlog, reviews PRs, and owns
  the shared foundation; workers implement within clearly bounded lanes
- **Atomic claim protocol** — agents can't collide on the same work; the claim is visible and
  timestamped on the issue itself
- **Shared foundation protection** — OIDC trust, Terraform module interfaces, base images, and
  SLO frameworks are coordinator-gated with no exceptions
- **Competing-model review** — PRs get an independent security and reliability review from a
  different AI provider before merge
- **Skills library** — agents load the right guidance for their specific task before writing anything

**GitHub is the coordination layer.** All decisions, claims, and handoffs are on issues and PRs —
not in invisible conversation. Any agent on any machine can read the state and continue safely.

---

## Repository structure

```
CLAUDE.md                          # Main agent instructions (read this first)
.github/
  skills/
    workflow/
      multi-agent-coordination.md  # Coordinator/worker model, claim protocol, worker loop
      issue-triage.md              # Platform engineering issue taxonomy
      code-review-agent.md         # Competing-model review process
      human-test-scenarios.md      # Infrastructure validation scenarios
    coding/
      platform-engineering.md      # Core platform principles (load for all code changes)
      kubernetes.md                # Cluster, workloads, PDBs, upgrades
      terraform.md                 # IaC, modules, plan/destroy discipline
      observability.md             # OTel, SLO/SLI, alerting patterns
      security-hardening.md        # OIDC, IAM, RBAC, secrets, network policies
github-actions/
  secrets-injection.yml            # Example OIDC CI credentials (not a live workflow here)
playbooks/
  feature-decomposition.md         # Split initiatives into classified issues
  incident-response.md             # Post-incident GitHub follow-ups
  status-reporting.md              # STATUS comment format
setup/
  setup-guide.md                   # Index of install docs (not a second procedure)
  wrapper-catalog.md               # Approved command surfaces (read before raw gh/git)
  project-taxonomy.json            # Authoritative labels, lanes, milestones
  platform_harness/                # Packaged issue lifecycle (remote/ops/cli)
  repo_issue.py                    # Thin CLI shim → platform_harness
  create_labels.py                 # Create/reconcile taxonomy labels
  sync_harness_to_repo.py          # Copy allowlisted files into a consumer repo
  agent-permissions.json           # Portable permission source (placeholder root)
  apply_permissions.py             # Materialize permissions into gitignored local files
  apply_permissions.ps1            # PowerShell launcher for apply_permissions.py
  create-labels.sh                 # Bash launcher for create_labels.py
  create-labels.ps1                # PowerShell launcher for create_labels.py
  pr_gate.py                       # PR hygiene gate (Closes #, blast radius, foundation paths)
pyproject.toml                     # Installable package + repo-issue console script
docs/
  STATUS.md                        # Current state, active work, milestone progress
  guides/
    trial-install.md               # Dogfood / first-repo trial checklist
    permissions-and-security.md    # Allowlist and wrapper rules
    project-board.md               # Optional GitHub Project lane sync
    claim-concurrency-drill.md     # Live fail-closed claim drill
    multi-repo-rollout.md          # Install harness into consumer infra repos
    five-minute-demo.md            # Live demo script for claim → PR → velocity
  test-scenarios/
    pending.md                     # Validation scenarios awaiting human/integration testing
    archive/                       # Confirmed scenarios (moved here after validation)
  review-ledger.md                 # Record of competing-model review passes
tests/
  test_repo_issue.py               # Taxonomy, permissions, and claim-race unit tests
  test_velocity_features.py        # WIP limits, velocity, pr-draft, doctor score, PR gate
.github/workflows/
  harness-ci.yml                   # unittest + taxonomy/permission sanity on PRs
  pr-gate.yml                      # Coordination hygiene gate on pull requests
```

**Velocity features:** per-lane `wip_limit`, `repo_issue.py velocity|pr-draft|sweep-stale|scaffold`,
`doctor --target` adoption scores, and PR gate checks for `Closes #` / blast radius / foundation paths.

---

## Setup (one time per repository)

Do not ad-hoc `cp` a subset of files. Follow:

- **This repo (dogfood):** [`docs/guides/trial-install.md`](docs/guides/trial-install.md)
- **Consumer infra repo:** [`docs/guides/multi-repo-rollout.md`](docs/guides/multi-repo-rollout.md)

Short index: [`setup/setup-guide.md`](setup/setup-guide.md).

**1. Sync allowlisted harness files** (from a clone of this repo):

```bash
python setup/sync_harness_to_repo.py --target /path/to/your-infra-repo --dry-run
python setup/sync_harness_to_repo.py --target /path/to/your-infra-repo --force
```

**2. Adapt CLAUDE.md** in the consumer repo (`--include-identity` is usually wrong for real orgs):

- Repository identity and what it owns
- Development arc (current state, active work, next milestone)
- Architecture overview (directories that actually exist)
- Validation commands (only commands that run in that repo)
- Lane definitions (adapt to subsystem boundaries)

**3. Create labels and milestones** (names must match `setup/project-taxonomy.json`):

```bash
python setup/create_labels.py --plan
python setup/create_labels.py
```

Create milestones with `gh api` as in trial-install — not `gh milestone create`.

Issue create/classify/claim uses `python setup/repo_issue.py`. See
[`setup/wrapper-catalog.md`](setup/wrapper-catalog.md).

Apply portable permissions only when the human asks:

```bash
python setup/apply_permissions.py --dry-run
python setup/apply_permissions.py
```

**4. Adapt docs/STATUS.md** (already present after sync of identity, or write it if the consumer had none).

**5. Start the coordinator agent**

Open a coding-agent session in the infrastructure repo and paste the coordinator kickoff prompt from
`.github/skills/workflow/multi-agent-coordination.md`.

---

## Lane model

Lanes map to real architecture subsystems — not invented categories. The default lanes are
a starting point; adapt them to your actual architecture boundaries.

| Lane | Default scope | Validation | Blast radius |
|---|---|---|---|
| `lane:foundation` | Shared Terraform modules, OIDC trust, base images, SLO framework | Infra | Org-wide — coordinator only |
| `lane:compute` | Kubernetes fleet, node management | Infra | High |
| `lane:networking` | API gateway, service mesh, ingress | Infra | High |
| `lane:identity` | OIDC, secrets, RBAC, certs | Infra + Security review | High |
| `lane:observability` | OTel pipeline, SLOs, alerting | Machine + Infra | Medium |
| `lane:ci-cd` | Deployment pipelines, release automation | Machine | Medium |
| `lane:platform-api` | Self-service tooling, onboarding APIs | Human acceptance | Medium |
| `lane:cost` | FinOps, cost attribution | Machine | Low |

Design your lanes with the coordinator agent first:

```
Review this repo's architecture and propose a lane model for parallel agent work.
Identify the shared foundation, the dominant subsystem seams, each lane's validation
mode (machine, infra, or human-acceptance), likely file ownership, and collision risks.
```

---

## Integration with the agent-harness execution layer

This harness handles **project coordination** — how agents divide and track work. The
`agent-harness/` repository in this organization handles **execution** — how individual
Claude API calls run with OTel tracing, cost governance, and confidence gating.

The two complement each other:

```
platform-agent-harness (this repo)         agent-harness
─────────────────────────────────          ─────────────
issue taxonomy + routing            ──→    pr_reviewer.py (code review gate)
coordinator/worker coordination     ──→    deploy_risk.py (deployment gate)
skills library + CLAUDE.md          ──→    runbook_gen.py (post-incident docs)
GitHub as coordination layer        ──→    OTel tracing on every agent run
```

Wire them only if that sibling repo is available. `.github/skills/workflow/code-review-agent.md`
describes the competing-model review that always works from this harness, and optionally
invokes `agent-harness/agents/pr_reviewer.py` when that tree is checked out next to the
infra repo.

---

## Relationship to the source

This harness is a port of a Copilot-native agentic development coordination system, adapted for:

- **Claude Code** instead of GitHub Copilot (CLAUDE.md instead of copilot-instructions.md)
- **Platform engineering** instead of application development (infra lanes, blast radius, OIDC,
  SLOs replace renderer, UI, and animation lanes)
- **Claude API execution harness** instead of a competing-model review via a separate AI service
- **Python wrappers** plus Bash *and* PowerShell launchers for labels and permissions

The core insights from the original are preserved: GitHub as the coordination layer, visible
claims with timestamped provenance, shared foundation protection, role separation between
coordinator and workers, skills-as-composable-markdown that agents load on demand, taxonomy-bound
issue wrappers, and portable permission sources that never commit machine-specific absolute paths.
