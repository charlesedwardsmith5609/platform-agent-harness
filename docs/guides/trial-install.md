# Trial install (dogfood)

Use this checklist to run the harness against a real GitHub repository for the
first time. The default trial target is **this repository**
(`platform-agent-harness`) so coordination can be exercised without touching a
production fleet.

## Preconditions

- [ ] `git` and `python` 3.11+ on PATH
- [ ] `gh` authenticated to the trial repo (`gh auth status`)
- [ ] Working tree on `main`, clean enough to commit STATUS / CLAUDE adaptations
- [ ] Human present for label/milestone creation and the first claim

## Steps

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

## Success criteria

- Labels from taxonomy exist on GitHub
- At least one milestone exists and matches taxonomy names
- At least one issue was created **only** via `setup/repo_issue.py`
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
