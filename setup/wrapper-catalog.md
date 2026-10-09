# Reviewed wrapper catalog

> Consult this file before concluding that an operation has no approved command surface.
> Detailed sequencing stays in `.github/skills/workflow/` and `CLAUDE.md`.

This catalog lists **agent-facing entry points**. Support files such as
`setup/project-taxonomy.json` and `setup/agent-permissions.json` are configuration, not commands.

Run one bare executable per tool call. Do not chain with `&&`, pipes, or `cd`.

## Common workflow entry points

| Wrapper | Operations | Contract |
|---|---|---|
| `setup/create_labels.py` | `[--plan] [--label name] [--reconcile]` | Plans, creates, or reconciles only labels declared by `setup/project-taxonomy.json`. |
| `setup/create-labels.sh` | same | Bash launcher for `create_labels.py`. |
| `setup/create-labels.ps1` | same | PowerShell launcher for `create_labels.py`. |
| `setup/apply_permissions.py` | `[--dry-run]` | Resolves the portable permission placeholder into a gitignored local settings file. |
| `setup/apply_permissions.ps1` | same | PowerShell launcher for `apply_permissions.py`. |
| `setup/claim_concurrency_drill.py` | (no args) | Live two-worker claim race drill; expects fail-closed second claim. |
| `setup/sync_harness_to_repo.py` | `--target <path> [--dry-run] [--force] [--include-identity]` | Copy allowlisted harness files into a consumer infra checkout. `--force` required to replace existing destination directories. |
| `setup/pr_gate.py` | `[--event] [--body-file] [--diff-files] [--branch] [--warn-only]` | PR hygiene gate: require `Closes #` + `## Blast radius`; foundation-path diffs need coordinator signal. |

## Issue lifecycle

| Wrapper | Operations | Contract |
|---|---|---|
| `setup/repo_issue.py` | `create`, `list`, `view`, `classify`, `link-child`, `unlink-child`, `claim`, `release`, `in-review`, `doctor`, `velocity`, `pr-draft`, `sweep-stale`, `scaffold` | Taxonomy-bound GitHub issue lifecycle (`setup/platform_harness/`). `claim` is comment-first, fail-closed on races, and respects per-lane `wip_limit`. Do not substitute raw `gh issue` for these operations. |

### Command shapes

```bash
python setup/repo_issue.py create --title "<title>" --body-file <ignored.issue-body.local.md> --type <type> --priority <priority> --lane <lane> [--concern <concern> ...]
```

```bash
python setup/repo_issue.py list [--state open|closed|all]
python setup/repo_issue.py view --issue <number>
python setup/repo_issue.py classify --issue <number> --type <type> --priority <priority> --lane <lane> [--concern <concern> ...] [--milestone "<milestone>"] --rationale-file <ignored.rationale.local.md>
python setup/repo_issue.py link-child --parent <number> --child <number>
python setup/repo_issue.py unlink-child --parent <number> --child <number>
python setup/repo_issue.py claim --issue <number> --lane <lane> --worker <handle> --branch <branch>
python setup/repo_issue.py release --issue <number> --mode abandon|blocked --reason-file <ignored.rationale.local.md>
python setup/repo_issue.py in-review --issue <number>
python setup/repo_issue.py doctor [--offline] [--target <consumer-repo-path>]
python setup/repo_issue.py velocity [--days 14]
python setup/repo_issue.py pr-draft --issue <number> [--write]
python setup/repo_issue.py sweep-stale [--days 7] [--apply]
python setup/repo_issue.py scaffold --title "<title>" --body-file <ignored.issue-body.local.md> --lane <lane> [--lane <lane> ...] [--type feature] [--priority P2] [--no-foundation]
```

Creation leaves milestone empty (untriaged). Classification requires a configured milestone when
`setup/project-taxonomy.json` lists milestones. Classification replaces only taxonomy-owned type,
priority, concern, and lane labels; claim-status and unrelated labels stay intact. Parent/child
hierarchy is independent of issue type.

Lane `wip_limit` (in taxonomy) caps concurrent `status:wip` claims per lane. Claim `--worker` /
`--branch` reject whitespace and newlines so CLAIM comments cannot smuggle extra harness markers.

`doctor --target` returns an adoption **score** (0–100). `velocity` reports open WIP, stale claims,
P0/P1 aging, and median claim→close / claim→merge hours. `sweep-stale` defaults to dry-run;
pass `--apply` to release. `scaffold` creates a foundation parent (unless `--no-foundation`) plus
blocked per-lane children.

Structured telemetry is optional: set `HARNESS_TELEMETRY=1` (JSON lines on stderr) and/or
`AGENT_AUDIT_LOG=<path>` (append JSONL).

Body and rationale files must be physical, repository-local files ignored by Git (use the
`*.issue-body.local.md` and `*.rationale.local.md` patterns).

## Still human or coordinator-owned

Pull request merge, foundation changes, and GitHub milestone creation remain explicit coordinator
or human operations. Validation stays as documented in `CLAUDE.md` — run each command as its own
call. In this harness repo that is `python -m unittest discover -s tests -v`, not pytest.

PR hygiene is machine-checked by `.github/workflows/pr-gate.yml` (via `setup/pr_gate.py`).
