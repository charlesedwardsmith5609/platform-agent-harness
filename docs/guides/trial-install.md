# Trial install (dogfood)

Use this checklist to run the harness against a real GitHub repository for the
first time. The default trial target is **this repository**
(`platform-agent-harness`) so coordination can be exercised without touching a
production fleet.

Notes: `pr-draft` returns `gh_command` (POSIX shell quoting, or Windows quoting on `nt`) and `gh_argv`
(the portable argument list). Body files must be physical `.local.md` files: a symlink at any path
component under the repository root is rejected.

## Fast path (recommended)

From a clean checkout of this repo on `main`:

```bash
# Windows
.\setup\trial-local.ps1 -Worktree

# Unix
bash setup/trial-local.sh --worktree

# Optional: full create→classify→claim→release→close against GitHub
python setup/trial_local.py --worktree --smoke
```

This installs the package, pulls `GH_TOKEN` from git credentials when needed,
runs doctor, ensures labels/milestones, materializes local permissions, writes
gitignored trial body templates, and (with `--worktree`) creates
`../platform-agent-harness-trial-worker`.

## Preconditions

- [ ] `git` and `python` 3.11+ on PATH
- [ ] `gh` on PATH (token may come from git credentials via the bootstrap)
- [ ] Working tree on `main`, clean enough to commit STATUS / CLAUDE adaptations
- [ ] Human present for the first real claim if you skip `--smoke`

## Manual steps (if you prefer not to use the bootstrap)

1. **Fill identity** — adapt `CLAUDE.md` repository identity, development arc, and
   validation commands to the trial repo (not fictional platform folders if this
   repo has none).
2. **Fill status** — rewrite `docs/STATUS.md` with current state, active
   initiatives, and lane ownership for the trial.
3. **Doctor** (taxonomy + sync paths; add `gh` probes when online)

   ```bash
   python setup/repo_issue.py doctor --offline
   python setup/repo_issue.py doctor
   ```

4. **Create labels**

   ```bash
   python setup/create_labels.py --plan
   python setup/create_labels.py
   ```

5. **Create milestones** named exactly as in `setup/project-taxonomy.json`

   ```bash
   gh api repos/{owner}/{repo}/milestones -f title="Phase 1: Foundational" -f description="Core infrastructure that everything else depends on"
   gh api repos/{owner}/{repo}/milestones -f title="Phase 2: Developer Experience" -f description="Self-service, onboarding, developer tooling"
   gh api repos/{owner}/{repo}/milestones -f title="Phase 3: Reliability" -f description="SLO framework, advanced observability, chaos engineering"
   gh api repos/{owner}/{repo}/milestones -f title="Phase 4: Scale" -f description="Cost optimization, multi-region, advanced security"
   ```

6. **Optional permissions** (human only)

   ```bash
   python setup/apply_permissions.py --dry-run
   python setup/apply_permissions.py
   ```

7. **File the first issue** through the wrapper (body in a Git-ignored file):

   ```bash
   python setup/repo_issue.py create \
     --title "..." \
     --body-file scratch.issue-body.local.md \
     --type hardening \
     --priority P2 \
     --lane lane:ci-cd
   ```

8. **Classify** (coordinator triage) with a milestone + rationale file.
9. **Claim** from a worker branch, or stop after create/classify if this is a
   coordination-only smoke test.
10. **Record friction** in `docs/STATUS.md` under Active initiatives / trial notes.

## Enforce it on the server

The permission files (`setup/agent-permissions.json`, `.claude/settings.json`) are a seatbelt,
not a sandbox (`CLAUDE.md`, "Tool and network policy"). The GitHub settings below are the
control. They enforce "Never self-merge" (`CLAUDE.md`, Guardrails and Worker loop) and the
coordinator-owned shared foundation (`CLAUDE.md`, "Shared foundation"). The coordinator sets
them in the repository settings; no script in this repo sets or runs the checks below.

1. **Branch protection on `main`**: require a pull request, at least one approving review, code
   owner review, dismiss stale approvals, include administrators, and block force pushes and
   deletions. A repository ruleset with the same rules is an equivalent alternative.
2. **Agent identity without merge or admin rights.** The agent uses its own account or app,
   never the coordinator's, with a fine-grained token scoped to this one repository (or its
   fork). It is on no bypass list. Required reviews alone do not stop merging, because a Write
   role can merge an approved PR. State the merge restriction separately, in one of two ways:
   - (a) Restrict who can update `main` to the coordinator: a ruleset "Restrict updates" rule
     with only the coordinator on the bypass list, or, on organization repositories, branch
     protection "Restrict who can push to matching branches". The agent keeps Write so it can
     push its `issue/<n>-<slug>` branches.
   - (b) Fork workflow: the agent has Read or Triage on the main repository, pushes to its own
     fork and opens PRs from there, so it has no merge right at all.
3. **CODEOWNERS** in `.github/CODEOWNERS`, owned by the coordinator, so changes to these paths
   need the coordinator's review (the owner needs Write access for the review to count):

   ```text
   /setup/                              @coordinator
   /.github/CODEOWNERS                  @coordinator
   /.github/                            @coordinator
   /foundation/terraform/modules/       @coordinator
   /foundation/oidc-trust/              @coordinator
   /foundation/base-images/             @coordinator
   /foundation/slo-framework/           @coordinator
   /foundation/network-policy/          @coordinator
   ```

   `setup/` covers `setup/project-taxonomy.json` and `setup/platform_harness/`. The five
   `foundation/` paths exist in a fleet repo only (`CLAUDE.md`, "Shared foundation").

**Verify by hand.** The coordinator runs these; do not add them to a script.

```bash
# Branch protection: check required_pull_request_reviews.required_approving_review_count,
# require_code_owner_reviews, dismiss_stale_reviews, enforce_admins.enabled, restrictions
gh api repos/{owner}/{repo}/branches/main/protection
# Or, if you use rulesets (active rules only):
gh api repos/{owner}/{repo}/rules/branches/main
# Agent role: role_name must not be maintain or admin; with option (a) write is fine,
# with option (b) it should be read or triage
gh api repos/{owner}/{repo}/collaborators/{agent-login}/permission
# CODEOWNERS content: read it for the protected paths and the coordinator handle
gh api repos/{owner}/{repo}/contents/.github/CODEOWNERS -H "Accept: application/vnd.github.raw"
# CODEOWNERS syntax only: an empty errors list proves it parses, not that paths are covered
gh api repos/{owner}/{repo}/codeowners/errors
```

Endpoint names and the response fields above were checked against the GitHub REST
documentation on 2026-11-21. The `restrictions` field and push restrictions are organization-only
(personal-account repositories use a ruleset or the fork workflow); that the "Restrict updates"
ruleset rule is available on a given plan is not verified here: confirm in the repository
settings.

## Success criteria

- Branch protection, an agent identity without merge or admin rights, and CODEOWNERS are on and
  verified with the `gh api` checks in "Enforce it on the server"
- Labels from taxonomy exist on GitHub
- At least one milestone exists and matches taxonomy names
- At least one issue was created **only** via `setup/repo_issue.py`
- `python -m pip install -e ".[dev]" && python -m ruff check setup tests && python -m mypy` clean
- `python -m unittest discover -s tests -v` still passes
- `python setup/repo_issue.py doctor --offline` reports `ok: true`
- Friction notes captured (missing skills, Windows launcher, install copy set, etc.)

Optional velocity smoke (after a claim exists):

```bash
python setup/repo_issue.py pr-draft --issue <n>
python setup/repo_issue.py velocity --days 14
```

Demo script: [`five-minute-demo.md`](five-minute-demo.md).

## Out of scope for first trial

- Parallel worktrees / multi-worker collision drills (do after one happy-path claim)
- Foundation changes on a real fleet
- Competing-model review wiring to an external agent-harness
