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
      observability.md             # OTel, SLO/SLI, alerting patterns
      security-hardening.md        # OIDC, IAM, RBAC, secrets, network policies
setup/
  wrapper-catalog.md               # Approved command surfaces (read before raw gh/git)
  project-taxonomy.json            # Authoritative labels, lanes, milestones
  platform_harness/                # Packaged issue lifecycle (remote/ops/cli)
  repo_issue.py                    # Thin CLI shim → platform_harness
  create_labels.py                 # Create/reconcile taxonomy labels
  agent-permissions.json           # Portable permission source (placeholder root)
  apply_permissions.py             # Materialize permissions into gitignored local files
  apply_permissions.ps1            # PowerShell launcher for apply_permissions.py
  create-labels.sh                 # Bash launcher for create_labels.py
  create-labels.ps1                # PowerShell launcher for create_labels.py
pyproject.toml                     # Installable package + repo-issue console script
docs/
  STATUS.md                        # Current state, active work, milestone progress
  guides/
    trial-install.md               # Dogfood / first-repo trial checklist
    permissions-and-security.md    # Allowlist and wrapper rules
  test-scenarios/
    pending.md                     # Validation scenarios awaiting human/integration testing
    archive/                       # Confirmed scenarios (moved here after validation)
  review-ledger.md                 # Record of competing-model review passes
tests/
  test_repo_issue.py               # Taxonomy, permissions, and claim-race unit tests
.github/workflows/
  harness-ci.yml                   # unittest + taxonomy/permission sanity on PRs
```

---

## Setup (one time per repository)

**1. Install the harness files into your infrastructure repo**

```bash
# Clone or copy the harness structure into your existing repo
cp CLAUDE.md /path/to/your-infra-repo/
cp -r .github/skills /path/to/your-infra-repo/.github/
```

**2. Adapt CLAUDE.md to your repository**

Fill in the `PROJECT-SPECIFIC` sections:
- Repository identity and what it owns
- Development arc (current state, active work, next milestone)
- Architecture overview (your actual directory structure)
- Validation commands (your actual test/validate commands)
- Lane definitions (adapt to your actual subsystem boundaries)

**3. Create labels and milestones**

```bash
cd /path/to/your-infra-repo
python setup/create_labels.py --plan
python setup/create_labels.py

# Create delivery phase milestones named in setup/project-taxonomy.json
gh milestone create "Phase 1: Foundational" --description "Core infrastructure that everything depends on"
gh milestone create "Phase 2: Developer Experience" --description "Self-service, onboarding, tooling"
```

Issue create/classify/claim after that uses `python setup/repo_issue.py`. See
[`setup/wrapper-catalog.md`](setup/wrapper-catalog.md).

Apply portable permissions only when the human asks:

```bash
python setup/apply_permissions.py --dry-run
python setup/apply_permissions.py
```

**4. Create docs/STATUS.md**

Describe current production state, active initiatives, and the lane model for your specific
architecture. This is what agents read to understand context before starting work.

**5. Start the coordinator agent**

Open Claude Code in your infrastructure repo and paste the coordinator kickoff prompt from
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

The `code-review-agent.md` skill references `agent-harness/agents/pr_reviewer.py` directly
for structured PR security and reliability reviews.

---

## Relationship to the source

This harness is a port of a Copilot-native agentic development coordination system, adapted for:

- **Claude Code** instead of GitHub Copilot (CLAUDE.md instead of copilot-instructions.md)
- **Platform engineering** instead of application development (infra lanes, blast radius, OIDC,
  SLOs replace renderer, UI, and animation lanes)
- **Claude API execution harness** instead of a competing-model review via a separate AI service
- **Bash** instead of PowerShell for setup scripts

The core insights from the original are preserved: GitHub as the coordination layer, visible
claims with timestamped provenance, shared foundation protection, role separation between
coordinator and workers, skills-as-composable-markdown that agents load on demand, taxonomy-bound
issue wrappers, and portable permission sources that never commit machine-specific absolute paths.
