import json
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SETUP = ROOT / "setup"
sys.path.insert(0, str(SETUP))

from platform_harness import (
    IssueError,
    load_taxonomy,
    set_command_runners,
    sync_project_lane,
)
from platform_harness.issue_ops import (
    change_child_relation,
    classify_issue,
    create_issue,
)
from platform_harness.project_sync import project_board_config
from platform_harness.runtime import REPOSITORY_ROOT


class MutableFakeGitHub:
    def __init__(self):
        self.issues: dict[int, dict] = {}
        self.next_number = 100
        self.labels = {
            "hardening": {"name": "hardening", "color": "E4E669", "description": ""},
            "p2": {"name": "P2", "color": "E4E669", "description": ""},
            "lane:observability": {
                "name": "lane:observability",
                "color": "006B75",
                "description": "",
            },
            "lane:compute": {"name": "lane:compute", "color": "0E8A16", "description": ""},
            "security": {"name": "security", "color": "B60205", "description": ""},
            "status:wip": {"name": "status:wip", "color": "D93F0B", "description": ""},
        }
        self.project_calls: list[list[str]] = []
        self.comment_clock = 0

    def __call__(self, args: list[str]) -> str:
        if args[:2] == ["label", "list"]:
            return json.dumps(list(self.labels.values()))
        if args[:2] == ["label", "create"]:
            name = args[2]
            self.labels[name.lower()] = {
                "name": name,
                "color": "ffffff",
                "description": "",
            }
            return ""
        if args[:2] == ["issue", "create"]:
            title = args[args.index("--title") + 1]
            labels = []
            milestone = None
            index = 0
            while index < len(args):
                if args[index] == "--label":
                    labels.append({"name": args[index + 1]})
                    index += 2
                    continue
                if args[index] == "--milestone":
                    milestone = {"title": args[index + 1]}
                    index += 2
                    continue
                index += 1
            number = self.next_number
            self.next_number += 1
            url = f"https://example.test/issues/{number}"
            self.issues[number] = {
                "number": number,
                "title": title,
                "body": "created",
                "state": "OPEN",
                "labels": labels,
                "milestone": milestone,
                "assignees": [],
                "comments": [],
                "parent": None,
                "subIssues": {"nodes": [], "totalCount": 0},
                "url": url,
            }
            return url + "\n"
        if args[:2] == ["issue", "view"]:
            number = int(args[2])
            return json.dumps(self.issues[number])
        if args[:2] == ["issue", "edit"]:
            number = int(args[2])
            issue = self.issues[number]
            labels = {item["name"].lower(): item for item in issue.get("labels") or []}
            index = 3
            while index < len(args):
                if args[index] == "--add-label":
                    labels[args[index + 1].lower()] = {"name": args[index + 1]}
                    index += 2
                    continue
                if args[index] == "--remove-label":
                    labels.pop(args[index + 1].lower(), None)
                    index += 2
                    continue
                if args[index] == "--milestone":
                    issue["milestone"] = {"title": args[index + 1]}
                    index += 2
                    continue
                if args[index] == "--remove-milestone":
                    issue["milestone"] = None
                    index += 1
                    continue
                if args[index] == "--add-sub-issue":
                    child = int(args[index + 1])
                    nodes = issue.setdefault("subIssues", {"nodes": [], "totalCount": 0})
                    nodes["nodes"].append(self.issues[child])
                    nodes["totalCount"] = len(nodes["nodes"])
                    self.issues[child]["parent"] = {
                        "number": number,
                        "title": issue["title"],
                        "state": issue["state"],
                        "url": issue["url"],
                    }
                    index += 2
                    continue
                if args[index] == "--remove-parent":
                    parent = issue.get("parent")
                    if parent:
                        parent_issue = self.issues[parent["number"]]
                        nodes = parent_issue.get("subIssues", {"nodes": []})["nodes"]
                        parent_issue["subIssues"]["nodes"] = [
                            node for node in nodes if node.get("number") != number
                        ]
                        parent_issue["subIssues"]["totalCount"] = len(
                            parent_issue["subIssues"]["nodes"]
                        )
                    issue["parent"] = None
                    index += 1
                    continue
                index += 1
            issue["labels"] = list(labels.values())
            return ""
        if args[:2] == ["issue", "comment"]:
            number = int(args[2])
            body = args[args.index("--body") + 1]
            self.comment_clock += 1
            self.issues[number].setdefault("comments", []).append(
                {
                    "id": self.comment_clock,
                    "body": body,
                    "createdAt": f"2026-01-01T00:00:{self.comment_clock:02d}Z",
                }
            )
            return ""
        if args[:1] == ["project"]:
            self.project_calls.append(list(args))
            return ""
        raise AssertionError(f"unexpected gh args: {args}")


class MutationTests(unittest.TestCase):
    def tearDown(self):
        set_command_runners(gh=None, git=None)

    def test_create_issue_with_ignored_body(self):
        body = REPOSITORY_ROOT / "mutation-create.issue-body.local.md"
        body.write_text("create body\n", encoding="utf-8")
        fake = MutableFakeGitHub()
        set_command_runners(gh=fake)
        try:
            result = create_issue(
                load_taxonomy(),
                [
                    "--title",
                    "Collector missing memory limiter docs",
                    "--body-file",
                    "mutation-create.issue-body.local.md",
                    "--type",
                    "hardening",
                    "--priority",
                    "P2",
                    "--lane",
                    "lane:observability",
                ],
            )
            self.assertEqual(result["number"], 100)
            self.assertFalse(result["project"]["synced"])
            self.assertIn("lane:observability", result["labels"])
        finally:
            body.unlink(missing_ok=True)

    def test_classify_preserves_status_wip(self):
        rationale = REPOSITORY_ROOT / "mutation-classify.rationale.local.md"
        rationale.write_text("triage note\n", encoding="utf-8")
        fake = MutableFakeGitHub()
        fake.issues[50] = {
            "number": 50,
            "title": "existing",
            "body": "b",
            "state": "OPEN",
            "labels": [
                {"name": "bug"},
                {"name": "P1"},
                {"name": "lane:compute"},
                {"name": "status:wip"},
            ],
            "milestone": None,
            "comments": [],
            "parent": None,
            "subIssues": {"nodes": [], "totalCount": 0},
            "url": "https://example.test/issues/50",
        }
        set_command_runners(gh=fake)
        try:
            result = classify_issue(
                load_taxonomy(),
                [
                    "--issue",
                    "50",
                    "--type",
                    "hardening",
                    "--priority",
                    "P2",
                    "--lane",
                    "lane:observability",
                    "--milestone",
                    "Phase 1: Foundational",
                    "--rationale-file",
                    "mutation-classify.rationale.local.md",
                ],
            )
            names = {label["name"].lower() for label in fake.issues[50]["labels"]}
            self.assertIn("status:wip", names)
            self.assertIn("hardening", names)
            self.assertNotIn("bug", names)
            self.assertEqual(result["milestone"], "Phase 1: Foundational")
        finally:
            rationale.unlink(missing_ok=True)

    def test_link_and_unlink_child(self):
        fake = MutableFakeGitHub()
        for number in (10, 11):
            fake.issues[number] = {
                "number": number,
                "title": f"issue-{number}",
                "body": "b",
                "state": "OPEN",
                "labels": [],
                "milestone": None,
                "comments": [],
                "parent": None,
                "subIssues": {"nodes": [], "totalCount": 0},
                "url": f"https://example.test/issues/{number}",
            }
        set_command_runners(gh=fake)
        linked = change_child_relation(
            ["--parent", "10", "--child", "11"], unlink=False
        )
        self.assertTrue(linked["linked"])
        self.assertEqual(fake.issues[10]["subIssues"]["totalCount"], 1)
        unlinked = change_child_relation(
            ["--parent", "10", "--child", "11"], unlink=True
        )
        self.assertFalse(unlinked["linked"])
        self.assertEqual(fake.issues[11]["parent"], None)

    def test_project_sync_when_configured(self):
        fake = MutableFakeGitHub()
        set_command_runners(gh=fake)
        taxonomy = load_taxonomy()
        taxonomy["project_board"] = {
            "owner": "acme",
            "number": 7,
            "lane_field": "Lane",
            "lane_option_map": {"lane:observability": "Observability"},
        }
        result = sync_project_lane(
            taxonomy,
            issue_number=3,
            lane="lane:observability",
            issue_url="https://github.com/acme/platform/issues/3",
        )
        self.assertTrue(result["synced"])
        self.assertEqual(len(fake.project_calls), 2)
        self.assertEqual(fake.project_calls[0][1], "item-add")
        self.assertEqual(project_board_config(load_taxonomy()), None)

    def test_project_board_rejects_incomplete_config(self):
        taxonomy = load_taxonomy()
        taxonomy["project_board"] = {"owner": "acme", "number": 1}
        with self.assertRaisesRegex(IssueError, "missing required keys"):
            project_board_config(taxonomy)

    def test_project_board_rejects_unsafe_owner(self):
        taxonomy = load_taxonomy()
        taxonomy["project_board"] = {
            "owner": "acme; rm -rf /",
            "number": 7,
            "lane_field": "Lane",
            "lane_option_map": {"lane:observability": "Observability"},
        }
        with self.assertRaisesRegex(IssueError, "project_board.owner"):
            project_board_config(taxonomy)

    def test_project_sync_rejects_non_github_url(self):
        taxonomy = load_taxonomy()
        taxonomy["project_board"] = {
            "owner": "acme",
            "number": 7,
            "lane_field": "Lane",
            "lane_option_map": {"lane:observability": "Observability"},
        }
        with self.assertRaisesRegex(IssueError, "issue URL"):
            sync_project_lane(
                taxonomy,
                issue_number=3,
                lane="lane:observability",
                issue_url="https://example.test/issues/3",
            )


if __name__ == "__main__":
    unittest.main()
