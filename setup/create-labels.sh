#!/usr/bin/env bash
# setup/create-labels.sh
# Creates all GitHub issue labels for the platform engineering agent harness.
# Run once per repository: bash setup/create-labels.sh

set -euo pipefail

echo "Creating lane labels..."
gh label create "lane:foundation"    -c "#1D76DB" -d "Shared foundation: Terraform modules, OIDC trust, base images, SLO framework — COORDINATOR ONLY" --force
gh label create "lane:compute"       -c "#0E8A16" -d "EKS/Kubernetes fleet, node groups, resource management, Kubernetes upgrades" --force
gh label create "lane:networking"    -c "#5319E7" -d "Envoy Proxy, API gateway, service mesh, TLS/mTLS, ingress, DNS" --force
gh label create "lane:identity"      -c "#B60205" -d "OIDC workload identity, secrets management, cert rotation, RBAC, IAM" --force
gh label create "lane:observability" -c "#006B75" -d "OTel pipeline, SLO/SLI alert rules, dashboards, on-call routing" --force
gh label create "lane:ci-cd"         -c "#BFD4F2" -d "Deployment pipelines, release automation, build infrastructure" --force
gh label create "lane:platform-api"  -c "#C2E0C6" -d "Internal developer APIs, service onboarding, self-service tooling" --force
gh label create "lane:cost"          -c "#F9D0C4" -d "Cost attribution, FinOps dashboards, budget alerts, chargeback" --force

echo "Creating status labels..."
gh label create "status:wip"         -c "#D93F0B" -d "Claimed and in progress — do NOT grab" --force
gh label create "status:in-review"   -c "#FBCA04" -d "PR open, awaiting coordinator review and merge" --force

echo "Creating type labels..."
gh label create "bug"         -c "#D73A4A" -d "Something is broken in production — P0/P1 only" --force
gh label create "feature"     -c "#A2EEEF" -d "New platform capability" --force
gh label create "enhancement" -c "#84B6EB" -d "Improving an existing, working capability" --force
gh label create "hardening"   -c "#E4E669" -d "Defensive improvement, tech debt, missing validation, weak patterns" --force

echo "Creating priority labels..."
gh label create "P0" -c "#B60205" -d "Production incident or imminent security exploit — drop everything" --force
gh label create "P1" -c "#D93F0B" -d "Every other bug; or non-bug blocking another team's delivery" --force
gh label create "P2" -c "#E4E669" -d "Important non-bug; complete this sprint or cycle" --force
gh label create "P3" -c "#0075CA" -d "Lower priority; schedule when capacity allows" --force
gh label create "P4" -c "#CFD3D7" -d "Nice to have; add to backlog" --force

echo "Creating concern labels..."
gh label create "security"           -c "#B60205" -d "Has a security dimension — on a bug: fix first" --force
gh label create "blocked"            -c "#000000" -d "Waiting on a dependency — add Blocked by #N in body" --force
gh label create "incident-follow-up" -c "#FBCA04" -d "Generated from postmortem; prioritize above normal enhancement work" --force

echo ""
echo "Labels created. Next steps:"
echo "1. Create milestones for your delivery phases (gh milestone create)"
echo "2. Create a GitHub Project board (see setup-guide.md)"
echo "3. Adapt CLAUDE.md PROJECT-SPECIFIC sections to your repository"
echo "4. Create docs/STATUS.md describing current state and active work"
