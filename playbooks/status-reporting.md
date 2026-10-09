# Status reporting

Emit **one** status event after a meaningful milestone: PR opened, PR merged, or
incident resolved. Put it on the GitHub issue (comment) and, if you maintain one,
in the weekly summary. Do not rely on chat history.

---

## When to emit

| Event | Who | Where |
|---|---|---|
| Worker opened a PR | Worker | Issue comment (optional but useful) + PR body already has the detail |
| Coordinator merged a PR | Coordinator | Issue is auto-closed; add a merge note only if something the human must know is not in the PR |
| Incident closed | Coordinator or human | Issue with `incident-follow-up` plus a short comment on the original incident issue |

Skip status comments for documentation-only PRs unless the human asked for a trail.

---

## Format

Keep it short enough to scan in the issue timeline:

```
STATUS · <event> · <UTC timestamp>
Lane: lane:<name>
Issue: #<n>  PR: #<pr>   (omit PR if none)
What: one sentence
Validation: commands run and pass/fail (or "n/a — docs")
Blast radius: who is affected if this is wrong
Next: coordinator review | human security review | done
```

Example:

```
STATUS · PR opened · 2026-08-25T18:00:00Z
Lane: lane:observability
Issue: #42  PR: #88
What: add 2% / 1h burn-rate page for the API gateway SLO
Validation: python -m unittest discover -s tests -v pass (or the commands in CLAUDE.md)
Blast radius: on-call for platform + gateway owners; no dataplane change
Next: coordinator review
```

---

## Rules

- One event per milestone, not a running diary
- No secrets, tokens, or internal URLs that do not belong on GitHub
- If validation failed, do not open the PR; there is no status event for a red PR
