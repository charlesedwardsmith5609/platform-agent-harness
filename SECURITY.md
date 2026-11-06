# Security policy

## Reporting

Please report vulnerabilities through a private GitHub security advisory on this repository. Do not open a public issue with exploit details. This is a personal project maintained on a best-effort basis, so response times are not guaranteed.

## Scope

This repository is a reference implementation: issue-driven coordination layer for Claude Code agents. Review defaults before using it in production. Never commit credentials; secret scanning and dependency updates are enabled where noted in the CI configuration. The portable permission source ships Claude Code `ask`/`deny` defaults for environ/env/ssh/cloud-cred/metadata access (aligned with agent-pairing-kit); Cursor still relies on `CLAUDE.md` agreements. Deny rules reduce accidental exposure and are not a sandbox.
