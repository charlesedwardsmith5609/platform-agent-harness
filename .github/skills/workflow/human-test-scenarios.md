# Skill: Human test scenarios (platform engineering)

**Trigger:** any change that requires human or integration validation before it can be considered
complete — infrastructure that can't be fully tested with unit/integration tests alone.

**Goal:** produce a durable, specific checklist of validation steps that a human or an integration
test can follow to confirm the change works correctly in a real environment.

> In platform engineering, "human test scenarios" often means "validation steps that require a
> real cluster or cloud environment" — not just unit tests. Treat the human (or the integration
> environment) as a scarce resource and write scenarios that are as specific and self-contained
> as possible.

---

## When to add scenarios

Add scenarios to `docs/test-scenarios/pending.md` for any change where:
- The validation requires a live Kubernetes cluster or AWS account
- The change affects service-to-service communication or traffic routing
- The change modifies OIDC/IAM trust and correctness can't be verified synthetically
- The change affects the OTel pipeline and trace delivery must be confirmed end-to-end
- The change modifies SLO alerts and you need to confirm they fire correctly

**Do NOT add scenarios for:**
- Changes fully covered by `terraform validate` + unit tests (just reference the test output)
- Documentation-only changes
- Cost attribution tag changes (verify with `aws resourcegroupstaggingapi`)

---

## Scenario format

```markdown
## Scenario: [Descriptive name]

**Issue:** #<n>
**Lane:** lane:<X>
**Environment:** staging / production / either
**Requires:** [what environment/access is needed to validate this]

### Steps

1. [Exact step with specific command or action]
   Expected: [what should happen]
   Failure: [what failure looks like]

2. [Next step]
   Expected: [...]

### Validation complete when

- [ ] [Specific condition that confirms the change works]
- [ ] [Second condition if applicable]

### Rollback if validation fails

[Exact rollback command or procedure]
```

---

## Platform engineering scenario examples

### OTel pipeline validation

```markdown
## Scenario: OTel collector pipeline — traces reach backend

**Issue:** #42
**Lane:** lane:observability
**Environment:** staging
**Requires:** kubectl access to observability namespace; access to Chronosphere/Datadog

### Steps

1. Deploy a test workload with OTel instrumentation:
   `kubectl apply -f tests/fixtures/otel-test-workload.yaml -n observability-test`
   Expected: pod reaches Running state

2. Generate test traffic:
   `kubectl exec -n observability-test deployment/otel-test -- curl http://localhost:8080/test`
   Expected: HTTP 200 response

3. Verify traces appear in the backend within 30 seconds:
   - Open Chronosphere → Services → otel-test-workload
   - Expected: at least one trace visible with service.name = "otel-test-workload"
   - Failure: no traces visible after 60 seconds → check collector logs:
     `kubectl logs -n observability deployment/otel-collector --tail=50`

4. Verify metrics appear:
   - Open Grafana → Platform → OTel Test Dashboard
   - Expected: request_total counter incrementing

### Validation complete when

- [ ] Traces visible in backend with correct service.name attribute
- [ ] Metrics visible in Grafana with correct labels
- [ ] No error logs in collector pod

### Rollback if validation fails

`kubectl rollout undo deployment/otel-collector -n observability`
```

### OIDC workload identity validation

```markdown
## Scenario: OIDC workload identity — service can assume IAM role

**Issue:** #87
**Lane:** lane:identity
**Environment:** staging
**Requires:** kubectl access; AWS console or CLI access to staging account

### Steps

1. Verify the service account annotation is correct:
   `kubectl get serviceaccount payments-api -n payments -o jsonpath='{.metadata.annotations}'`
   Expected: `{"eks.amazonaws.com/role-arn":"arn:aws:iam::ACCOUNT:role/payments-api-workload"}`

2. Verify the pod has the projected service account token mounted:
   `kubectl exec -n payments deployment/payments-api -- cat /var/run/secrets/eks.amazonaws.com/serviceaccount/token | cut -d. -f2 | base64 -d 2>/dev/null | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('sub', 'ERROR'))"`
   Expected: `system:serviceaccount:payments:payments-api`

3. Verify AWS STS assume role works from within the pod:
   `kubectl exec -n payments deployment/payments-api -- aws sts get-caller-identity`
   Expected: ARN contains `role/payments-api-workload`
   Failure: `InvalidClientTokenId` or `AccessDenied` → IAM role trust policy mismatch

### Validation complete when

- [ ] Service account has correct IAM role annotation
- [ ] Token subject matches `system:serviceaccount:NAMESPACE:SERVICE_ACCOUNT`
- [ ] `aws sts get-caller-identity` from within pod returns correct role ARN

### Rollback if validation fails

The IAM role and Kubernetes service account changes are independent:
- Revert service account annotation: `kubectl annotate serviceaccount payments-api -n payments eks.amazonaws.com/role-arn-`
- Revert IAM role: `terraform apply -target=aws_iam_role.payments_api`
```

---

## Pending scenarios file

Maintain `docs/test-scenarios/pending.md` as the live queue:

```markdown
# Pending validation scenarios

Scenarios waiting for human or integration validation. Check off each item after confirming,
then move completed batches to `docs/test-scenarios/archive/YYYY-MM-DD.md`.

## In queue

[Paste scenarios here as they are added by workers]

## Confirmed (ready to archive)

[Move completed scenarios here before archiving]
```

**Archive after confirmation** — move confirmed batches to `docs/test-scenarios/archive/` so
the pending file stays manageable. Don't flood the human with more scenarios than they can
validate in one session; coordinate with the coordinator to batch related validations.
