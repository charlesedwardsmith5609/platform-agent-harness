# Terraform / IaC skill

> **Load before:** any `.tf` change, module interface change, or state-affecting
> workflow. Foundation module **interfaces** are coordinator-owned
> (`foundation/terraform/modules/` in the default layout).

Also load `coding/platform-engineering.md` and `coding/security-hardening.md`.

---

## Invariants

- Pin module and provider versions. Do not use `version = ">= x"` on production
  module sources.
- Critical stateful resources use `lifecycle { prevent_destroy = true }` unless
  the human has approved a destroy plan.
- `terraform plan` for a non-trivial change belongs in the PR description
  (sanitized: no secrets).
- Never commit `*.tfvars` with secrets, `*.env`, or files under `secrets/` /
  `credentials/`.
- A worker branch must not change shared module inputs/outputs. Propose the
  interface change on the issue; wait for a `foundation/<slug>` landing; rebase.

---

## Plan review

Before apply (human or pipeline):

- Look for `destroy` / replacement of databases, queues, NAT, IAM trust, OIDC
  providers, and KMS keys
- Confirm encryption, logging, and least-privilege IAM (see security skill)
- Confirm cost tags (`team`, `service`, `environment`) on new billable resources
- State what `terraform destroy` would take down if someone ran it on this root

---

## Validation (each command separately)

From `CLAUDE.md` defaults — **only if this repo actually contains Terraform**:

```bash
terraform fmt -check -recursive
terraform validate
tflint --recursive
```

Initialize with the backend your org uses; do not invent a local backend that
diverges from production state.

---

## Modules vs roots

- **Modules** (especially shared ones): stable outputs, documented variables,
  no environment-specific hardcoded account IDs unless that is the contract.
- **Roots** (envs): compose modules, pass environment, hold backend config.

Changing a shared module is org-wide blast radius even if the ticket was filed
in another lane.
