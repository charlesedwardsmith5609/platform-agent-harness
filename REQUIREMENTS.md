## Review fixes 2026-11-14

Source: `.review/findings.md` (PR #24). Decisions: `.review/DECISIONS.md`.

- Issue body files must end in `.local.md`, resolve inside the working tree, and be Git-ignored.
- Auto-approved command prefixes must not allow the known bypasses (`--upload-pack`, `git remote add`, `--output`, `--no-index`, writing `unittest` runs). Each bypass has a test.
- The `/proc` environ deny uses the absolute-path form Claude Code expects, with a test.
- Docs say plainly that Bash denies are a seatbelt, not a sandbox.
- The title filter blocks control characters and shell metacharacters but accepts ordinary titles. Tests assert the rejection reason.
- `gh_command` quoting works on Windows/WSL; the dead symlink check is removed or made effective.

## TLDR guidance 2026-11-20 (step 4)

Source: owner's weekly TLDR brief (unattended run; requirements taken from the brief, pending owner confirmation).

- Docs only: `docs/guides/trial-install.md` gains an "Enforce it on the server" section covering required reviews and branch protection on `main`, an agent token without merge or admin rights, and CODEOWNERS for `setup/` and the foundation paths in `CLAUDE.md`.
- Each setting has a one-line `gh api` command the coordinator runs by hand; no script runs or contains them.
- The section says the permission files are a seatbelt and the server settings are the control, citing `CLAUDE.md`.
- Open question recorded, not built: should `doctor` print a reminder.
- Docs tests and `bash scripts/check.sh` pass.
