# Platform engineering principles

> **Load this skill** before writing any platform infrastructure code, Terraform, Kubernetes
> manifests, or automation. These are the failure patterns that cause production incidents —
> not abstract best practices.

---

## 1. The safe path must be the easy path

Every internal platform capability should be harder to use wrong than right. If engineers route
around your platform, the platform has failed — regardless of how technically correct it is.

- Self-service APIs should reject invalid inputs with clear error messages, not silently accept
  and produce broken infrastructure
- Defaults should be secure (encryption on, logging on, least-privilege IAM) — engineers should
  have to opt out of security, not opt in
- Onboarding to the platform should be faster than doing it manually; measure and enforce this

---

## 2. Blast radius is your primary constraint

Before implementing any change, state the blast radius explicitly:
- **Who is affected if this goes wrong?** (one service / one team / all teams)
- **Is this recoverable?** (can you roll back in under 5 minutes?)
- **Is there a progressive path?** (canary → staging → production, not all-at-once)

Changes with org-wide blast radius (shared Terraform modules, OIDC trust, base images) go through
the coordinator and require the human's sign-off. No exceptions.

---

## 3. Infrastructure changes are code changes — treat them the same way

Terraform, Kubernetes YAML, Helm values, and CI/CD configuration are production code:
- Every change goes through PR review
- Every change has validation (terraform validate, conftest, OPA policies)
- Every change has an explicit rollback path documented in the PR
- Stateful resources (databases, queues, caches) require extra care: check for `destroy` actions
  before applying

**Terraform specifically:**
- `terraform plan` output in the PR description for any non-trivial change
- Mark critical resources with `lifecycle { prevent_destroy = true }`
- Pin module versions; never use `source = "..." version = ">= x"` in production modules
- Document what `terraform destroy` would actually destroy and its production impact

---

## 4. Observability is not optional

Every new platform component ships with:
- **Metrics** — at minimum: error rate, latency (p50/p95/p99), saturation
- **Traces** — OTel instrumentation on all cross-service calls
- **Logs** — structured JSON, with correlation IDs, on all error paths
- **Alerts** — at least one SLO-based burn rate alert before any service is considered "in production"
- **Cost attribution** — resource tags for team, service, environment on all cloud resources

A service without SLO targets is not a production service — it's a prototype that happens to be running.

---

## 5. OIDC workload identity everywhere — no long-lived credentials

Any service, pipeline, or agent that needs to authenticate to cloud resources uses OIDC workload
identity. No `AWS_SECRET_ACCESS_KEY`, no long-lived API keys, no service account tokens in
Kubernetes secrets that rotate manually.

Pattern:
```
Kubernetes service account → OIDC token → AWS STS AssumeRoleWithWebIdentity → scoped IAM role
```

If you find yourself writing a long-lived credential into a Kubernetes secret or CI/CD system,
stop and use OIDC instead. Copy and adapt `github-actions/secrets-injection.yml` from this
harness into the target repo's `.github/workflows/` (the sample is not a live workflow here).

---

## 6. Treat every service owner as a customer

Internal developers consuming platform capabilities are customers. Their experience matters:
- Document every public API with input/output schema, error codes, and examples
- Maintain backwards compatibility — breaking changes require a deprecation notice and migration path
- Measure adoption and satisfaction (are engineers actually using this? what's their NPS?)
- When something breaks, communicate to affected teams before they discover it themselves

---

## 7. Failure modes must be explicit

**Never let infrastructure fail silently:**
- OTel collectors that drop traces under backpressure should log the drop count and alert
- Deployment pipelines that fail should clearly identify the failure reason and blast radius
- Service onboarding APIs that reject invalid inputs should return structured errors with guidance
- Missing health checks are a bug, not a to-do

**Prefer fail-open for observability, fail-closed for security:**
- If the OTel collector is down, services should continue running (fail-open) — not block on telemetry
- If the OIDC issuer is unreachable, the workload should fail to authenticate (fail-closed) — not
  fall back to a less-secure credential mechanism

---

## 8. Document the invariants, not the mechanics

Comments in Terraform, Kubernetes manifests, and automation scripts should explain:
- **Why** this resource exists and what it owns
- **What breaks** if this is removed or misconfigured
- **What you must not do** (the invariants that the code enforces)

Not:
```hcl
# Create an IAM role
resource "aws_iam_role" "gateway" {
```

Yes:
```hcl
# API gateway workload identity role — attached to the Kubernetes service account via OIDC.
# This role grants access to the gateway's Secrets Manager secrets only.
# Do not add additional policies to this role; scope secrets access to per-gateway roles.
resource "aws_iam_role" "gateway" {
```

---

## 9. Runbooks before incidents

Every platform component that has ever had an incident, or could realistically have one, needs a
runbook before it's considered production-ready. Runbooks must include:
- Symptoms (what monitoring/alerting surfaces this)
- Diagnosis steps (exact commands, expected outputs)
- Remediation (step-by-step with rollback)
- Escalation path

If you use the companion **agent-harness** execution repo, `agents/runbook_gen.py` can
draft a runbook from an incident write-up. That script is not shipped in this
coordination harness; a human must still approve the runbook. See
`playbooks/incident-response.md`.

---

## 10. Cost is a first-class concern

Platform infrastructure often runs at high scale and high cost. Every new resource should have:
- A cost estimate in the PR description (even a rough order-of-magnitude)
- Resource tags for cost attribution (team, service, environment)
- A plan for cost optimization as usage scales (reserved instances, spot capacity, right-sizing)
- An alert if cost grows unexpectedly above baseline

If you don't know what something costs, find out before merging it to production.
