#!/usr/bin/env python3
"""Create or reconcile GitHub labels from setup/project-taxonomy.json."""

from __future__ import annotations

import argparse
import json
import sys

from platform_harness import IssueError, load_taxonomy, parse_json, run_gh

TAXONOMY_GROUPS = (
    "issue_types",
    "priorities",
    "concerns",
    "claim_statuses",
    "lanes",
)


def taxonomy_labels(taxonomy: dict) -> list[dict]:
    labels = []
    for group in TAXONOMY_GROUPS:
        labels.extend(taxonomy[group])
    names = [label["name"].lower() for label in labels]
    if len(set(names)) != len(names):
        raise IssueError("setup/project-taxonomy.json contains duplicate label names")
    return labels


def existing_labels() -> dict[str, dict]:
    listed = parse_json(
        run_gh(["label", "list", "--limit", "1000", "--json", "name,color,description"]),
        "label list",
    )
    return {item["name"].lower(): item for item in listed}


def color_value(label: dict) -> str:
    return label["color"].lstrip("#").lower()


def plan_actions(taxonomy: dict, *, only: str | None, reconcile: bool) -> list[dict]:
    wanted = taxonomy_labels(taxonomy)
    if only:
        wanted = [label for label in wanted if label["name"].lower() == only.lower()]
        if not wanted:
            raise IssueError(f"label is not configured in setup/project-taxonomy.json: {only}")
    existing = existing_labels()
    actions = []
    for label in wanted:
        current = existing.get(label["name"].lower())
        if current is None:
            actions.append({"action": "create", "label": label})
            continue
        if reconcile and (
            current.get("color", "").lower() != color_value(label)
            or (current.get("description") or "") != label["description"]
        ):
            actions.append({"action": "update", "label": label, "current": current})
        else:
            actions.append({"action": "keep", "label": label})
    return actions


def apply_actions(actions: list[dict]) -> None:
    for item in actions:
        label = item["label"]
        color = color_value(label)
        if item["action"] == "create":
            run_gh(
                [
                    "label",
                    "create",
                    label["name"],
                    "--color",
                    color,
                    "--description",
                    label["description"],
                ]
            )
        elif item["action"] == "update":
            run_gh(
                [
                    "label",
                    "edit",
                    item["current"]["name"],
                    "--color",
                    color,
                    "--description",
                    label["description"],
                ]
            )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", action="store_true", help="print actions without mutating GitHub")
    parser.add_argument("--label", help="operate on one configured label")
    parser.add_argument(
        "--reconcile",
        action="store_true",
        help="restore color and description for taxonomy-owned labels",
    )
    args = parser.parse_args(argv)
    taxonomy = load_taxonomy()
    actions = plan_actions(taxonomy, only=args.label, reconcile=args.reconcile)
    if args.plan:
        json.dump(actions, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0
    apply_actions(actions)
    created = sum(1 for item in actions if item["action"] == "create")
    updated = sum(1 for item in actions if item["action"] == "update")
    kept = sum(1 for item in actions if item["action"] == "keep")
    sys.stdout.write(f"labels create={created} update={updated} keep={kept}\n")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except IssueError as error:
        sys.stderr.write(f"{error}\n")
        raise SystemExit(1)
