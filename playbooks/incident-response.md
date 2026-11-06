# Incident response (coordination)

This playbook covers **how agents and humans use GitHub after an incident**, not
how to mitigate a live outage. During an active incident, follow your on-call
runbook and paging policy first.

---

## During the incident

Agents do **not** claim random issues or open drive-by PRs on the hot path unless
the human (or the incident commander) asks. Coordination noise makes the outage
worse.

If an agent is asked to help:

- Work only on the lane that owns the failing subsystem
- Do not touch `foundation/` without coordinator + human sign-off
- Record commands and outcomes on the incident issue, not only in chat

---

## After mitigation: file follow-ups

For each durable action item from the postmortem:

Write the body to a Git-ignored `*.issue-body.local.md` file, then:

```bash
python setup/repo_issue.py create \
  --title "concise follow-up from incident <id>" \
  --body-file scratch.issue-body.local.md \
  --type hardening \
  --priority P2 \
  --lane lane:<owning-lane> \
  --concern incident-follow-up
```

Use `bug` + `P0`/`P1` only if production is still broken or the next deploy will
break it. Use `security` as well when the incident had a security dimension.

Leave milestone empty; triage assigns the delivery phase.

---

## Runbooks

Every component that has had an incident (or realistically could) needs a runbook:
symptoms, diagnosis commands, remediation, rollback, escalation.

If your organization uses the companion **agent-harness** execution repo, its
`agents/runbook_gen.py` can draft a runbook from the incident write-up. That
script is **not** part of this coordination harness. Review any generated runbook
with a human before it is considered production-ready.

---

## Agent credentials (incident-informed)

Public incidents have shown a test-scoped agent expanding into tenant-wide secret reads and
internal network scans by using ambient container or instance credentials. Treat that class of
failure as a coordination incident even when no production outage is open yet.

**Worker rule (also in `CLAUDE.md`):**

- Never use ambient cloud credentials (instance role, user SSO cache, leftover CI OIDC, broad
  container env). Use only scoped credentials issued for the current task.
- If the agent sees credentials or secrets outside its lane (or any secret it was not issued),
  it posts a short issue comment describing *what kind* of material it saw and *where* (no
  secret values), then stops. Do not continue the task, do not exfiltrate, do not “just check
  one more path.”
- Do not probe cloud metadata (`169.254.169.254`, `metadata.google.internal`), `.env*` files,
  `~/.ssh`, or cloud credential files to recover from a blocked tool call.

File follow-ups from such events as `hardening` or `bug` with `--concern security` (and
`incident-follow-up` when tied to a postmortem). Prefer fixing issuance/scoping of task
credentials over adding more ambient access.

---

## Coordinator duties after an incident

1. Confirm follow-up issues have a lane and `incident-follow-up`
2. Serialize foundation or trust-model changes so they do not land in a pile
3. Append human/integration scenarios to `docs/test-scenarios/pending.md` when
   the fix cannot be proven with unit tests alone
4. Emit one `STATUS` comment (see `playbooks/status-reporting.md`) when the
   incident is closed or when the first durable fix PR opens
5. For credential-misuse follow-ups: confirm workers still cannot rely on ambient cloud
   credentials and that deny/ask defaults in `setup/agent-permissions.json` remain applied
