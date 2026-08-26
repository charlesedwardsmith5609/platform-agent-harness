# Security hardening for platform engineering

> **Load before:** any change touching IAM, OIDC, Kubernetes RBAC, secrets, network policies,
> service accounts, or any privileged code path. These are the patterns that cause
> platform-layer security incidents.

---

## 1. OIDC workload identity — the root of trust

The OIDC issuer URL and audience validation are the security boundary between your workloads
and cloud credentials. Get these wrong and you've opened your AWS account to any Kubernetes
workload in the cluster.

```hcl
# CORRECT: scoped to a specific namespace and service account
assume_role_policy = jsonencode({
  Statement = [{
    Effect = "Allow"
    Principal = { Federated = "arn:aws:iam::${account_id}:oidc-provider/${oidc_issuer}" }
    Action    = "sts:AssumeRoleWithWebIdentity"
    Condition = {
      StringEquals = {
        # BOTH conditions required — issuer alone is not sufficient
        "${oidc_issuer}:aud" = "sts.amazonaws.com"
        "${oidc_issuer}:sub" = "system:serviceaccount:${namespace}:${service_account_name}"
      }
    }
  }]
})

# WRONG: missing sub condition — ANY service account in the cluster can assume this role
Condition = {
  StringEquals = {
    "${oidc_issuer}:aud" = "sts.amazonaws.com"
    # Missing sub condition = all service accounts can assume this role
  }
}
```

**Invariants:**
- Every OIDC trust policy must include BOTH `aud` and `sub` conditions
- `sub` must be scoped to the specific namespace AND service account name
- Never use wildcard subjects (`system:serviceaccount:*`) in production trust policies

---

## 2. Least-privilege IAM

IAM roles should grant only the exact permissions needed for the specific task. Never:
- Attach `AdministratorAccess` to a workload role
- Use `"Action": "*"` on any IAM policy attached to a workload
- Grant `s3:*` when only `s3:GetObject` on specific buckets is needed

```hcl
# CORRECT: scoped to specific resources and actions
resource "aws_iam_role_policy" "gateway_secrets" {
  name = "${var.service_name}-secrets"
  role = aws_iam_role.gateway.id

  policy = jsonencode({
    Statement = [{
      Effect   = "Allow"
      Action   = ["secretsmanager:GetSecretValue"]
      Resource = [
        "arn:aws:secretsmanager:${var.region}:${data.aws_caller_identity.current.account_id}:secret:platform/${var.environment}/${var.service_name}/*"
      ]
    }]
  })
}
```

---

## 3. Kubernetes RBAC

```yaml
# CORRECT: verb-specific, resource-specific, namespace-scoped
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: otel-collector
  namespace: observability
rules:
  - apiGroups: [""]
    resources: ["pods", "nodes"]
    verbs: ["get", "list", "watch"]   # read-only; no create/update/delete/patch

# WRONG: cluster-admin is almost never appropriate for a workload
# Cluster-wide roles that grant write access to all resources
```

**Invariants:**
- Prefer `Role` (namespace-scoped) over `ClusterRole` (cluster-wide)
- Never grant `create`, `update`, `delete`, `patch` unless the workload genuinely needs to write
- `pods/exec` and `pods/portforward` are high-risk — flag for human review

---

## 4. Network policies — default deny

Without network policies, any pod in the cluster can talk to any other pod. This is the default
and it is insecure for a platform hosting multiple tenants.

```yaml
# Default deny for a namespace — apply this first
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-all
  namespace: payments-api
spec:
  podSelector: {}   # selects all pods in namespace
  policyTypes: [Ingress, Egress]
  # No ingress or egress rules = deny all
```

Then explicitly allow what's needed:
```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-api-gateway
  namespace: payments-api
spec:
  podSelector:
    matchLabels:
      app: payments-api
  policyTypes: [Ingress]
  ingress:
    - from:
        - namespaceSelector:
            matchLabels:
              kubernetes.io/metadata.name: api-gateway
          podSelector:
            matchLabels:
              app: envoy-gateway
      ports:
        - protocol: TCP
          port: 8080
```

---

## 5. Secrets — never in manifests or git

```bash
# WRONG: secret value in a Kubernetes manifest (goes into git history)
apiVersion: v1
kind: Secret
data:
  api-key: c2VjcmV0  # base64 — NOT encryption, still visible in git

# CORRECT: use external-secrets-operator or CSI driver to inject at runtime
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: payments-api-secrets
spec:
  secretStoreRef:
    name: aws-secrets-manager
    kind: SecretStore
  target:
    name: payments-api-secrets
  data:
    - secretKey: api-key
      remoteRef:
        key: platform/production/payments-api/config
        property: api-key
```

**Invariants:**
- `.gitignore` must include `*.tfvars`, `*.env`, `secrets/`, `credentials/`
- `git secrets` or equivalent pre-commit hook on every repo that touches credentials
- Rotate secrets on every suspected exposure — never try to determine if a secret was used

---

## 6. Privileged containers — never without a reason

```yaml
# CORRECT: explicit security context
securityContext:
  runAsNonRoot: true
  runAsUser: 1000
  allowPrivilegeEscalation: false
  readOnlyRootFilesystem: true
  capabilities:
    drop: [ALL]

# WRONG: no security context = defaults = potentially privileged
# Especially dangerous for DaemonSets that run on every node
```

---

## Security review checklist

Before merging any change that touches security-sensitive code:

- [ ] No hardcoded credentials, tokens, or secrets in code or config
- [ ] OIDC trust policies include both `aud` and `sub` conditions
- [ ] IAM roles grant only the specific actions and resources needed
- [ ] Kubernetes RBAC is namespace-scoped and uses only required verbs
- [ ] Network policies explicitly allow only required traffic; default-deny is in place
- [ ] Container security context sets `runAsNonRoot`, drops capabilities, `readOnlyRootFilesystem`
- [ ] Secrets are injected at runtime from Secrets Manager, not stored in manifests
- [ ] Any privileged or host-network containers are documented and justified
- [ ] Changes to OIDC trust model or IAM roots flagged for human security review before merge

---

## When to flag for human review

Some changes require a human security approval before merging, regardless of how clean they look:

- Any change to the OIDC issuer configuration or trust model root
- New ClusterRoles or ClusterRoleBindings
- Changes to admission webhooks or OPA/Kyverno policies
- New ingress resources that expose services externally
- Changes to base container images
- Any `privileged: true` or `hostNetwork: true` container
