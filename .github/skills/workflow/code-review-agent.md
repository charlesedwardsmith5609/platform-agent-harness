# Skill: Code review agent (platform engineering)

**Trigger (coordinator):** you have finished reviewing a worker PR, the human is away, and the
working tree is clean and pushed. Use idle time to run a competing-model review pass on the diff.
**Do NOT run while code is in flux or mid-change.**

**Goal:** a second-opinion review run by the strongest available competing frontier model, opening
well-formed GitHub issues for quality problems, security gaps, and weak patterns — without
disrupting active work.

> **Why competing model?** Independent blind spots. The author's provider systematically misses
> what the reviewer's provider catches. This is especially important in platform engineering where
> a missed security issue or a missed blast radius assessment can affect the entire organization.

---

## Competing model selection

Resolve the reviewer model **at launch time**:

1. Identify the coding agent's model provider (Claude = Anthropic)
2. The approved competing provider is **OpenAI** (when the coding agent is Claude)
3. Select the **most capable frontier model** available from OpenAI — highest capability tier,
   newest generation, maximum reasoning, long context support
4. If OpenAI is unavailable or no frontier model is accessible, **stop and report** — never
   silently fall back to the same provider

The reviewer can also be launched using the Python harness in `agents/pr_reviewer.py`, which
handles model selection, OTel instrumentation, and cost tracking automatically.

---

## Using the Python harness (recommended)

The `agents/pr_reviewer.py` agent in this repo runs structured security and reliability review
with OTel instrumentation and confidence gating:

```bash
# Install the harness
pip install -e agent-harness/

# Run review against a specific PR
python agent-harness/agents/pr_reviewer.py \
  --pr <pr-number> \
  --repo <owner/repo>

# The agent posts structured findings as a PR comment and exits with:
# 0 = APPROVE, 1 = REQUEST_CHANGES, 2 = BLOCK, 3 = agent failure
```

The PR reviewer will:
- Fetch the diff automatically
- Post findings as a structured GitHub PR comment
- Return a gate decision (APPROVE / REQUEST_CHANGES / BLOCK)
- Emit OTel traces if OTEL_EXPORTER_OTLP_ENDPOINT is set
- Write an audit record to AGENT_AUDIT_LOG if set

---

## Platform engineering review lens

When reviewing platform infrastructure changes, look for:

**Security (file with `security` concern):**
- Overly permissive IAM roles or Kubernetes RBAC (principle of least privilege)
- OIDC trust misconfiguration (wrong issuer URL, missing audience validation, overly broad subjects)
- Hardcoded credentials or secrets in Terraform/YAML/code
- Missing network policies allowing unintended service-to-service communication
- Terraform resources without encryption, logging, or access controls
- Insecure defaults left in place (public S3 buckets, unencrypted volumes, unrestricted security groups)
- Missing input validation in platform APIs that process service-owner-supplied data

**Reliability risks (`bug` if actively broken, `hardening` if defensive):**
- Terraform changes that will destroy and recreate stateful resources in production
- Missing `lifecycle { prevent_destroy = true }` on critical infrastructure
- Kubernetes resource requests/limits that will cause OOM kills or CPU throttling at load
- Missing PodDisruptionBudgets on critical services
- OTel collector config that could drop traces under backpressure
- SLO alert thresholds that will cause alert fatigue or miss real incidents
- Missing retry/circuit breaker on external dependencies
- Single-AZ deployments of multi-AZ-critical services

**Blast radius assessment:**
- Does the change affect shared infrastructure (VPC, IAM, cluster config)? → `lane:foundation`
- Does it affect service-to-service communication? → flag for coordinator serialization
- Does it touch the OIDC trust model? → requires human security review before merge
- How many engineering teams does this change affect if it goes wrong?

**Observability gaps:**
- New resources without proper cost attribution tags
- New services without SLO targets defined
- Infrastructure changes without corresponding alerting updates
- Missing structured logging on error paths

---

## Issue format for review findings

```bash
gh issue create \
  --title "Missing PodDisruptionBudget on OTel collector deployment" \
  --body "**Where:** observability/otel-collector/deployment.yaml

**Why it matters:** Without a PDB, a node drain during Kubernetes upgrades can take down all
OTel collector replicas simultaneously, causing trace loss for all services until collectors
reschedule. This is a reliability gap in a critical observability component.

**Suggested fix:**
\`\`\`yaml
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: otel-collector-pdb
  namespace: observability
spec:
  minAvailable: 1
  selector:
    matchLabels:
      app: otel-collector
\`\`\`" \
  --label "hardening" --label "P2" --label "lane:observability"
# For security findings: also add --label "security"
# Do NOT set --milestone (empty = untriaged, deliberate)
```

---

## Review ledger

After each review pass, append to `docs/review-ledger.md`:

```markdown
## Review — YYYY-MM-DD

- **Reviewed-through:** `<HEAD SHA>`
- **Scope:** incremental / full — files reviewed: [list]
- **Issues opened:** #N (hardening · P2 · lane:observability), #M (security · P1 · lane:identity)
- **Findings summary:** 2 findings — no P0/P1 bugs; 1 security-concern hardening item
- **Notes:** [anything worth calling out for the coordinator]
```

---

## Hard constraints (review agent)

- **Read-only on source.** Never edit, refactor, or fix code. Write only: GitHub issues, the
  review ledger, and audit log entries.
- **One type + one priority + one `lane:*` + concerns.** Never a milestone (empty = untriaged).
- **No duplicates.** Search before filing: `gh issue list --search "keyword"`
- **Platform calibration:** infrastructure "could be better" findings are `hardening` (P2–P4),
  not `bug`. A `bug` requires something that is actually broken or will break on deploy. Reserve
  P0/P1 for things the coordinator needs to know about immediately.
- **Abort if working tree is dirty** — reviewing code in flux produces invalid findings
