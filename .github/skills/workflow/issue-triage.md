# Skill: Issue triage (platform engineering)

**Trigger:** "go triage", "triage #N", "triage open issues", feature decomposition from the human.

**Goal:** find untriaged issues (open, no milestone) and apply the full taxonomy:
type + priority + lane + concerns + milestone + rationale comment.

> **Untriaged = open issue with no milestone.** This is the deliberate signal.
> Do not re-triage milestoned issues unless asked.
>
> **Agent-created issues:** apply type + priority + lane + concerns at creation.
> Leave milestone empty. The triage sweep adds the milestone.
>
> **Human-filed issues:** humans leave labels, milestone, and lane blank — then ask for triage.

---

## Filing a new issue (classify at creation)

Apply this to *any* issue you open — from user feedback, a follow-up spotted mid-task, or a
postmortem action item.

```bash
gh issue create \
  --title "concise, specific description" \
  --body "What/where + why it matters in production + how to reproduce or verify a fix" \
  --label "hardening" \
  --label "P2" \
  --label "lane:observability"
# Add --label "security" or --label "blocked" when applicable
# DO NOT set --milestone (empty = untriaged, deliberate)
```

Lane is set **at creation**, not deferred. An issue without a lane cannot be routed to a worker.

---

## Triage procedure

### 1. Find untriaged issues

```bash
gh issue list --state open --limit 100 --json number,title,milestone \
  | python3 -c "import json,sys; issues=json.load(sys.stdin); [print(i['number'], i['title']) for i in issues if not i['milestone']]"
```

Read each fully: `gh issue view <n>`

### 2. Classify

**Type — exactly one:**

| Label | Platform engineering meaning |
|---|---|
| `bug` | Something is **broken in production or will break on deploy**: misconfigured Terraform causing service failures, OTel pipeline dropping traces, OIDC trust misconfiguration causing auth failures. **P0/P1 only.** |
| `feature` | New platform capability that doesn't exist: new lane in the API gateway, new secrets management pattern, new OTel integration |
| `enhancement` | Improving an existing, working capability: faster rollout strategy, better error messages in the self-service API |
| `hardening` | Not broken but should be more resilient: missing input validation in the onboarding workflow, weak RBAC, no retry on the deployment pipeline, missing SLO for a critical service. **If tempted to file P2+ bug, it's almost always this.** |

**Platform engineering triage rule:** if a finding doesn't cause an observable production failure
*today*, it is not a `bug`. Infrastructure "this could cause problems" findings are `hardening`.
Reserve `bug` for actual breakage or imminent security exploits.

**Concerns — add alongside type:**
- `security` — OIDC misconfiguration, overly permissive IAM, exposed secrets, unvalidated inputs
  in privileged code paths. On a `bug`: fix immediately before other work.
- `blocked` — waiting on another team, a vendor response, a dependency issue. Add `Blocked by #N`.
- `incident-follow-up` — generated from a postmortem action item. Prioritize above normal `enhancement`
  work regardless of priority label.

**Priority:**
- `P0` — production incident, security exploit in progress, or a change that will cause an outage
  at next deploy. Coordinator notifies human immediately.
- `P1` — every other `bug`; or non-bug work that is actively blocking another engineering team's
  delivery (they cannot ship because of a missing platform capability).
- `P2` — important non-bug work; plan to complete within the current sprint or cycle.
- `P3` — lower value or lower urgency; schedule when capacity allows.
- `P4` — nice to have; add to backlog and revisit quarterly.

**Attack order:**
1. `bug` `P0` (production incidents — drop everything)
2. `bug` `P1`
3. `security` non-bugs (defense-in-depth, hardening with security concern)
4. `incident-follow-up` (postmortem action items, regardless of priority label)
5. Everything else by priority, then lane capacity

**Milestone — which delivery phase?**
Adapt to your actual roadmap. Typical platform phases:
- `Phase 1: Foundational` — core infrastructure that everything else depends on
- `Phase 2: Developer Experience` — self-service, onboarding, developer tooling
- `Phase 3: Reliability` — SLO framework, advanced observability, chaos engineering
- `Phase 4: Scale` — cost optimization, multi-region, advanced security

**Lane — exactly one:**
Pick the lane owning the **bulk of the work**. For issues spanning multiple lanes, assign the
dominant one and cross-reference the others.

- `lane:foundation` — shared Terraform modules, OIDC trust model, base images, SLO framework,
  cluster-wide network policies. Coordinator-owned.
- `lane:compute` — EKS cluster config, node pools, Karpenter/node lifecycle, resource quotas,
  Kubernetes upgrades, workload scheduling
- `lane:networking` — Envoy Proxy, API gateway config, service mesh, TLS/mTLS, ingress, DNS
- `lane:identity` — OIDC workload identity, secrets management platform, cert rotation, RBAC, IAM
- `lane:observability` — OTel collectors, metrics/tracing pipeline, SLO alert rules, dashboards,
  on-call routing configuration
- `lane:ci-cd` — deployment pipelines, release automation, artifact management, build infra
- `lane:platform-api` — internal developer APIs, service onboarding automation, self-service tooling
- `lane:cost` — cost attribution labels, FinOps dashboards, budget alerts, chargeback

### 3. Apply labels and milestone

```bash
gh issue edit <n> --add-label "hardening" --add-label "P2" --add-label "lane:observability" --milestone "Phase 2: Developer Experience"
# Add security/blocked when applicable:
gh issue edit <n> --add-label "security"
gh issue edit <n> --add-label "blocked"
```

### 4. Comment rationale

```bash
gh issue comment <n> --body "Triage: hardening · P2 · lane:observability · Phase 2

This is a hardening issue rather than a bug because [reason]. Assigned to observability because
[the bulk of the work is in the OTel pipeline / alert configuration / etc.].

[Any cross-references to related issues or blocking dependencies.]"
```

### 5. Verify and summarize

```bash
# Should return 0 when triage is complete
gh issue list --state open --limit 100 --json number,milestone \
  | python3 -c "import json,sys; issues=json.load(sys.stdin); print(sum(1 for i in issues if not i['milestone']), 'untriaged')"
```

Report one line per issue: `#N — type [concern] · Pk · lane:X · phase`

---

## Platform triage rules

- Only triage **untriaged** (no-milestone) issues by default
- Never invent labels or milestones — use `gh label list` and `gh api repos/{owner}/{repo}/milestones`
- `lane:foundation` issues go to the coordinator, not workers — note this in the triage comment
- `incident-follow-up` issues should reference the incident postmortem in the body
- Overlapping issues → cross-reference, don't merge/close without human confirmation
- If the human files an issue with a type/priority already filled in, honor it unless there's a concrete reason to change it; explain any change in the triage comment
