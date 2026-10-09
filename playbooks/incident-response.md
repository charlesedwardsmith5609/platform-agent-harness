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

## Coordinator duties after an incident

1. Confirm follow-up issues have a lane and `incident-follow-up`
2. Serialize foundation or trust-model changes so they do not land in a pile
3. Append human/integration scenarios to `docs/test-scenarios/pending.md` when
   the fix cannot be proven with unit tests alone
4. Emit one `STATUS` comment (see `playbooks/status-reporting.md`) when the
   incident is closed or when the first durable fix PR opens
