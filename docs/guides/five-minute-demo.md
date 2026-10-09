# Five-minute demo script

Use this as a live walkthrough (or record a short video) to show how the harness
improves engineering velocity: claim safely, ship a PR, measure flow.

## Prep (once)

```bash
python setup/repo_issue.py doctor --offline
python setup/create_labels.py --plan
```

Have `gh` authenticated to the demo repo.

## Minute 0–1 — Health + backlog

```bash
python setup/repo_issue.py doctor
python setup/repo_issue.py list --state open
```

Narrate: taxonomy + wrappers are the coordination API; GitHub remains the ledger.

## Minute 1–2 — Scaffold an initiative

```bash
# body in a gitignored file
python setup/repo_issue.py scaffold \
  --title "Demo: OTel burn-rate alerts" \
  --body-file demo.issue-body.local.md \
  --lane lane:observability \
  --lane lane:ci-cd
```

Narrate: foundation parent (if enabled) + blocked children keep workers from racing
foundation contracts.

## Minute 2–3 — Fail-closed claim + WIP limit

```bash
git fetch origin
git switch -c issue/<n>-demo-otel origin/main
python setup/repo_issue.py claim \
  --issue <n> \
  --lane lane:observability \
  --worker demo-worker \
  --branch issue/<n>-demo-otel
```

Optionally show a second claim in the same lane failing at `wip_limit`.

## Minute 3–4 — PR draft + gate

```bash
python setup/repo_issue.py pr-draft --issue <n> --write
# push branch, then:
# gh pr create ... using the written body
```

Narrate: PR gate requires `Closes #` + `## Blast radius`, and flags foundation-path
diffs without a coordinator signal.

## Minute 4–5 — Velocity + stale sweep

```bash
python setup/repo_issue.py in-review --issue <n>
python setup/repo_issue.py velocity --days 14
python setup/repo_issue.py sweep-stale --days 7
```

Narrate: leadership gets claim→merge medians and stuck WIP without a new SaaS tool.

## Cleanup

Release or merge the demo issue; delete the demo branch.
