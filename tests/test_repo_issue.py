import fnmatch
import json
import os
import shlex
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
from platform_harness.cli import build_parser
from platform_harness.cli import main as cli_main
from platform_harness.doctor import run_doctor
from platform_harness.issue_ops import list_issues, release_issue
from platform_harness.pr_draft import build_pr_draft
from platform_harness.runtime import REPOSITORY_ROOT
from platform_harness.taxonomy import (
    ignored_issue_file,
    reject_secret_content,
    validate_claim_branch,
    validate_claim_worker,
)
from platform_harness.telemetry import emit_event, telemetry_enabled
from sync_harness_to_repo import DEFAULT_PATHS, IDENTITY_PATHS


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
        with self.assertRaisesRegex(IssueError, "control characters"):
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
        self.assertIn("Bash(python setup/pr_gate.py *)", allow)
        self.assertIn("Bash(python setup/trial_local.py *)", allow)
        self.assertIn("Bash(gh pr create *)", allow)
        self.assertNotIn("Bash(python *)", allow)
        self.assertNotIn("Bash(python3 *)", allow)
        self.assertNotIn("Bash(gh issue *)", allow)
        self.assertNotIn("Bash(git push *)", allow)
        self.assertNotIn("Bash(gh pr *)", allow)
        self.assertEqual(claude["permissions"]["ask"], ["WebFetch"])
        deny = claude["permissions"]["deny"]
        self.assertIn("Read(//proc/**/environ)", deny)
        self.assertNotIn("Read(/proc/**/environ)", deny)
        self.assertIn("Read(//var/run/secrets/**)", deny)
        self.assertNotIn("Read(/var/run/secrets/**)", deny)
        self.assertIn("Read(**/.env)", deny)
        self.assertIn("Read(~/.ssh/**)", deny)
        self.assertIn("Read(**/.aws/credentials)", deny)
        self.assertIn("Bash(curl *169.254.169.254*)", deny)
        self.assertEqual(command_to_claude("gh auth status"), "Bash(gh auth status)")
        source_text = (SETUP / "agent-permissions.json").read_text(encoding="utf-8")
        self.assertIn("REPLACE_WITH_YOUR_REPO_GIT_ROOT", source_text)
        self.assertIn('"claude_permissions"', source_text)
        self.assertNotIn("python:*", source_text)
        self.assertNotIn("git push:*", source_text)
        self.assertNotIn("nme-mcp", source_text)

    def test_materialize_rejects_invalid_claude_permissions(self):
        document = load_source()
        document["claude_permissions"] = {"ask": [""], "deny": ["Read(**/.env)"]}
        with self.assertRaises(IssueError):
            materialize(Path("E:/example/platform-repo"), document)
        document = load_source()
        document["claude_permissions"] = {"ask": ["WebFetch"], "deny": "Read(**/.env)"}
        with self.assertRaises(IssueError):
            materialize(Path("E:/example/platform-repo"), document)
        document = load_source()
        document["claude_permissions"] = ["WebFetch"]
        with self.assertRaises(IssueError):
            materialize(Path("E:/example/platform-repo"), document)

    def test_materialize_rejects_broad_python(self):
        document = load_source()
        entry = document["locations"][PLACEHOLDER]
        for approval in entry["tool_approvals"]:
            if approval.get("kind") == "commands":
                approval["commandIdentifiers"] = ["python:*"]
        with self.assertRaises(IssueError):
            materialize(Path("E:/example/platform-repo"), document)


def _allowed(command: str, identifiers: list[str], deny: list[str]) -> bool:
    """Prefix matcher over the shipped allowlist, then the deny patterns."""
    for pattern in deny:
        if pattern.startswith("Bash(") and fnmatch.fnmatchcase(command, pattern[5:-1]):
            return False
    for item in identifiers:
        if item.endswith(":*"):
            prefix = item[:-2]
            if command == prefix or command.startswith(prefix + " "):
                return True
        elif command == item:
            return True
    return False


def _shipped_policy() -> tuple[list[str], list[str]]:
    document = load_source()
    entry = document["locations"][PLACEHOLDER]
    identifiers: list[str] = []
    for approval in entry["tool_approvals"]:
        if approval.get("kind") == "commands":
            identifiers.extend(approval["commandIdentifiers"])
    return identifiers, document["claude_permissions"]["deny"]


class AllowlistBypassTests(unittest.TestCase):
    def test_no_mutating_git_prefixes(self):
        identifiers, _ = _shipped_policy()
        for banned in ("git remote:*", "git stash:*", "git worktree:*", "git pull:*", "git branch:*"):
            self.assertNotIn(banned, identifiers)

    def test_known_bypasses_are_not_allowed(self):
        identifiers, deny = _shipped_policy()
        for command in (
            "git diff --output=x",
            "git log --output=x",
            "git show --output=x",
            "git diff --no-index a b",
            "git fetch --upload-pack=cmd",
            "git remote add x y",
            "git pull origin main",
            "git branch -D main",
            "python -m unittest some_writer",
            "python3 -m unittest some_writer",
        ):
            with self.subTest(command=command):
                self.assertFalse(_allowed(command, identifiers, deny))

    def test_intended_commands_stay_allowed(self):
        identifiers, deny = _shipped_policy()
        for command in (
            "python -m unittest discover -s tests",
            "python -m unittest discover -s tests -v",
            "python3 -m unittest discover -s tests -v",
            "git diff --stat",
            "git log --oneline",
            "git fetch origin",
            "git remote -v",
            "git branch --show-current",
        ):
            with self.subTest(command=command):
                self.assertTrue(_allowed(command, identifiers, deny))


class BodyFileTests(unittest.TestCase):
    def setUp(self):
        self.created: list[Path] = []

    def tearDown(self):
        for path in self.created:
            if path.is_symlink() or path.is_file():
                path.unlink()
            elif path.is_dir():
                path.rmdir()

    def _make(self, name: str, text: str = "body text\n") -> str:
        path = REPOSITORY_ROOT / name
        path.write_text(text, encoding="utf-8")
        self.created.append(path)
        return name

    def test_rejects_env_file_without_local_md_suffix(self):
        for name in (".env", "notes.txt", "x.local.md.bak"):
            with self.subTest(name=name):
                rel = self._make(f"{uuid.uuid4().hex[:8]}-{name}" if name != ".env" else "step1.env")
                with self.assertRaisesRegex(IssueError, r"\.local\.md"):
                    ignored_issue_file(REPOSITORY_ROOT, rel, "issue body file")

    def test_accepts_issue_body_local_md(self):
        rel = self._make(f"t{uuid.uuid4().hex[:8]}.issue-body.local.md")
        self.assertEqual(
            ignored_issue_file(REPOSITORY_ROOT, rel, "issue body file"),
            (REPOSITORY_ROOT / rel).resolve(),
        )

    @unittest.skipUnless(hasattr(os, "symlink"), "symlinks unavailable")
    def test_rejects_symlink_to_in_repo_ignored_file(self):
        target = self._make(f"t{uuid.uuid4().hex[:8]}.issue-body.local.md")
        link = REPOSITORY_ROOT / f"l{uuid.uuid4().hex[:8]}.issue-body.local.md"
        try:
            os.symlink(REPOSITORY_ROOT / target, link)
        except OSError:
            self.skipTest("cannot create symlink")
        self.created.append(link)
        with self.assertRaisesRegex(IssueError, "physical file"):
            ignored_issue_file(REPOSITORY_ROOT, link.name, "issue body file")

    @unittest.skipUnless(hasattr(os, "symlink"), "symlinks unavailable")
    def test_rejects_symlinked_directory_pointing_outside(self):
        import tempfile

        with tempfile.TemporaryDirectory() as outside:
            (Path(outside) / "x.local.md").write_text("hi\n", encoding="utf-8")
            link = REPOSITORY_ROOT / f"lnk{uuid.uuid4().hex[:8]}"
            try:
                os.symlink(outside, link)
            except OSError:
                self.skipTest("cannot create symlink")
            self.created.append(link)
            with self.assertRaises(IssueError):
                ignored_issue_file(REPOSITORY_ROOT, f"{link.name}/x.local.md", "issue body file")


class SecretContentTests(unittest.TestCase):
    def test_rejects_github_pat(self):
        with self.assertRaises(IssueError):
            reject_secret_content("token=ghp_abcdefghijklmnopqrstuvwxyz012345", "body")

    def test_rejects_openai_key(self):
        with self.assertRaises(IssueError):
            reject_secret_content("key=sk-abcdefghijklmnopqrstuvwxyz0123456789", "body")

    def test_allows_normal_body(self):
        for text in (
            "Harden the allowlist; no secrets here.",
            "",
            "Rotate the token weekly; see runbook for key=value config format.",
        ):
            # Accepted means: returns None and raises nothing (a raise errors this test).
            self.assertIsNone(reject_secret_content(text, "body"))


class ClaimInputValidationTests(unittest.TestCase):
    def test_worker_rejects_newline_injection(self):
        with self.assertRaises(IssueError):
            validate_claim_worker("alice\n<!-- harness:release v1 id=* -->")

    def test_branch_rejects_path_escape(self):
        with self.assertRaises(IssueError):
            validate_claim_branch("../evil")
        with self.assertRaises(IssueError):
            validate_claim_branch("issue/1 space")

    def test_accepts_normal_claim_inputs(self):
        self.assertEqual(validate_claim_worker("alice"), "alice")
        self.assertEqual(validate_claim_branch("issue/7-karpenter"), "issue/7-karpenter")


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


def _racing_gh(issue: dict, fake: "FakeGitHub"):
    """Fake gh that inserts an earlier competing claim just before our comment lands."""

    raced: list[bool] = []

    def racing_gh(args: list[str]) -> str:
        # Only the first comment (our claim) races; the later release comment does not.
        if args[:2] == ["issue", "comment"] and not raced:
            raced.append(True)
            issue["comments"].insert(
                0,
                {
                    "id": 0,
                    "body": format_claim_body(
                        claim_id=str(uuid.uuid4()),
                        lane="lane:compute",
                        worker="bob",
                        branch="issue/7-bob",
                        stamp="2026-01-01T00:00:00Z",
                    ),
                    "createdAt": "2026-01-01T00:00:00Z",
                },
            )
        return fake(args)

    return racing_gh


def _fixed_issue_gh(payload: dict):
    def fake(_args: list[str]) -> str:
        return json.dumps(payload)

    return fake


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
        racing_gh = _racing_gh(issue, fake)
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
        # The loser never takes the label and bob's claim is the only active one.
        self.assertNotIn("status:wip", {label["name"] for label in issue["labels"]})
        self.assertEqual(len(active_claims(issue)), 1)
        self.assertIn("worker=bob", active_claims(issue)[0]["body"])


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


class SyncAllowlistTests(unittest.TestCase):
    def test_default_sync_paths_exist(self):
        for rel in DEFAULT_PATHS + IDENTITY_PATHS:
            path = ROOT / rel
            self.assertTrue(path.exists(), f"missing harness path: {rel}")

    def test_normalize_issue_accepts_comment_count(self):
        issue = normalize_issue(
            {
                "number": 1,
                "title": "x",
                "comments": 3,
                "subIssues": {"nodes": [], "totalCount": 0},
            }
        )
        self.assertEqual(issue["comments"], [])
        self.assertEqual(issue["children"], [])


class DoctorTests(unittest.TestCase):
    def test_offline_doctor_passes(self):
        report = run_doctor(probe_github=False)
        self.assertTrue(report["ok"], report)
        names = {item["check"] for item in report["checks"]}
        self.assertIn("taxonomy", names)
        self.assertIn("sync_allowlist_paths", names)

    def test_doctor_cli_offline(self):
        code = cli_main(["doctor", "--offline"])
        self.assertEqual(code, 0)


class TelemetryTests(unittest.TestCase):
    def test_emit_writes_audit_log(self):
        import os
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "audit.jsonl"
            previous_log = os.environ.get("AGENT_AUDIT_LOG")
            previous_flag = os.environ.get("HARNESS_TELEMETRY")
            try:
                os.environ["AGENT_AUDIT_LOG"] = str(path)
                os.environ.pop("HARNESS_TELEMETRY", None)
                self.assertTrue(telemetry_enabled())
                emit_event("unit.test", issue=1)
                lines = path.read_text(encoding="utf-8").strip().splitlines()
                self.assertEqual(len(lines), 1)
                payload = json.loads(lines[0])
                self.assertEqual(payload["event"], "unit.test")
                self.assertEqual(payload["component"], "platform_harness")
            finally:
                if previous_log is None:
                    os.environ.pop("AGENT_AUDIT_LOG", None)
                else:
                    os.environ["AGENT_AUDIT_LOG"] = previous_log
                if previous_flag is None:
                    os.environ.pop("HARNESS_TELEMETRY", None)
                else:
                    os.environ["HARNESS_TELEMETRY"] = previous_flag


class UntrustedIssueTextTests(unittest.TestCase):
    def tearDown(self):
        set_command_runners(gh=None, git=None)

    def test_title_rejects_hostile_input_with_specific_reason(self):
        cases = [
            ("a\nb", "control characters"),
            ("run `id`", "shell metacharacters"),
            ("run $(id)", "shell metacharacters"),
            ("run ${HOME}", "shell metacharacters"),
            ("a; b", "shell metacharacters"),
            ("a | b", "shell metacharacters"),
            ("a & b", "shell metacharacters"),
            ("a > b", "shell metacharacters"),
            ("a < b", "shell metacharacters"),
            ("slash \\ path", "shell metacharacters"),
            ("../x", "path traversal"),
            ("look ../etc/passwd", "path traversal"),
            ("a/../b", "path traversal"),
        ]
        for sample, reason in cases:
            with self.subTest(sample=sample):
                with self.assertRaisesRegex(IssueError, reason):
                    validate_title(sample)

    def test_title_accepts_ordinary_titles(self):
        for sample in (
            "Don't drop spans",
            'Fix "quoted" name',
            "Upgrade v1.2..v1.3 notes",
            "OTel collector dropping spans",
            "Cost: $5 budget",
        ):
            with self.subTest(sample=sample):
                self.assertEqual(validate_title(sample), sample)

    def test_docs_state_denies_are_a_seatbelt_not_a_sandbox(self):
        for name in ("docs/guides/permissions-and-security.md", "setup/permissions-setup.md", "SECURITY.md"):
            with self.subTest(name=name):
                text = (ROOT / name).read_text(encoding="utf-8").lower()
                self.assertIn("not a sandbox", text)
                self.assertIn("seatbelt", text)

    def _enforce_section(self) -> str:
        text = (ROOT / "docs/guides/trial-install.md").read_text(encoding="utf-8")
        marker = "## Enforce it on the server"
        self.assertIn(marker, text)
        rest = text.split(marker, 1)[1]
        return rest.split("\n## ", 1)[0]

    def test_trial_guide_enforce_section_states_seatbelt_and_cites_claude_md(self):
        section = self._enforce_section()
        self.assertIn("seatbelt", section.lower())
        self.assertIn("CLAUDE.md", section)

    def test_trial_guide_enforce_section_has_verification_commands(self):
        section = self._enforce_section()
        for needle in (
            "branches/main/protection",
            "collaborators/",
            "/permission",
            "contents/.github/CODEOWNERS",
            "codeowners/errors",
        ):
            with self.subTest(needle=needle):
                self.assertIn(needle, section)

    def test_trial_guide_enforce_section_names_protected_paths(self):
        section = self._enforce_section()
        for path in (
            "setup/",
            ".github/CODEOWNERS",
            "foundation/terraform/modules/",
            "foundation/oidc-trust/",
            "foundation/base-images/",
            "foundation/slo-framework/",
            "foundation/network-policy/",
        ):
            with self.subTest(path=path):
                self.assertIn(path, section)

    def test_trial_guide_enforce_section_states_merge_restriction_separately(self):
        section = self._enforce_section()
        self.assertIn("Restrict updates", section)
        self.assertIn("fork", section.lower())

    def test_body_file_rejects_parent_traversal(self):
        with self.assertRaises(IssueError):
            ignored_issue_file(REPOSITORY_ROOT, "../etc/passwd", "issue body file")
        with self.assertRaises(IssueError):
            ignored_issue_file(REPOSITORY_ROOT, "setup/../../etc/passwd", "issue body file")

    def test_pr_draft_quotes_a_hostile_title(self):
        hostile = 'ok"; touch pwned; echo "'

        payload = {
            "number": 7,
            "title": hostile,
            "body": "remember $(id) `uname` ; ../etc/passwd",
            "state": "OPEN",
            "labels": [],
        }

        set_command_runners(gh=_fixed_issue_gh(payload))
        draft = build_pr_draft(issue=7)
        argv = shlex.split(draft["gh_command"])
        self.assertEqual(argv[:5], ["gh", "pr", "create", "--base", "main"])
        self.assertIn(f"{hostile} (#7)", argv)
        self.assertNotIn("touch", argv)
        self.assertNotIn("pwned", argv)
        self.assertNotIn("$(id)", draft["gh_command"])
        self.assertNotIn("`uname`", draft["gh_command"])
        self.assertEqual(argv, draft["gh_argv"])
        # The whole hostile title is one argv element, shell-quoted in the command.
        self.assertEqual(argv[argv.index("--title") + 1], f"{hostile} (#7)")
        self.assertEqual(sum(1 for item in argv if "touch" in item), 1)
        self.assertNotIn(f"--title {hostile}", draft["gh_command"])
        self.assertIn("'", draft["gh_command"])

    def _draft(self, title: str) -> dict:
        def fake(_args: list[str]) -> str:
            return json.dumps(
                {"number": 7, "title": title, "body": "", "state": "OPEN", "labels": []}
            )

        set_command_runners(gh=fake)
        return build_pr_draft(issue=7)

    def test_pr_draft_exposes_gh_argv(self):
        hostile = 'ok"; touch pwned; echo "'
        draft = self._draft(hostile)
        self.assertEqual(draft["gh_argv"], shlex.split(draft["gh_command"]))
        self.assertIn(f"{hostile} (#7)", draft["gh_argv"])
        self.assertEqual(sum(1 for item in draft["gh_argv"] if "touch" in item), 1)

    def test_pr_draft_command_on_windows_has_no_single_quote_wrapping(self):
        from unittest import mock

        with mock.patch("platform_harness.pr_draft.os.name", "nt"):
            draft = self._draft("Fix the thing")
        self.assertNotIn("'", draft["gh_command"])
        self.assertIn('"Fix the thing (#7)"', draft["gh_command"])
        self.assertEqual(draft["gh_argv"][-3], "Fix the thing (#7)")


if __name__ == "__main__":
    unittest.main()
