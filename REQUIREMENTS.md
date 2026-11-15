## Review fixes 2026-11-14

Source: `.review/findings.md` (PR #24). Decisions: `.review/DECISIONS.md`.

- Issue body files must end in `.local.md`, resolve inside the working tree, and be Git-ignored.
- Auto-approved command prefixes must not allow the known bypasses (`--upload-pack`, `git remote add`, `--output`, `--no-index`, writing `unittest` runs). Each bypass has a test.
- The `/proc` environ deny uses the absolute-path form Claude Code expects, with a test.
- Docs say plainly that Bash denies are a seatbelt, not a sandbox.
- The title filter blocks control characters and shell metacharacters but accepts ordinary titles. Tests assert the rejection reason.
- `gh_command` quoting works on Windows/WSL; the dead symlink check is removed or made effective.
