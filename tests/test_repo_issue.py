import json
import sys
import unittest
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SETUP = ROOT / "setup"
sys.path.insert(0, str(SETUP))

from apply_permissions import PLACEHOLDER, command_to_claude, load_source, materialize
from platform_harness import (
    IssueError,
    active_claim,
    active_claims,
    claim_issue,
    claim_winner,
    classification_from_arguments,
    format_claim_body,
    format_release_body,
    load_taxonomy,
    normalize_issue,
    set_command_runners,
    sub_issue_nodes,
    validate_title,
)
from platform_harness.taxonomy import reject_secret_content
from platform_harness.cli import build_parser
from platform_harness.issue_ops import list_issues, release_issue
from platform_harness.runtime import REPOSITORY_ROOT


class TaxonomyTests(unittest.TestCase):
    def test_taxonomy_declares_platform_lanes(self):
        taxonomy = load_taxonomy()
        names = {lane["name"] for lane in taxonomy["lanes"]}
        self.assertIn("lane:foundation", names)
        self.assertIn("lane:observability", names)
        self.assertFalse(taxonomy["require_milestone_on_create"])
        self.assertTrue(taxonomy["require_milestone_on_classify"])

    def test_create_classification_omits_milestone(self):
        taxonomy = load_taxonomy()
        result = classification_from_arguments(
            taxonomy,
            [
                "--title",
                "OTel collector dropping spans under backpressure",
                "--body-file",
                "scratch.issue-body.local.md",
                "--type",
                "hardening",
                "--priority",
                "P2",
                "--lane",
                "lane:observability",
                "--concern",
                "security",
            ],
        )
        self.assertIsNone(result["milestone"])
        self.assertEqual(result["lane"], "lane:observability")
        self.assertEqual(
            [label["name"] for label in result["labels"]],
            ["hardening", "P2", "lane:observability", "security"],
        )

    def test_classify_requires_configured_milestone(self):
        taxonomy = load_taxonomy()
        with self.assertRaisesRegex(IssueError, "require --milestone"):
            classification_from_arguments(
                taxonomy,
                [
                    "--issue",
                    "12",
                    "--type",
                    "hardening",
                    "--priority",
                    "P2",
                    "--lane",
                    "lane:compute",
                    "--rationale-file",
                    "scratch.rationale.local.md",
                ],
                rationale=True,
            )

    def test_unknown_lane_is_rejected(self):
        taxonomy = load_taxonomy()
        with self.assertRaisesRegex(IssueError, "not configured"):
            classification_from_arguments(
                taxonomy,
                [
                    "--title",
                    "valid title",
                    "--body-file",
                    "scratch.issue-body.local.md",
                    "--type",
                    "bug",
                    "--priority",
                    "P1",
                    "--lane",
                    "lane:renderer",
                ],
            )

    def test_title_rejects_control_characters(self):
        with self.assertRaisesRegex(IssueError, "printable"):
            validate_title("bad\ntitle")
        self.assertEqual(
            validate_title("OIDC trust policy missing sub condition"),
            "OIDC trust policy missing sub condition",
        )


class SubIssuesShapeTests(unittest.TestCase):
    def test_sub_issues_object_payload(self):
        self.assertEqual(sub_issue_nodes({"nodes": [], "totalCount": 0}), [])
        nodes = sub_issue_nodes(
            {"nodes": [{"number": 3, "title": "child", "state": "OPEN", "url": "u"}], "totalCount": 1}
        )
        self.assertEqual(nodes[0]["number"], 3)

    def test_normalize_issue_accepts_sub_issues_object(self):
        issue = normalize_issue(
            {
                "number": 2,
                "title": "t",
                "body": "b",
                "state": "OPEN",
                "labels": [],
                "comments": [],
                "parent": None,
                "subIssues": {"nodes": [], "totalCount": 0},
                "url": "https://example.test/issues/2",
            }
        )
        self.assertEqual(issue["children"], [])
        self.assertIsNone(issue["parent"])


class PermissionSourceTests(unittest.TestCase):
    def test_permission_source_is_portable(self):
        document = load_source()
        example_root = Path("E:/example/platform-repo")
        resolved, claude = materialize(example_root, document)
        self.assertNotIn(PLACEHOLDER, json.dumps(resolved))
        self.assertIn(str(example_root), resolved["locations"])
        location = resolved["locations"][str(example_root)]
        self.assertEqual(location["allowed_directories"], [str(example_root)])
        allow = claude["permissions"]["allow"]
        self.assertIn("Bash(python setup/repo_issue.py *)", allow)
        self.assertIn("Bash(gh pr create *)", allow)
        self.assertNotIn("Bash(python *)", allow)
        self.assertNotIn("Bash(python3 *)", allow)
        self.assertNotIn("Bash(gh issue *)", allow)
        self.assertNotIn("Bash(git push *)", allow)
        self.assertNotIn("Bash(gh pr *)", allow)
        self.assertEqual(command_to_claude("gh auth status"), "Bash(gh auth status)")
        source_text = (SETUP / "agent-permissions.json").read_text(encoding="utf-8")
        self.assertIn("REPLACE_WITH_YOUR_REPO_GIT_ROOT", source_text)
        self.assertNotIn("python:*", source_text)
        self.assertNotIn("git push:*", source_text)
        self.assertNotIn("nme-mcp", source_text)

    def test_materialize_rejects_broad_python(self):
        document = load_source()
        entry = document["locations"][PLACEHOLDER]
        for approval in entry["tool_approvals"]:
            if approval.get("kind") == "commands":
                approval["commandIdentifiers"] = ["python:*"]
        with self.assertRaises(IssueError):
            materialize(Path("E:/example/platform-repo"), document)


class SecretContentTests(unittest.TestCase):
    def test_rejects_github_pat(self):
        with self.assertRaises(IssueError):
            reject_secret_content("token=ghp_abcdefghijklmnopqrstuvwxyz012345", "body")

    def test_allows_normal_body(self):
        reject_secret_content("Harden the allowlist; no secrets here.", "body")


class ClaimMarkerTests(unittest.TestCase):
    def test_free_text_claim_is_ignored(self):
        issue = {
            "comments": [
                {
                    "body": "Please CLAIM this after standup",
                    "createdAt": "2026-01-01T00:00:00Z",
                }
            ]
        }
        self.assertFalse(active_claim(issue))
        self.assertEqual(active_claims(issue), [])

    def test_structured_claim_and_release(self):
        claim_id = str(uuid.uuid4())
        issue = {
            "comments": [
                {
                    "body": format_claim_body(
                        claim_id=claim_id,
                        lane="lane:observability",
                        worker="alice",
                        branch="issue/1-otel",
                        stamp="2026-01-01T00:00:00Z",
                    ),
                    "createdAt": "2026-01-01T00:00:00Z",
                },
                {
                    "body": format_release_body(claim_id=claim_id, reason="done"),
                    "createdAt": "2026-01-01T00:01:00Z",
                },
            ]
        }
        self.assertFalse(active_claim(issue))

    def test_earliest_claim_wins(self):
        first = str(uuid.uuid4())
        second = str(uuid.uuid4())
        issue = {
            "comments": [
                {
                    "body": format_claim_body(
                        claim_id=first,
                        lane="lane:compute",
                        worker="a",
                        branch="issue/1-a",
                        stamp="2026-01-01T00:00:00Z",
                    ),
                    "createdAt": "2026-01-01T00:00:00Z",
                },
                {
                    "body": format_claim_body(
                        claim_id=second,
                        lane="lane:compute",
                        worker="b",
                        branch="issue/1-b",
                        stamp="2026-01-01T00:00:01Z",
                    ),
                    "createdAt": "2026-01-01T00:00:01Z",
                },
            ]
        }
        self.assertEqual(claim_winner(issue)["id"], first)
        self.assertEqual(len(active_claims(issue)), 2)

    def test_star_release_clears_all(self):
        first = str(uuid.uuid4())
        issue = {
            "comments": [
                {
                    "body": format_claim_body(
                        claim_id=first,
                        lane="lane:compute",
                        worker="a",
                        branch="issue/1-a",
                        stamp="2026-01-01T00:00:00Z",
                    ),
                    "createdAt": "2026-01-01T00:00:00Z",
                },
                {
                    "body": format_release_body(claim_id="*", reason="coordinator reset"),
                    "createdAt": "2026-01-01T00:02:00Z",
                },
            ]
        }
        self.assertFalse(active_claim(issue))


class FakeGitHub:
    """Minimal in-memory gh issue surface for claim race tests."""

    def __init__(self, issue: dict, *, catalog: list[dict] | None = None):
        self.issue = issue
        self.catalog = catalog or [issue]
        self.labels = {
            "status:wip": {
                "name": "status:wip",
                "color": "D93F0B",
                "description": "wip",
            },
            "blocked": {
                "name": "blocked",
                "color": "000000",
                "description": "blocked",
            },
        }
        self.comment_clock = 0
        self.label_list_calls = 0
        self.issue_list_calls = 0
        self.issue_view_calls = 0

    def __call__(self, args: list[str]) -> str:
        if args[:2] == ["label", "list"]:
            self.label_list_calls += 1
            return json.dumps(list(self.labels.values()))
        if args[:2] == ["label", "create"]:
            name = args[2]
            self.labels[name.lower()] = {
                "name": name,
                "color": "ffffff",
                "description": "",
            }
            return ""
        if args[:2] == ["issue", "list"]:
            self.issue_list_calls += 1
            return json.dumps(self.catalog)
        if args[:2] == ["issue", "view"]:
            self.issue_view_calls += 1
            return json.dumps(self.issue)
        if args[:2] == ["issue", "comment"]:
            body_idx = args.index("--body")
            self.comment_clock += 1
            self.issue.setdefault("comments", []).append(
                {
                    "id": self.comment_clock,
                    "body": args[body_idx + 1],
                    "createdAt": f"2026-01-01T00:00:{self.comment_clock:02d}Z",
                }
            )
            return ""
        if args[:2] == ["issue", "edit"]:
            labels = {item["name"].lower(): item for item in self.issue.get("labels") or []}
            index = 2
            while index < len(args):
                if args[index] == "--add-label":
                    name = args[index + 1]
                    labels[name.lower()] = {"name": name}
                    index += 2
                    continue
                if args[index] == "--remove-label":
                    labels.pop(args[index + 1].lower(), None)
                    index += 2
                    continue
                index += 1
            self.issue["labels"] = list(labels.values())
            return ""
        raise AssertionError(f"unexpected gh args: {args}")


class ClaimRaceTests(unittest.TestCase):
    def tearDown(self):
        set_command_runners(gh=None, git=None)

    def _open_issue(self) -> dict:
        return {
            "number": 7,
            "title": "Karpenter consolidation thrashing",
            "body": "body",
            "state": "OPEN",
            "labels": [{"name": "lane:compute"}],
            "milestone": None,
            "assignees": [],
            "comments": [],
            "url": "https://example.test/issues/7",
        }

    def test_claim_succeeds_and_sets_wip(self):
        fake = FakeGitHub(self._open_issue())
        set_command_runners(gh=fake)
        taxonomy = load_taxonomy()
        result = claim_issue(
            taxonomy,
            [
                "--issue",
                "7",
                "--lane",
                "lane:compute",
                "--worker",
                "alice",
                "--branch",
                "issue/7-karpenter",
            ],
        )
        self.assertEqual(result["number"], 7)
        self.assertIn("claim_id", result)
        self.assertTrue(active_claim(fake.issue))
        self.assertIn("status:wip", {label["name"].lower() for label in fake.issue["labels"]})

    def test_second_claim_loses_race(self):
        issue = self._open_issue()
        first_id = str(uuid.uuid4())
        issue["comments"] = [
            {
                "id": 1,
                "body": format_claim_body(
                    claim_id=first_id,
                    lane="lane:compute",
                    worker="bob",
                    branch="issue/7-bob",
                    stamp="2026-01-01T00:00:00Z",
                ),
                "createdAt": "2026-01-01T00:00:00Z",
            }
        ]
        issue["labels"] = [{"name": "lane:compute"}, {"name": "status:wip"}]
        fake = FakeGitHub(issue)
        set_command_runners(gh=fake)
        taxonomy = load_taxonomy()
        with self.assertRaisesRegex(IssueError, "not grabbable|already has a structured CLAIM"):
            claim_issue(
                taxonomy,
                [
                    "--issue",
                    "7",
                    "--lane",
                    "lane:compute",
                    "--worker",
                    "alice",
                    "--branch",
                    "issue/7-alice",
                ],
            )

    def test_concurrent_second_comment_loses_after_post(self):
        """Simulate TOCTOU: preflight clean, then another claim appears as earlier winner."""
        issue = self._open_issue()
        fake = FakeGitHub(issue)
        original = fake.__call__

        def racing_gh(args: list[str]) -> str:
            if args[:2] == ["issue", "comment"]:
                # Insert an earlier competing claim before our comment lands.
                competitor = str(uuid.uuid4())
                issue["comments"].insert(
                    0,
                    {
                        "id": 0,
                        "body": format_claim_body(
                            claim_id=competitor,
                            lane="lane:compute",
                            worker="bob",
                            branch="issue/7-bob",
                            stamp="2026-01-01T00:00:00Z",
                        ),
                        "createdAt": "2026-01-01T00:00:00Z",
                    },
                )
            return original(args)

        set_command_runners(gh=racing_gh)
        taxonomy = load_taxonomy()
        with self.assertRaisesRegex(IssueError, "claim race lost"):
            claim_issue(
                taxonomy,
                [
                    "--issue",
                    "7",
                    "--lane",
                    "lane:compute",
                    "--worker",
                    "alice",
                    "--branch",
                    "issue/7-alice",
                ],
            )
        # Loser must have posted a structured release for its own id.
        releases = [
            comment
            for comment in issue["comments"]
            if "harness:release" in comment["body"] and "lost claim race" in comment["body"]
        ]
        self.assertEqual(len(releases), 1)
        self.assertEqual(claim_winner(issue)["body"].count("worker=bob"), 1)


class ListAndReleaseTests(unittest.TestCase):
    def tearDown(self):
        set_command_runners(gh=None, git=None)

    def test_list_is_single_batched_call(self):
        issue = {
            "number": 9,
            "title": "t",
            "body": "b",
            "state": "OPEN",
            "labels": [{"name": "lane:ci-cd"}],
            "milestone": None,
            "assignees": [],
            "comments": [],
            "url": "https://example.test/issues/9",
        }
        fake = FakeGitHub(issue, catalog=[issue, dict(issue, number=10)])
        set_command_runners(gh=fake)
        result = list_issues(["--state", "open"])
        self.assertEqual(len(result), 2)
        self.assertEqual(fake.issue_list_calls, 1)
        self.assertEqual(fake.issue_view_calls, 0)

    def test_label_list_is_memoized_across_ensure(self):
        fake = FakeGitHub(
            {
                "number": 7,
                "title": "t",
                "body": "b",
                "state": "OPEN",
                "labels": [{"name": "lane:compute"}],
                "comments": [],
                "url": "u",
            }
        )
        set_command_runners(gh=fake)
        taxonomy = load_taxonomy()
        claim_issue(
            taxonomy,
            [
                "--issue",
                "7",
                "--lane",
                "lane:compute",
                "--worker",
                "alice",
                "--branch",
                "issue/7-a",
            ],
        )
        self.assertEqual(fake.label_list_calls, 1)

    def test_release_abandon_does_not_add_blocked(self):
        reason = REPOSITORY_ROOT / "release-abandon.rationale.local.md"
        reason.write_text("stepping away\n", encoding="utf-8")
        issue = {
            "number": 11,
            "title": "t",
            "body": "b",
            "state": "OPEN",
            "labels": [{"name": "lane:platform-api"}, {"name": "status:wip"}],
            "comments": [],
            "url": "https://example.test/issues/11",
        }
        fake = FakeGitHub(issue)
        set_command_runners(gh=fake)
        try:
            result = release_issue(
                load_taxonomy(),
                [
                    "--issue",
                    "11",
                    "--mode",
                    "abandon",
                    "--reason-file",
                    "release-abandon.rationale.local.md",
                ],
            )
            self.assertEqual(result["mode"], "abandon")
            names = {label["name"].lower() for label in fake.issue["labels"]}
            self.assertNotIn("status:wip", names)
            self.assertNotIn("blocked", names)
        finally:
            reason.unlink(missing_ok=True)

    def test_release_blocked_adds_blocked(self):
        reason = REPOSITORY_ROOT / "release-blocked.rationale.local.md"
        reason.write_text("waiting on dependency\n", encoding="utf-8")
        issue = {
            "number": 12,
            "title": "t",
            "body": "b",
            "state": "OPEN",
            "labels": [{"name": "lane:platform-api"}, {"name": "status:wip"}],
            "comments": [],
            "url": "https://example.test/issues/12",
        }
        fake = FakeGitHub(issue)
        set_command_runners(gh=fake)
        try:
            result = release_issue(
                load_taxonomy(),
                [
                    "--issue",
                    "12",
                    "--mode",
                    "blocked",
                    "--reason-file",
                    "release-blocked.rationale.local.md",
                ],
            )
            self.assertEqual(result["mode"], "blocked")
            names = {label["name"].lower() for label in fake.issue["labels"]}
            self.assertNotIn("status:wip", names)
            self.assertIn("blocked", names)
        finally:
            reason.unlink(missing_ok=True)

    def test_argparse_help_includes_release_mode(self):
        parser = build_parser()
        ns = parser.parse_args(
            ["release", "--issue", "1", "--mode", "abandon", "--reason-file", "x.md"]
        )
        self.assertEqual(ns.command, "release")
        self.assertEqual(ns.mode, "abandon")
        with self.assertRaises(SystemExit):
            parser.parse_args(["release", "--issue", "1", "--reason-file", "x.md"])


if __name__ == "__main__":
    unittest.main()
