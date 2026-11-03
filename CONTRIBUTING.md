# Contributing

Issues and pull requests are welcome. Keep changes small and focused, and explain the why in the PR description.

## Before opening a PR

Run the same checks CI runs:

```bash
pip install -e ".[dev]"
python -m ruff check setup tests
python -m mypy
python -m unittest discover -s tests -v
python setup/apply_permissions.py --dry-run
```

## Guidelines

- Add or update tests with behavior changes.
- Do not commit secrets, tokens, or generated artifacts.
- If a change touches AI-generated code, review it as you would any other contribution.
