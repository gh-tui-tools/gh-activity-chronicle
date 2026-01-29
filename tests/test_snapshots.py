"""Snapshot tests comparing full output against golden files.

These tests generate complete reports and compare them against known-good
baseline files. Any difference indicates a potential regression.

To update golden files after intentional changes:
    pytest tests/test_snapshots.py --update-golden

Or manually:
    python -c "from tests.test_snapshots import update_golden_files; \
update_golden_files()"
"""

import difflib
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from tests.conftest import load_chronicle_module  # noqa: E402

# Load the module
mod = load_chronicle_module()

FIXTURES_DIR = Path(__file__).parent / "fixtures"
GOLDEN_DIR = FIXTURES_DIR / "golden"


def get_comprehensive_user_data():
    """Create comprehensive mock data for user report snapshot."""
    return {
        "username": "testuser",
        "user_real_name": "Test User",
        "company": "@testorg",
        "total_commits_default_branch": 85,
        "total_commits_all": 120,
        "total_prs": 12,
        "total_pr_reviews": 25,
        "total_issues": 5,
        "total_additions": 8500,
        "total_deletions": 2100,
        "test_commits": 8,
        "repos_contributed": 5,
        "reviews_received": 15,
        "pr_comments_received": 8,
        "lines_reviewed": 3200,
        "review_comments": 12,
        "repos_by_category": {
            "Web standards and specifications": [
                {
                    "name": "w3c/csswg-drafts",
                    "commits": 45,
                    "prs": 5,
                    "language": "CSS",
                    "description": "CSS Working Group Editor Drafts",
                },
                {
                    "name": "whatwg/html",
                    "commits": 20,
                    "prs": 3,
                    "language": "HTML",
                    "description": "HTML Standard",
                },
            ],
            "Browser engines": [
                {
                    "name": "nicehero/nicejson",
                    "commits": 15,
                    "prs": 2,
                    "language": "C++",
                    "description": "A fast JSON parser",
                },
            ],
            "Other": [
                {
                    "name": "testuser/my-project",
                    "commits": 40,
                    "prs": 2,
                    "language": "Python",
                    "description": "Personal project",
                },
            ],
        },
        "repo_line_stats": {
            "w3c/csswg-drafts": {"additions": 4000, "deletions": 1000},
            "whatwg/html": {"additions": 1500, "deletions": 400},
            "nicehero/nicejson": {"additions": 2000, "deletions": 500},
            "testuser/my-project": {"additions": 1000, "deletions": 200},
        },
        "repo_languages": {
            "w3c/csswg-drafts": "CSS",
            "whatwg/html": "HTML",
            "nicehero/nicejson": "C++",
            "testuser/my-project": "Python",
        },
        "prs_nodes": [
            {
                "title": "Add CSS Grid gap shorthand",
                "url": "https://github.com/w3c/csswg-drafts/pull/100",
                "state": "MERGED",
                "merged": True,
                "additions": 250,
                "deletions": 50,
                "repository": {
                    "nameWithOwner": "w3c/csswg-drafts",
                    "primaryLanguage": {"name": "CSS"},
                },
            },
            {
                "title": "Fix HTML parser edge case",
                "url": "https://github.com/whatwg/html/pull/50",
                "state": "MERGED",
                "merged": True,
                "additions": 80,
                "deletions": 20,
                "repository": {
                    "nameWithOwner": "whatwg/html",
                    "primaryLanguage": {"name": "HTML"},
                },
            },
            {
                "title": "Add JSON5 support",
                "url": "https://github.com/nicehero/nicejson/pull/10",
                "state": "OPEN",
                "merged": False,
                "additions": 500,
                "deletions": 100,
                "repository": {
                    "nameWithOwner": "nicehero/nicejson",
                    "primaryLanguage": {"name": "C++"},
                },
            },
        ],
        "reviewed_nodes": [
            {
                "title": "Update Flexbox algorithm",
                "url": "https://github.com/w3c/csswg-drafts/pull/101",
                "additions": 300,
                "deletions": 80,
                "author": {"login": "otheruser"},
                "repository": {"nameWithOwner": "w3c/csswg-drafts"},
            },
            {
                "title": "Add new element",
                "url": "https://github.com/whatwg/html/pull/51",
                "additions": 150,
                "deletions": 20,
                "author": {"login": "anotheruser"},
                "repository": {"nameWithOwner": "whatwg/html"},
            },
        ],
    }


def get_comprehensive_org_data():
    """Create comprehensive mock data for org report snapshot."""
    return {
        "total_commits_default_branch": 450,
        "total_commits_all": 450,
        "total_prs": 65,
        "total_pr_reviews": 120,
        "total_issues": 25,
        "repos_contributed": 8,
        "total_additions": 35000,
        "total_deletions": 8000,
        "test_commits": 30,
        "reviews_received": 0,
        "pr_comments_received": 0,
        "lines_reviewed": 0,
        "review_comments": 0,
        "repos_by_category": {
            "Web standards and specifications": [
                {
                    "name": "w3c/csswg-drafts",
                    "commits": 200,
                    "prs": 30,
                    "language": "CSS",
                    "description": "CSS Working Group Editor Drafts",
                },
                {
                    "name": "whatwg/html",
                    "commits": 100,
                    "prs": 15,
                    "language": "HTML",
                    "description": "HTML Standard",
                },
            ],
            "Accessibility (WAI)": [
                {
                    "name": "w3c/wai-aria",
                    "commits": 80,
                    "prs": 10,
                    "language": "HTML",
                    "description": "WAI-ARIA specification",
                },
            ],
            "Other": [
                {
                    "name": "user/misc-project",
                    "commits": 70,
                    "prs": 10,
                    "language": "JavaScript",
                    "description": "Miscellaneous project",
                },
            ],
        },
        "repo_line_stats": {},
        "repo_languages": {
            "w3c/csswg-drafts": "CSS",
            "whatwg/html": "HTML",
            "w3c/wai-aria": "HTML",
            "user/misc-project": "JavaScript",
        },
        "repo_member_commits": {
            "w3c/csswg-drafts": {"alice": 120, "bob": 80},
            "whatwg/html": {"alice": 60, "charlie": 40},
            "w3c/wai-aria": {"diana": 50, "bob": 30},
            "user/misc-project": {"charlie": 40, "alice": 30},
        },
        "lang_member_commits": {
            "CSS": {"alice": 120, "bob": 80},
            "HTML": {"alice": 60, "charlie": 40, "diana": 50, "bob": 30},
            "JavaScript": {"charlie": 40, "alice": 30},
        },
        "member_real_names": {
            "alice": "Alice Smith",
            "bob": "Bob Jones",
            "charlie": "Charlie Brown",
            "diana": "Diana Prince",
        },
        "member_companies": {
            "alice": "@w3c",
            "bob": "@google",
            "charlie": "@w3c @mozilla",
            "diana": "Amazon Web Services",
        },
        "prs_nodes": [
            {
                "title": "Major CSS update",
                "url": "https://github.com/w3c/csswg-drafts/pull/200",
                "state": "MERGED",
                "merged": True,
                "additions": 500,
                "deletions": 100,
                "repository": {
                    "nameWithOwner": "w3c/csswg-drafts",
                    "primaryLanguage": {"name": "CSS"},
                },
            },
        ],
        "reviewed_nodes": [
            {
                "title": "HTML improvement",
                "url": "https://github.com/whatwg/html/pull/100",
                "additions": 200,
                "deletions": 50,
                "author": {"login": "external"},
                "repository": {"nameWithOwner": "whatwg/html"},
            },
        ],
        "is_light_mode": True,
    }


def normalize_report(report: str) -> str:
    """Normalize a report for comparison.

    Removes/normalizes things that change between runs:
    - Generation timestamps
    - Trailing whitespace
    """
    lines = []
    for line in report.split("\n"):
        # Skip generation timestamp line
        if line.startswith("*Report generated on"):
            lines.append("*Report generated on [TIMESTAMP]*")
        else:
            lines.append(line.rstrip())

    # Remove trailing empty lines
    while lines and not lines[-1]:
        lines.pop()

    return "\n".join(lines)


def diff_reports(expected: str, actual: str) -> str:
    """Generate a unified diff between expected and actual reports."""
    expected_lines = expected.split("\n")
    actual_lines = actual.split("\n")

    diff = difflib.unified_diff(
        expected_lines,
        actual_lines,
        fromfile="expected (golden)",
        tofile="actual",
        lineterm="",
    )
    return "\n".join(diff)


class TestUserReportSnapshot:
    """Snapshot tests for user report output."""

    @pytest.fixture
    def user_report(self):
        """Generate a user report with mock data."""
        mock_data = get_comprehensive_user_data()
        with patch.object(mod, "gather_user_data", return_value=mock_data):
            return mod.generate_report("testuser", "2026-01-01", "2026-01-31")

    def test_user_report_matches_golden(self, user_report, request):
        """Compare user report against golden file."""
        golden_path = GOLDEN_DIR / "user_report.md"

        # Handle --update-golden flag
        if request.config.getoption("--update-golden", default=False):
            golden_path.parent.mkdir(parents=True, exist_ok=True)
            golden_path.write_text(
                normalize_report(user_report), encoding="utf-8"
            )
            pytest.skip("Golden file updated")

        if not golden_path.exists():
            pytest.skip(
                f"Golden file not found: {golden_path}. "
                "Run with --update-golden to create it."
            )

        expected = golden_path.read_text(encoding="utf-8")
        actual = normalize_report(user_report)

        if expected != actual:
            diff = diff_reports(expected, actual)
            pytest.fail(
                f"User report does not match golden file.\n\n"
                f"Diff:\n{diff}\n\n"
                f"Run with --update-golden to update the golden file "
                f"if this change is intentional."
            )


class TestOrgReportSnapshot:
    """Snapshot tests for org report output."""

    @pytest.fixture
    def org_report(self):
        """Generate an org report with mock data."""
        org_info = {"login": "w3c", "name": "World Wide Web Consortium"}
        members = [
            {"login": "alice"},
            {"login": "bob"},
            {"login": "charlie"},
            {"login": "diana"},
        ]
        mock_data = get_comprehensive_org_data()
        return mod.generate_org_report(
            org_info, None, "2026-01-01", "2026-01-31", mock_data, members
        )

    def test_org_report_matches_golden(self, org_report, request):
        """Compare org report against golden file."""
        golden_path = GOLDEN_DIR / "org_report.md"

        # Handle --update-golden flag
        if request.config.getoption("--update-golden", default=False):
            golden_path.parent.mkdir(parents=True, exist_ok=True)
            golden_path.write_text(
                normalize_report(org_report), encoding="utf-8"
            )
            pytest.skip("Golden file updated")

        if not golden_path.exists():
            pytest.skip(
                f"Golden file not found: {golden_path}. "
                "Run with --update-golden to create it."
            )

        expected = golden_path.read_text(encoding="utf-8")
        actual = normalize_report(org_report)

        if expected != actual:
            diff = diff_reports(expected, actual)
            pytest.fail(
                f"Org report does not match golden file.\n\n"
                f"Diff:\n{diff}\n\n"
                f"Run with --update-golden to update the golden file "
                f"if this change is intentional."
            )


def update_golden_files():
    """Utility function to update golden files manually."""
    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)

    # Generate user report
    mock_data = get_comprehensive_user_data()
    with patch.object(mod, "gather_user_data", return_value=mock_data):
        user_report = mod.generate_report(
            "testuser", "2026-01-01", "2026-01-31"
        )
    (GOLDEN_DIR / "user_report.md").write_text(
        normalize_report(user_report), encoding="utf-8"
    )
    print(f"Updated {GOLDEN_DIR / 'user_report.md'}")

    # Generate org report
    org_info = {"login": "w3c", "name": "World Wide Web Consortium"}
    members = [
        {"login": "alice"},
        {"login": "bob"},
        {"login": "charlie"},
        {"login": "diana"},
    ]
    mock_data = get_comprehensive_org_data()
    org_report = mod.generate_org_report(
        org_info, None, "2026-01-01", "2026-01-31", mock_data, members
    )
    (GOLDEN_DIR / "org_report.md").write_text(
        normalize_report(org_report), encoding="utf-8"
    )
    print(f"Updated {GOLDEN_DIR / 'org_report.md'}")


def pytest_addoption(parser):
    """Add --update-golden command line option."""
    try:
        parser.addoption(
            "--update-golden",
            action="store_true",
            default=False,
            help="Update golden files instead of comparing",
        )
    except ValueError:
        # Option already added (e.g., by conftest)
        pass


# Allow running as script to update golden files
if __name__ == "__main__":
    update_golden_files()
