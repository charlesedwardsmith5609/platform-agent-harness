# Skill: Multi-agent coordination (platform engineering)

**Trigger:** more than one Claude Code instance will work this repo in parallel; or the human says
"spin up a worker on lane X", "start parallel agents", or "set up the coordination board".

**Goal:** let 2–4 Claude Code instances multiply output without stomping on each other or causing
production incidents — by splitting work across **lanes** (platform subsystems), claiming issues
visibly, and shipping through branch → PR → coordinator review → squash-merge.

> **Why GitHub as the coordination layer?** Hidden agent-to-agent negotiation is invisible when
> something goes wrong. In a platform engineering org, a miscoordinated change can affect every
> team in the company. All coordination is git-committed and on the issue — labels, CLAIM comments,
> PRs — searchable, timestamped, and reviewable by the human and the coordinator.

---

## 1. Roles

**Human** — sets direction, approves security/architectural decisions, validates high-blast-radius
changes before they land in production, owns the acceptance test queue.

**Coordinator** (one instance — usually the one in active conversation with the human). Owns:
- Backlog, triage, sequencing, and lane assignment
- The **shared foundation** — OIDC trust model, Terraform module interfaces, base images, SLO
  framework, network policy. These land on the coordinator's branch first; workers rebase.
- Review and merge of every worker PR, plus the competing-model review pass on meaningful changes
- Serializing high-blast-radius work (foundation changes, external-facing API changes) so the
  human is never reviewing more than they can absorb at once
- Does NOT parallel-edit a lane a worker currently owns

**Worker** (one per active lane). Owns exactly **one lane**. Claims issues in it, implements,
validates locally, opens PRs, and hands off. Never touches the shared foundation without
coordinator sign-off. Never grabs work outside its lane. Never self-merges.

---

## 2. Lane boundaries for parallel work

The lane model exists because real architecture seams separate platform subsystems. A compute change
and an observability change rarely touch the same files, so parallel workers don't collide.

**Recommended starting configuration (2–3 workers):**
- `lane:observability` + `lane:ci-cd` (machine-validated, low collision risk — start here)
- Add `lane:compute` or `lane:identity` once the first two are running cleanly
- Keep `lane:networking` serial through the coordinator unless you have an experienced platform
  worker available — networking changes have high blast radius and complex validation
- `lane:foundation` is coordinator-only, always

**Lane collision risk:**
| Pair | Risk | Mitigation |
|---|---|---|
| `compute` + `networking` | HIGH — both touch EKS node/service configs | Coordinator sequences; never parallel |
| `identity` + `networking` | HIGH — OIDC and ingress share trust boundaries | Coordinator sequences |
| `observability` + `ci-cd` | LOW — different files, different subsystems | Safe to parallel |
| `cost` + `observability` | LOW — cost labels, different from metrics pipeline | Safe to parallel |
| any + `foundation` | BLOCKED — foundation lands first, all others rebase | Foundation-first rule |

---

## 3. The shared foundation (non-negotiable)

The following paths are coordinator-gated regardless of which lane the work touches:

```
foundation/terraform/modules/    # Shared Terraform module interfaces
foundation/oidc-trust/           # OIDC workload identity trust model
foundation/base-images/          # Base container image specs
foundation/slo-framework/        # SLO/SLI standards and alert thresholds
foundation/network-policy/       # Cluster-wide network policies
```

A worker branch that touches these paths is a **bug** in the coordination protocol, not just a
process violation. Platform-wide breakage follows. Workers that identify a needed foundation change:

1. Comment on the issue: "Foundation change needed: [describe the specific change and why]"
2. Wait for coordinator to open a `foundation/<slug>` branch and land the change
3. Rebase their worker branch on top of the updated `main`
4. Then proceed with their lane work

---

## 4. Claim protocol (the lock — all three parts required)

The claim is atomic: all three parts must be applied before starting any implementation work.

```bash
# Part 1: status label (the authoritative "in flight, do not grab" signal)
gh issue edit <n> --add-label "status:wip"

# Part 2: CLAIM comment (carries agent handle, branch, and timestamp — what labels can't)
gh issue comment <n> --body "🤖 CLAIM · lane:<X> · worker=<your-handle> · branch=issue/<n>-<slug> · $(date -u +%Y-%m-%dT%H:%M:%SZ)"
```

**Grabbable** means ALL of: open issue, correct `lane:*`, no `status:wip`, no `status:in-review`,
no `blocked` label, no open CLAIM comment. Always check before claiming.

**Release** (if blocked or abandoning):
```bash
gh issue edit <n> --remove-label "status:wip" --add-label "blocked"
gh issue comment <n> --body "🤖 RELEASE · Reason: [blocked by #M / abandoning because X]"
```

**Status label lifecycle:**
`(open, no status)` → `status:wip` (claimed) → `status:in-review` (PR open) → *closed on merge*

---

## 5. Worker loop

```bash
# 1. Sync and isolate
git fetch origin
git switch -c issue/<n>-<slug> origin/main

# If running multiple Claude Code instances on the same machine, use worktrees:
git worktree add ../platform-wt-obs -b issue/<n>-<slug> origin/main
```

Then:
2. **Claim** the issue (§4)
3. **Read skills** — `coding/platform-engineering.md` + the lane-specific skill before writing anything
4. **Implement** — follow platform engineering principles, hardening guidelines, and the lane's
   validation mode. Comment the *why*, not the *what*. Reference `(#<n>)` in commit messages.
5. **Validate locally** — run each validation command as its own separate call. Never chain with
   `&&` or pipes. Never open a red PR.
   ```bash
   terraform validate        # separate call
   terraform fmt -check -recursive   # separate call
   tflint --recursive        # separate call
   pytest tests/ -v          # separate call
   ```
6. **Open PR:**
   ```bash
   git push -u origin issue/<n>-<slug>
   gh pr create \
     --base main \
     --title "<concise summary> (#<n>)" \
     --body "Closes #<n>

   ## What changed
   [What was done and why]

   ## Validation
   [Results of each local validation command]

   ## Blast radius
   [Which systems/teams are affected and how]"
   ```
7. **Update labels:** `gh issue edit <n> --remove-label "status:wip" --add-label "status:in-review"`
8. **Append acceptance scenarios** to `docs/test-scenarios/pending.md` for any change that
   requires human or integration verification
9. **Hand off to coordinator** — the PR is the handoff. A brief issue comment noting the PR is
   open is optional but helpful.
10. **Re-triage your lane** before declaring it empty — `gh issue list --label "lane:<X>" --state open`

---

## 6. Coordinator PR review checklist

For each worker PR:

1. **Rebase check** — is the branch current with `main`? If it touched foundation paths, was the
   foundation change landed first on `main`?
2. **Blast radius assessment** — what does this change affect? Is the blast radius appropriately
   scoped to the lane?
3. **Validation completeness** — did the worker run all required validation commands and report
   results? Does the PR description include blast radius?
4. **Security review** — does this change touch the OIDC trust model, IAM roles, network policies,
   or secrets? If so, flag for human security review before merge.
5. **Competing-model review** — for meaningful changes (more than config updates or doc edits),
   run the review agent (see `workflow/code-review-agent.md`). One review per PR, coordinator-only.
6. **Merge:**
   ```bash
   gh pr merge <n> --squash --delete-branch
   ```
   Confirm the issue auto-closed. Strip any `status:*` labels.
7. **Serialize high-blast-radius work** — don't merge a networking change and a foundation change
   in the same 30-minute window. Give the human time to see what landed.

---

## 7. Coordinator kickoff prompt (paste into a new Claude Code session)

```
You are the COORDINATOR agent on the [YOUR ORG] platform engineering repo.

Read in this order:
1. CLAUDE.md
2. docs/STATUS.md
3. .github/skills/workflow/multi-agent-coordination.md
4. .github/skills/workflow/issue-triage.md

Your responsibilities:
- Triage open issues without milestones
- Review and merge open PRs from workers (apply the coordinator PR checklist)
- Manage the shared foundation — nothing in foundation/ lands from a worker branch
- Sequence high-blast-radius work so the human isn't overwhelmed
- Launch worker kickoff prompts for lanes with queued work

Do not start implementing lane work yourself unless there are no workers and the human asks.
```

---

## 8. Worker kickoff prompt (paste into a new Claude Code session)

```
You are a WORKER agent on the [YOUR ORG] platform engineering repo, lane = lane:<X>.

Read in this order:
1. CLAUDE.md
2. .github/skills/workflow/multi-agent-coordination.md
3. .github/skills/coding/platform-engineering.md
4. [lane-specific skill, e.g. .github/skills/coding/observability.md]

Worker loop:
1. Find the highest-priority GRABBABLE issue with label lane:<X> —
   open, no status:wip/in-review/blocked, no open CLAIM comment
2. CLAIM it: add status:wip label + post CLAIM comment with your handle + branch + timestamp
3. git fetch origin && git switch -c issue/<n>-<slug> origin/main
4. Read relevant coding skills before implementing
5. Implement following platform engineering principles and security hardening
6. Validate locally (each command as a separate call — never chain)
7. Open PR with Closes #<n>, blast radius, and validation results
8. Set status:in-review, drop status:wip
9. Append docs/test-scenarios/pending.md scenarios for human/integration verification
10. Hand PR to coordinator — do NOT self-merge
11. Re-triage your lane before declaring it empty

Never touch foundation/ — propose changes on the issue and wait for the coordinator.
Never grab issues outside lane:<X>. Never self-merge.
```

---

## 9. GitHub setup (one time)

```bash
# Lane labels
gh label create "lane:foundation"    -c "#1D76DB" -d "Shared foundation: Terraform modules, OIDC trust, base images, SLO framework — COORDINATOR ONLY"
gh label create "lane:compute"       -c "#0E8A16" -d "EKS/Kubernetes fleet, node groups, resource management"
gh label create "lane:networking"    -c "#5319E7" -d "Envoy Proxy, API gateway, service mesh, TLS/mTLS, ingress"
gh label create "lane:identity"      -c "#E4E669" -d "OIDC workload identity, secrets management, cert rotation, RBAC"
gh label create "lane:observability" -c "#006B75" -d "OTel pipeline, SLO/SLI alert rules, dashboards, on-call routing"
gh label create "lane:ci-cd"         -c "#BFD4F2" -d "Deployment pipelines, release automation, build infrastructure"
gh label create "lane:platform-api"  -c "#C2E0C6" -d "Internal developer APIs, service onboarding, self-service tooling"
gh label create "lane:cost"          -c "#F9D0C4" -d "Cost attribution, FinOps dashboards, budget alerts"

# Status labels
gh label create "status:wip"          -c "#D93F0B" -d "Claimed and in progress — do NOT grab"
gh label create "status:in-review"    -c "#FBCA04" -d "PR open, awaiting coordinator review"

# Type labels
gh label create "bug"          -c "#D73A4A" -d "Something is broken — P0/P1 only"
gh label create "feature"      -c "#A2EEEF" -d "New platform capability"
gh label create "enhancement"  -c "#84B6EB" -d "Improving an existing capability"
gh label create "hardening"    -c "#E4E669" -d "Defensive improvement, tech debt, validation gaps"

# Priority labels
gh label create "P0" -c "#B60205" -d "Production incident or imminent security exploit — drop everything"
gh label create "P1" -c "#D93F0B" -d "Every other bug; or non-bug blocking another team"
gh label create "P2" -c "#E4E669" -d "Important non-bug; complete this sprint"
gh label create "P3" -c "#0075CA" -d "Lower priority; next cycle"
gh label create "P4" -c "#CFD3D7" -d "Nice to have; backlog"

# Concern labels
gh label create "security"          -c "#B60205" -d "Has a security dimension"
gh label create "blocked"           -c "#000000" -d "Waiting on a dependency"
gh label create "incident-follow-up" -c "#E4E669" -d "Created from postmortem; prioritize"
```
