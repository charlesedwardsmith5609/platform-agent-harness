# Multi-repo harness rollout

Use this when installing the coordination harness into one or more real (or
sandbox) infrastructure repositories.

## 1. Create or choose the consumer repo

The consumer owns fleet code (`compute/`, `foundation/`, …). This harness repo
owns the reusable wrappers and skills.

## 2. Sync allowlisted harness files

From the harness checkout:

```bash
python setup/sync_harness_to_repo.py --target /path/to/consumer --dry-run
python setup/sync_harness_to_repo.py --target /path/to/consumer
```

By default this **does not** overwrite consumer `CLAUDE.md` or `docs/STATUS.md`.
Pass `--include-identity` only for sandbox resets.

## 3. Adapt identity

Edit the consumer's `CLAUDE.md` and `docs/STATUS.md` for that org's lanes,
validation commands, and foundation paths.

## 4. Bootstrap GitHub metadata

```bash
cd /path/to/consumer
python setup/create_labels.py --plan
python setup/create_labels.py
# create milestones named exactly as in setup/project-taxonomy.json
```

Optional: configure `project_board` in `setup/project-taxonomy.json` — see
[`project-board.md`](project-board.md).

## 5. Prove coordination

1. Create + classify one issue via `python setup/repo_issue.py`
2. Claim → implement → PR → `in-review` → coordinator merge
3. Run `python setup/claim_concurrency_drill.py`

## 6. Scale

Repeat sync + identity adaptation per repo. Keep taxonomy lane names stable
across repos when possible so workers can move between codebases without
relearning labels.
