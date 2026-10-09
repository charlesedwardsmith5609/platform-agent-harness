import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SETUP = ROOT / "setup"
sys.path.insert(0, str(SETUP))

from platform_harness import IssueError, load_taxonomy, set_command_runners
from platform_harness.doctor import run_doctor
from platform_harness.issue_ops import (
    assert_lane_wip_available,
    claim_issue,
    count_lane_wip,
    format_claim_body,
    lane_wip_limit,
)
from platform_harness.pr_draft import build_pr_draft
from platform_harness.sweep import find_stale_claims
from platform_harness.velocity import first_claim_timestamp, velocity_report
from pr_gate import collect_findings

# Reuse claim fake from the primary suite.
from test_repo_issue import FakeGitHub


class WipLimitTests(unittest.TestCase):
    def test_taxonomy_declares_wip_limits(self):
        taxonomy = load_taxonomy()
        self.assertEqual(lane_wip_limit(taxonomy, "lane:observability"), 1)
        self.assertEqual(lane_wip_limit(taxonomy, "lane:foundation"), 2)

    def test_claim_blocked_when_lane_at_limit(self):
        busy = {
            "number": 8,
            "title": "busy",
            "state": "OPEN",
            "labels": [{"name": "lane:compute"}, {"name": "status:wip"}],
            "comments": [],
            "url": "https://example.test/issues/8",
        }
        target = {
            "number": 9,
            "title": "next",
            "state": "OPEN",
            "labels": [{"name": "lane:compute"}],
            "comments": [],
            "url": "https://example.test/issues/9",
        }
        fake = FakeGitHub(target, catalog=[busy, target])
        set_command_runners(gh=fake)
        taxonomy = load_taxonomy()
        self.assertEqual(count_lane_wip("lane:compute"), 1)
        with self.assertRaisesRegex(IssueError, "WIP limit"):
            assert_lane_wip_available(taxonomy, "lane:compute")
        with self.assertRaisesRegex(IssueError, "WIP limit"):
            claim_issue(
                taxonomy,
                [
                    "--issue",
                    "9",
                    "--lane",
                    "lane:compute",
                    "--worker",
                    "alice",
                    "--branch",
                    "issue/9-next",
                ],
            )


class VelocityUnitTests(unittest.TestCase):
    def test_first_claim_timestamp(self):
        claim_id = "11111111-1111-1111-1111-111111111111"
        issue = {
            "comments": [
                {
                    "body": format_claim_body(
                        claim_id=claim_id,
                        lane="lane:ci-cd",
                        worker="a",
                        branch="issue/1-a",
                        stamp="2026-01-02T00:00:00Z",
                    ),
                    "createdAt": "2026-01-02T00:00:00Z",
                }
            ]
        }
        ts = first_claim_timestamp(issue)
        self.assertEqual(ts, datetime(2026, 1, 2, tzinfo=timezone.utc))

    def test_velocity_report_summary_shape(self):
        open_issue = {
            "number": 1,
            "title": "wip",
            "state": "OPEN",
            "labels": [{"name": "lane:ci-cd"}, {"name": "status:wip"}, {"name": "P1"}],
            "comments": [
                {
                    "body": format_claim_body(
                        claim_id="11111111-1111-1111-1111-111111111111",
                        lane="lane:ci-cd",
                        worker="a",
                        branch="issue/1-a",
                        stamp="2026-01-01T00:00:00Z",
                    ),
                    "createdAt": "2026-01-01T00:00:00Z",
                }
            ],
            "createdAt": "2026-01-01T00:00:00Z",
            "url": "https://example.test/issues/1",
        }

        def gh(args: list[str]) -> str:
            if args[:2] == ["issue", "list"]:
                state = args[args.index("--state") + 1]
                if state == "open":
                    return json.dumps([open_issue])
                return json.dumps([])
            if args[:2] == ["issue", "view"]:
                return json.dumps(open_issue)
            if args[:2] == ["pr", "list"]:
                return json.dumps([])
            raise AssertionError(args)

        set_command_runners(gh=gh)
        report = velocity_report(
            days=14, now=datetime(2026, 1, 5, tzinfo=timezone.utc)
        )
        self.assertEqual(report["summary"]["open_wip_count"], 1)
        self.assertEqual(report["summary"]["stale_wip_count"], 1)
        self.assertEqual(len(report["p0_p1_open_aging"]), 1)


class PrDraftTests(unittest.TestCase):
    def test_pr_draft_contains_closes_and_blast_radius(self):
        issue = {
            "number": 42,
            "title": "Add burn rate alert",
            "state": "OPEN",
            "labels": [{"name": "lane:observability"}],
            "comments": [],
            "url": "https://example.test/issues/42",
        }
        set_command_runners(gh=FakeGitHub(issue))
        draft = build_pr_draft(issue=42)
        self.assertIn("Closes #42", draft["body"])
        self.assertIn("## Blast radius", draft["body"])
        self.assertIn("lane:observability", draft["body"])


class SweepTests(unittest.TestCase):
    def test_find_stale_claims(self):
        claim_id = "11111111-1111-1111-1111-111111111111"
        issue = {
            "number": 3,
            "title": "stale",
            "state": "OPEN",
            "labels": [{"name": "lane:cost"}, {"name": "status:wip"}],
            "comments": [
                {
                    "id": 1,
                    "body": format_claim_body(
                        claim_id=claim_id,
                        lane="lane:cost",
                        worker="a",
                        branch="issue/3-a",
                        stamp="2026-01-01T00:00:00Z",
                    ),
                    "createdAt": "2026-01-01T00:00:00Z",
                }
            ],
            "url": "https://example.test/issues/3",
        }
        set_command_runners(gh=FakeGitHub(issue))
        stale = find_stale_claims(
            days=2, now=datetime(2026, 1, 10, tzinfo=timezone.utc)
        )
        self.assertEqual(len(stale), 1)
        self.assertEqual(stale[0]["issue"], 3)


class DoctorScorecardTests(unittest.TestCase):
    def test_self_doctor_has_score(self):
        report = run_doctor(probe_github=False)
        self.assertTrue(report["ok"])
        self.assertEqual(report["mode"], "self")
        self.assertGreaterEqual(report["score"], 80)

    def test_adoption_target_scorecard(self):
        report = run_doctor(probe_github=False, target=ROOT)
        self.assertEqual(report["mode"], "adoption")
        self.assertIn("score", report)
        self.assertTrue(report["ok"])


class PrGateTests(unittest.TestCase):
    def test_missing_closes_and_blast_radius(self):
        findings = collect_findings(
            body="hello",
            title="fix",
            branch="issue/1-x",
            changed_files=["README.md"],
        )
        self.assertEqual(len(findings), 2)

    def test_foundation_requires_signal(self):
        findings = collect_findings(
            body="Closes #1\n\n## Blast radius\nlow\n",
            title="tweak taxonomy",
            branch="issue/1-x",
            changed_files=["setup/project-taxonomy.json"],
        )
        self.assertTrue(any("foundation-path" in item for item in findings))

    def test_foundation_branch_ok(self):
        findings = collect_findings(
            body="Closes #1\n\n## Blast radius\norg-wide\n",
            title="taxonomy",
            branch="foundation/wip-limits",
            changed_files=["setup/project-taxonomy.json"],
        )
        self.assertEqual(findings, [])


if __name__ == "__main__":
    unittest.main()
