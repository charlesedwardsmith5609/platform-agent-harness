# Step 4 - "Enforce it on the server" section in the trial-install guide (TLDR 2026-11-20)

Docs only. No code, script or permission-file changes.

## Why
`CLAUDE.md` says "Never self-merge" (lines 69, 232, 303), merging is a coordinator duty
(line 240), the shared foundation is coordinator-owned (lines 76-89), and the permission files are
"a seatbelt, not a sandbox" (line 249). `docs/guides/permissions-and-security.md:29-30` already
says branch protection "is still required server-side", but no guide says which server settings
to turn on or how to check them. `docs/guides/trial-install.md` (Preconditions, lines 32-37, and
Manual steps, lines 39-90) is where an installer would look.

Reason given in the brief (a claim from one blog post, not verified here): written instructions
did not stop agents merging; server-enforced permissions did (TLDR Dev 2026-11-18,
https://itsmeduncan.com/2026/11/17/only-the-human-merges). The guide will not cite the post as
evidence; it cites `CLAUDE.md` for the rule.

## Approach
Add one section, `## Enforce it on the server`, to `docs/guides/trial-install.md`, placed after
"Manual steps" and before "Success criteria". Content (short, one bullet per setting):

1. Opening sentence: the permission files (`setup/agent-permissions.json`,
   `.claude/settings.json`) are a seatbelt, not a sandbox (`CLAUDE.md` "Tool and network policy");
   the GitHub settings below are the control that enforces "Never self-merge" and the
   coordinator-owned foundation (`CLAUDE.md` "Shared foundation", "Guardrails").
2. **Branch protection on `main`**: require a pull request, at least one approving review, code
   owner review, dismiss stale approvals, include administrators (no bypass), no force pushes or
   deletions. A repository ruleset with the same rules is an equivalent alternative.
3. **Agent token without merge or admin rights**: the agent uses its own account or app, never
   the coordinator's. Required reviews alone do not stop merging: a Write role can merge a PR once
   it is approved (plan review finding 1). So the guide states the merge restriction separately
   from the review requirement and gives two ways to get it:
   - (a) restrict who can update `main` to the coordinator: branch protection "Restrict who can
     push to matching branches" (organization repos) or a ruleset "Restrict updates" with only
     the coordinator on the bypass list; the agent keeps Write so it can push feature branches;
   - (b) fork workflow: the agent identity has Read or Triage on the main repo, pushes to its own
     fork and opens PRs from there, so it has no merge right at all.
   A fine-grained token is scoped to the one repository (or fork). Not on any bypass list.
4. **CODEOWNERS** in `.github/CODEOWNERS`, owned by the coordinator, covering `setup/` (includes
   `setup/project-taxonomy.json` and `setup/platform_harness/`), `.github/CODEOWNERS` itself
   (and `.github/`, so workflow and ownership changes need coordinator review), and, in a fleet
   repo, the five `foundation/` paths listed in `CLAUDE.md`. Note the owner must have Write
   access for the code-owner review to count. Example lines in a code block; this step does not
   add the file to the repo (see open questions).
5. **Verify by hand** (coordinator runs these; the guide says no script runs them):
   - Branch protection: `gh api repos/{owner}/{repo}/branches/main/protection`
     (check `required_pull_request_reviews.required_approving_review_count`,
     `require_code_owner_reviews`, `enforce_admins`, `restrictions`), or for rulesets
     `gh api repos/{owner}/{repo}/rules/branches/main`.
   - Agent role: `gh api repos/{owner}/{repo}/collaborators/{agent-login}/permission`
     (`role_name`: `write` only with option (a) in place; `read`/`triage` for option (b);
     never `maintain` or `admin`).
   - CODEOWNERS content: `gh api repos/{owner}/{repo}/contents/.github/CODEOWNERS -H "Accept: application/vnd.github.raw"`
     and read it for the protected paths and the coordinator handle; then
     `gh api repos/{owner}/{repo}/codeowners/errors` as a syntax check only (an empty `errors`
     list proves parsing, not coverage).
6. Add one Success-criteria bullet: the three settings above are on and verified.

The implementer checks each endpoint, field name and the "Restrict updates"/push-restriction
availability (organization vs personal repos) against GitHub docs before writing them. An
endpoint that cannot be confirmed is not dropped: keep it, mark it in the report as "unverified,
owner to confirm", and list it as a blocker in the open questions.

## Shared state ownership
None changed. The section describes coordinator-owned settings (GitHub repo settings); it does
not touch `setup/project-taxonomy.json` or `setup/platform_harness/`.

## Tests
One docs test in `tests/test_repo_issue.py`, next to
`test_docs_state_denies_are_a_seatbelt_not_a_sandbox` (around line 904):
Docs tests in `tests/test_repo_issue.py`, next to
`test_docs_state_denies_are_a_seatbelt_not_a_sandbox` (around line 904), reading only the text
between `## Enforce it on the server` and the next `## ` heading:
- the section exists and says "seatbelt" and cites `CLAUDE.md`;
- it has each verification command: `branches/main/protection`, `collaborators/`,
  `/permission`, `contents/.github/CODEOWNERS`, `codeowners/errors`;
- it names the protected paths `setup/`, `.github/CODEOWNERS` and each of the five
  `foundation/...` paths from `CLAUDE.md`;
- it states the merge restriction separately (mentions "Restrict updates" or "fork").
Written first, they fail before the doc edit and pass after. The `doctor` question is recorded in
this plan and the report, not in the guide, so it is not tested (plan review finding 4, partly
disagreed: it is a question for the owner, not guide content).

## Done criteria
- New section present; claims about the repo cite `CLAUDE.md`.
- No `gh api` call is added to any script; none is run.
- `python -m ruff check setup tests`, `python -m mypy`,
  `python -m unittest discover -s tests -v`, `python setup/apply_permissions.py --dry-run` pass;
  `bash scripts/check.sh` prints `CHECK PASSED` (report each stage; a SKIP counts as not run).
- `bash scripts/cross-review.sh` run on the change; findings assessed.
- `CHANGELOG.md` gets a new `## [Unreleased] - 2026-11-20` entry.

## Open questions (owner)
1. Should `repo_issue.py doctor` print a reminder to check the server settings? Not built in this
   step. Recommendation: yes, later, as an offline-only printed reminder (no `gh api` calls, so no
   new network surface or token scope); a separate plan.
2. Should this repo commit its own `.github/CODEOWNERS` and turn on the protection now?
   Recommendation: yes, but the owner does it (settings are the coordinator's; the file is a
   foundation-adjacent change).
3. Classic branch protection or rulesets as the primary recommendation? Recommendation: document
   branch protection first (simplest `gh api` check), rulesets as the equivalent.
4. Merge restriction: option (a) restricted updates to `main` or option (b) fork workflow for the
   agent? This repo is under a personal account, where classic push restrictions are an
   organization feature. Recommendation: (a) via a ruleset where available, (b) otherwise;
   guide documents both.

## Plan review (openai, 2026-11-21)
1. HIGH, Write role can merge an approved PR: agreed; added the separate merge restriction.
2. MEDIUM, CODEOWNERS does not protect itself: agreed; `.github/CODEOWNERS` and `.github/` added.
3. MEDIUM, errors endpoint proves syntax not coverage: agreed; added the content fetch.
4. MEDIUM, keyword test too weak: agreed for settings, commands and paths; disagreed for the
   `doctor` question (owner question, not guide content).
5. MEDIUM, dropping unconfirmed endpoints: agreed; unconfirmed ones are kept and flagged.

## Suggestions (not in scope)
- A one-line link from `docs/guides/permissions-and-security.md:30` to the new section.

## Files
- `docs/guides/trial-install.md`
- `tests/test_repo_issue.py`
- `CHANGELOG.md`
