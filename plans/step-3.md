# Step 3 - LOW findings (7, 8)

## Findings covered
7. `gh_command` is POSIX-only quoting.
8. Dead symlink check in `ignored_issue_file`.

## Types
- `build_pr_draft(...) -> dict` keeps key `gh_command` (str) and adds `gh_argv` (list[str]) as the portable form.
- `ignored_issue_file` returns `Path`.

## Shared state ownership
- `setup/platform_harness/` is coordinator-owned; coordinator sign-off needed before implementation.

## Design notes
- `path = (root / relpath).resolve()` follows symlinks, so `path.is_symlink()` is always false. Fix: check `(root / relpath)` and each parent under the root with `Path.is_symlink()` before resolving. A symlinked parent directory stays followed per shared-pattern 2; narrow any docs wording.
- Quoting: keep `shlex.quote` for the POSIX string, expose `gh_argv`, and use `subprocess.list2cmdline` when `os.name == "nt"`.

## Tests
- A symlink to an in-repo ignored `.local.md` file is rejected (skipped where symlinks are unavailable).
- `gh_argv` equals the parsed list for a hostile title and holds the title as one element.
- On simulated `nt`, `gh_command` has no single-quote wrapping.

## Files
- `setup/platform_harness/taxonomy.py`
- `setup/platform_harness/pr_draft.py`
- `tests/test_repo_issue.py`
- `docs/guides/trial-install.md`
- `CHANGELOG.md`
