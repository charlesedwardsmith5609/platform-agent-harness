# Observability skill

> **Load before:** designing or modifying OTel pipelines, SLO/SLI definitions, alert rules,
> dashboards, or any monitoring infrastructure.

---

## OTel instrumentation patterns

### Collector pipeline design

```yaml
# Standard OTel collector pipeline pattern
receivers:
  otlp:
    protocols:
      grpc: { endpoint: 0.0.0.0:4317 }
      http: { endpoint: 0.0.0.0:4318 }

processors:
  # Resource detection: inject service metadata from environment
  resource:
    attributes:
      - action: insert
        key: service.name
        value: ${SERVICE_NAME}
      - action: insert
        key: deployment.environment
        value: ${ENVIRONMENT}
  # Batch before export: critical for throughput and cost
  batch:
    timeout: 5s
    send_batch_size: 1024
    send_batch_max_size: 2048
  # Memory limiter: prevent OOM under backpressure
  memory_limiter:
    limit_mib: 400
    spike_limit_mib: 100
    check_interval: 5s

exporters:
  otlp:
    endpoint: ${OTEL_EXPORTER_ENDPOINT}
    headers: { "x-api-key": "${BACKEND_API_KEY}" }
  # Always include a debug/logging exporter for troubleshooting
  logging:
    verbosity: detailed
    sampling_initial: 5
    sampling_thereafter: 200

service:
  pipelines:
    traces:
      receivers: [otlp]
      processors: [memory_limiter, resource, batch]
      exporters: [otlp]
    metrics:
      receivers: [otlp]
      processors: [memory_limiter, resource, batch]
      exporters: [otlp]
```

**Invariants:**
- `memory_limiter` must come before `batch` in the processor chain (order matters)
- Always include `batch` — never export unbatched; it will exhaust rate limits at any real scale
- Pin collector image versions — `otel/opentelemetry-collector-contrib:latest` is not production

### SLO/SLI framework

SLOs have three components: the SLI (what you measure), the target (the goal), and the window
(the compliance period). All three must be defined before a service is "in production."

**SLI selection guide:**
- **Availability SLI:** `successful_requests / total_requests` — use for APIs and services
- **Latency SLI:** `requests_under_threshold / total_requests` — set threshold at your p99 target
- **Error rate SLI:** `error_requests / total_requests` — complement to availability
- **Saturation SLI:** `current_usage / capacity` — for queues, caches, databases

**Error budget calculation:**
```python
# Error budget for a 99.9% SLO over 30 days:
# error_budget_requests = total_requests * (1 - 0.999)
# error_budget_minutes  = 30 * 24 * 60 * (1 - 0.999) = 43.2 minutes

error_budget_fraction = 1 - slo_target   # 0.001 for 99.9%
```

### Multi-window burn rate alerting

Do not alert on raw error rate. Alert on burn rate — how fast you are consuming the error budget.

```python
# Burn rate thresholds for a 30-day window:
# These consume X% of the budget in Y hours:
ALERT_WINDOWS = [
    # (short_window, long_window, budget_pct, severity)
    ("1h",  "5h",  2,  "page"),      # burn_rate >= 14.4x
    ("6h",  "30h", 5,  "page"),      # burn_rate >= 6.0x
    ("24h", "72h", 10, "ticket"),    # burn_rate >= 3.0x
]
```

See `slo-toolkit/` for a CLI to generate these automatically.

**Alert fatigue rule:** if engineers are silencing or ignoring an alert, the alert is wrong —
not the engineers. Fix the alert, not the behavior.

### Dashboard design

Every service dashboard should have (in this order):
1. SLO burn rate + error budget remaining (the first thing on-call looks at)
2. Error rate + request rate (traffic shape)
3. Latency p50/p95/p99 (performance)
4. Saturation metrics (resource usage as % of capacity)
5. Downstream dependency health (what this service depends on)

---

## Alert engineering checklist

Before shipping a new alert:

- [ ] Alert fires on **symptom**, not cause (high error rate, not "disk is 80% full")
- [ ] Alert has a **runbook link** — on-call should never see an alert without knowing what to do
- [ ] Alert has been **tested with real failure data** — simulated or historical
- [ ] Alert has an appropriate **evaluation window** (too short = noisy, too long = slow)
- [ ] Alert has a **priority/severity** that matches its actual urgency
- [ ] Alert was **reviewed by someone who will be on-call** — don't ship alerts you won't have to respond to
- [ ] Alert does not **duplicate another alert** for the same condition

---

## Cost attribution for observability infrastructure

OTel collectors, metrics backends, and logging pipelines can be significant cost centers.
Tag all observability resources:

```hcl
# Required tags on all observability infrastructure
tags = {
  team        = "platform"
  component   = "observability"
  environment = var.environment
  managed-by  = "terraform"
}
```

Track observability cost per engineering team where possible — teams that instrument heavily
pay more than teams that don't, which creates the right incentive structure.
