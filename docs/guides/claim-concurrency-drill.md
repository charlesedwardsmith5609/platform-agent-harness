# Claim concurrency drill

Proves fail-closed claim behavior against a live GitHub repository.

```bash
python setup/claim_concurrency_drill.py
```

The script:

1. Creates a temporary `lane:platform-api` hardening issue
2. Claims it as `drill-worker-a`
3. Asserts a second claim as `drill-worker-b` fails closed
4. Releases with `--mode abandon` and closes the issue

Requires `gh` auth (or `GH_TOKEN`) with issue write access.
