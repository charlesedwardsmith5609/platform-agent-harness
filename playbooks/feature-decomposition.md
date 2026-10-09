# Feature decomposition

How to turn a platform initiative into classified GitHub issues that workers can
claim without colliding or touching the shared foundation.

Load `.github/skills/workflow/issue-triage.md` and `setup/wrapper-catalog.md` before filing.
Create issues with `python setup/repo_issue.py create`, not raw `gh issue create`.

---

## 1. Name the outcome and the blast radius

Write one sentence: what will be true in production when this is done, and which
teams or services break if it is wrong. If the answer is "everyone," the work
almost certainly includes `lane:foundation` and stays with the coordinator.

---

## 2. Split on architecture seams, not on "tasks"

Create **one issue per lane** where practical. A single issue that needs compute
*and* networking *and* identity will stall: only one `lane:*` label is allowed.

If a change requires a foundation contract first:

1. File a coordinator-owned `lane:foundation` issue (or comment on the existing
   initiative issue: "Foundation change needed: …")
2. File worker issues with `blocked` and `Blocked by #N` until that lands
3. Workers rebase onto `main` after the foundation PR merges

---

## 3. Classify at creation

Every issue: **one type + one priority + one lane + optional concerns**.
Leave **milestone empty** (untriaged signal).

| Split this… | Into… |
|---|---|
| New shared Terraform module interface | `lane:foundation` first, then consumer issues per lane |
| Cluster upgrade | `lane:compute`; networking/identity follow-ups if APIs change |
| New ingress + certs | Dominant lane is usually `lane:networking`; identity issue if trust/OIDC changes |
| SLO + dashboard + pipeline scrape config | Prefer one observability issue unless CI must change (then `lane:ci-cd` + blocked) |

Do not file P2+ `bug` for "this might hurt later" — that is `hardening`.

---

## 4. Acceptance

- Machine-validated lanes: name the exact commands in the issue body
- Infra-validated: add a scenario template pointer to
  `.github/skills/workflow/human-test-scenarios.md`
- Human-acceptance (`lane:platform-api`): the issue is not done until a human
  follows the pending scenario

---

## 5. Sequencing for the coordinator

Order of attack from `CLAUDE.md`: P0 bugs → P1 bugs → `security` non-bugs →
`incident-follow-up` → everything else by priority.

Do not put two high-blast-radius PRs in front of the human in the same short window
(foundation and networking especially).
