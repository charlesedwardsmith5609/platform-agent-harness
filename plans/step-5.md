# Step 5 - doctor prints a server-settings reminder (owner approved the step-4 recommendation)

Add a static `reminder` string to the `run_doctor` report (`setup/platform_harness/doctor.py`).
Text only: no network, no `gh` calls, not a check, does not change `ok` or the score. It points to
`docs/guides/trial-install.md` "Enforce it on the server". The CLI already prints the report as JSON.

## Tests
- `test_doctor_prints_server_settings_reminder_without_network` in `tests/test_repo_issue.py`.

## Files
- `setup/platform_harness/doctor.py`
- `tests/test_repo_issue.py`
- `CHANGELOG.md`
- `plans/step-5.md`
