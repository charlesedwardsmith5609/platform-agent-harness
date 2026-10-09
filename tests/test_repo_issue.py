import json
import sys
import unittest
from pathlib import Path

SETUP = Path(__file__).resolve().parents[1] / "setup"
sys.path.insert(0, str(SETUP))

from apply_permissions import PLACEHOLDER, command_to_claude, load_source, materialize
from repo_issue import (
    IssueError,
    classification_from_arguments,
    load_taxonomy,
    validate_title,
)


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


class PermissionSourceTests(unittest.TestCase):
    def test_permission_source_is_portable(self):
        document = load_source()
        example_root = Path("E:/example/platform-repo")
        resolved, claude = materialize(example_root, document)
        self.assertNotIn(PLACEHOLDER, json.dumps(resolved))
        self.assertIn(str(example_root), resolved["locations"])
        self.assertIn("Bash(gh issue *)", claude["permissions"]["allow"])
        self.assertEqual(command_to_claude("gh auth status"), "Bash(gh auth status)")
        source_text = (SETUP / "agent-permissions.json").read_text(encoding="utf-8")
        self.assertIn("REPLACE_WITH_YOUR_REPO_GIT_ROOT", source_text)
        self.assertNotIn("nme-mcp", source_text)


if __name__ == "__main__":
    unittest.main()
