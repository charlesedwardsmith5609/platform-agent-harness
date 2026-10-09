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

## 4. Claim protocol (the lock — one wrapper)

Claims are **fail-closed**, not magically atomic on GitHub. The wrapper uses a structured
comment marker as the lock stream, then verifies ownership before work starts.

```bash
python setup/repo_issue.py claim \
  --issue <n> \
  --lane lane:<X> \
  --worker <your-handle> \
  --branch issue/<n>-<slug>
```

Protocol inside the wrapper:
1. Preflight: refuse if not grabbable
2. Post `<!-- harness:claim v1 id=<uuid> -->` comment (unique id)
3. Re-read comments; earliest active structured claim wins
4. Losers immediately post a structured RELEASE and exit non-zero
5. Winner adds `status:wip` and re-verifies sole ownership

Free-text mentions of the word "CLAIM" do **not** count. Only harness markers do.

**Grabbable** means ALL of: open issue, correct `lane:*`, no `status:wip`, no `status:in-review`,
no `blocked` label, no active structured CLAIM. The wrapper refuses otherwise.

**Release** (explicit mode required):
```bash
python setup/repo_issue.py release --issue <n> --mode abandon --reason-file scratch.rationale.local.md
python setup/repo_issue.py release --issue <n> --mode blocked --reason-file scratch.rationale.local.md
```

Both post `<!-- harness:release v1 id=* -->` and clear `status:wip`.
`--mode blocked` also adds `blocked`; `--mode abandon` does not.

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
2. **Claim** the issue (§4) — wrapper posts a structured CLAIM, then `status:wip`
3. **Read skills** — `coding/platform-engineering.md` + the lane-specific skill before writing anything
4. **Implement** — follow platform engineering principles, hardening guidelines, and the lane's
   validation mode. Comment the *why*, not the *what*. Reference `(#<n>)` in commit messages.
5. **Validate locally** — run each validation command from `CLAUDE.md` as its own separate call.
   Never chain with `&&` or pipes. Never open a red PR.
   In this harness repo:
   ```bash
   python -m unittest discover -s tests -v
   python setup/apply_permissions.py --dry-run
   ```
   In a fleet repo, use that repo's Terraform/cluster commands instead.
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
7. **Update labels:** `python setup/repo_issue.py in-review --issue <n>`
8. **Append acceptance scenarios** to `docs/test-scenarios/pending.md` for any change that
   requires human or integration verification
9. **Hand off to coordinator** — the PR is the handoff. A brief issue comment noting the PR is
   open is optional but helpful.
10. **Re-triage your lane** before declaring it empty — `python setup/repo_issue.py list --state open` and keep only issues labeled `lane:<X>`

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
   open, no status:wip/in-review/blocked, no active structured CLAIM marker
2. git fetch origin; git switch -c issue/<n>-<slug> origin/main
3. CLAIM it: `python setup/repo_issue.py claim --issue <n> --lane lane:<X> --worker <handle> --branch issue/<n>-<slug>`
4. Read relevant coding skills before implementing
5. Implement following platform engineering principles and security hardening
6. Validate locally (each command as a separate call — never chain)
7. Open PR with Closes #<n>, blast radius, and validation results
8. `python setup/repo_issue.py in-review --issue <n>`
9. Append docs/test-scenarios/pending.md scenarios for human/integration verification
10. Hand PR to coordinator — do NOT self-merge
11. Re-triage your lane before declaring it empty

Never touch foundation/ — propose changes on the issue and wait for the coordinator.
Never grab issues outside lane:<X>. Never self-merge.
```

---

## 9. GitHub setup (one time)

Labels come from `setup/project-taxonomy.json`. Preview, then create:

```bash
python setup/create_labels.py --plan
python setup/create_labels.py
```

To restore color and description for taxonomy-owned labels without touching others:

```bash
python setup/create_labels.py --reconcile
```
