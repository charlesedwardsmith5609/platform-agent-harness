# Kubernetes / compute skill

> **Load before:** EKS or cluster config, node groups, Karpenter, quotas, Deployments,
> Services, RBAC (with `security-hardening.md`), or Kubernetes version upgrades.

Also load `coding/platform-engineering.md` and `coding/security-hardening.md`.

---

## Invariants

- Every workload has memory/CPU **requests and limits**. Missing requests cause
  noisy-neighbor scheduling; missing limits cause node memory exhaustion.
- Critical Deployments have a **PodDisruptionBudget** (`minAvailable` or
  `maxUnavailable` that still leaves serving capacity during a drain).
- Prefer **namespaced** Roles over ClusterRoles. ClusterRoleBindings are a human
  security review item.
- `privileged: true`, `hostNetwork: true`, and `hostPath` volumes are not
  defaults; document why if they appear.
- Pin image tags to digests or immutable version tags. `:latest` is not production.
- Changes that alter the cluster control plane, CNI, or admission webhooks are
  high blast radius: sequence through the coordinator; do not parallel with
  `lane:networking` foundation-adjacent work.

---

## Resource hygiene

```yaml
resources:
  requests:
    cpu: "100m"
    memory: "128Mi"
  limits:
    cpu: "500m"
    memory: "256Mi"
```

HPA and VPA need a matching SLO or saturation signal; do not autoscale blindly
on CPU if the service is I/O or queue bound.

---

## Rollouts and rollback

- Use `RollingUpdate` with `maxUnavailable` that your PDB can survive.
- Document rollback: `kubectl rollout undo deployment/<name> -n <ns>` or the
  Git revert + pipeline path your org actually uses.
- Kubernetes version upgrades: validate add-ons, storage drivers, and webhook
  compatibility in staging before production. Treat as `lane:compute` with
  infra validation scenarios in `docs/test-scenarios/pending.md`.

---

## Quotas and multi-tenant safety

ResourceQuota and LimitRange in tenant namespaces prevent one team from starving
the cluster. Default-deny NetworkPolicy belongs with identity/networking skills;
do not assume compute changes include it.

---

## Validation (adapt to your repo)

Run only commands that exist in the target repository, each as its own invocation:

- Manifest lint / schema (e.g. kubeconform, kustomize build)
- Policy tests (Conftest/OPA/Kyverno) if the repo has them
- Staging apply or dry-run the human scenario describes — not a surprise
  production `kubectl apply` from an agent
