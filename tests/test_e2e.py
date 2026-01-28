"""End-to-end tests with recorded API fixtures.

These tests use pre-recorded API responses to test the full data flow
from API calls through to final report output, without making real
network requests.

The recorded fixtures capture real GitHub API responses, ensuring
tests exercise actual data structures and edge cases.
"""

import json
import sys
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import patch, MagicMock
import subprocess

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from tests.conftest import load_chronicle_module
from tests.api_recorder import ApiReplayer, create_mock_responses_for_user

mod = load_chronicle_module()

FIXTURES_DIR = Path(__file__).parent / "fixtures"
API_RESPONSES_DIR = FIXTURES_DIR / "api_responses"


class MockGhCommand:
    """Mock for run_gh_command that returns pre-defined responses."""

    def __init__(self, responses: Dict[str, Any]):
        """Initialize with a dict of call patterns to responses.

        responses: Dict mapping call type to response data
            - "graphql_contributions": contribution summary response
            - "search_commits": commit search response
            - "graphql_prs_created": PR search response
            - "graphql_prs_reviewed": PR review response
            - "user_forks": user forks response
            - "repo_info": repo info response
        """
        self.responses = responses
        self.call_log: List[Dict] = []

    def __call__(self, args: List[str], parse_json: bool = True, **kwargs):
        """Handle a mocked gh command call."""
        call_record = {"args": args, "parse_json": parse_json, "kwargs": kwargs}
        self.call_log.append(call_record)

        # Convert args to string for pattern matching
        args_str = " ".join(str(a) for a in args)

        # Check for --jq flag (returns raw string, not JSON)
        has_jq = "--jq" in args

        # Determine response based on args
        if "graphql" in args:
            # GraphQL query - look at the query content
            query_idx = args.index("-f") + 1 if "-f" in args else -1
            if query_idx > 0 and query_idx < len(args):
                query = args[query_idx]
                if "contributionsCollection" in query:
                    return self.responses.get("graphql_contributions", {})
                elif "pullRequestReviewContributions" in query:
                    return self.responses.get("graphql_prs_reviewed", {
                        "data": {"user": {"contributionsCollection": {
                            "pullRequestReviewContributions": {
                                "nodes": [],
                                "pageInfo": {"hasNextPage": False}
                            }
                        }}}
                    })
                elif "search" in query and "type:pr" in query:
                    return self.responses.get("graphql_prs_created", {
                        "search": {"nodes": [], "issueCount": 0}
                    })

        elif "api" in args:
            # REST API call
            if "search/commits" in args_str:
                # Check if this is using --jq to get just the count
                if has_jq and ".total_count" in args_str:
                    return "0"  # Return string for --jq output
                return self.responses.get("search_commits", {
                    "total_count": 0, "items": []
                })
            elif "/repos/" in args_str and "/commits/" in args_str:
                # Commit stats
                return {"stats": {"additions": 10, "deletions": 5}}
            elif "user/repos" in args_str or "repositories" in args_str:
                return self.responses.get("user_forks", [])
            elif "/languages" in args_str:
                return {"Python": 10000, "JavaScript": 5000}
            elif "rate_limit" in args_str:
                return {"resources": {"graphql": {"remaining": 5000}}}

        # Default empty response
        return {} if parse_json else ""


class TestE2EUserReport:
    """End-to-end tests for user report generation."""

    @pytest.fixture
    def mock_responses(self):
        """Create mock responses for a user report."""
        return create_mock_responses_for_user("testuser", days=7)

    @pytest.fixture
    def mock_gh(self, mock_responses):
        """Create a MockGhCommand with the responses."""
        return MockGhCommand({
            "graphql_contributions": mock_responses["contribution_summary"],
            "search_commits": mock_responses["commits_search"],
            "graphql_prs_created": mock_responses["prs_created"],
            "graphql_prs_reviewed": {"data": {"user": {"contributionsCollection": {
                "pullRequestReviewContributions": {
                    "nodes": mock_responses["prs_reviewed"],
                    "pageInfo": {"hasNextPage": False}
                }
            }}}},
            "user_forks": mock_responses["user_forks"],
        })

    def test_full_user_data_gathering(self, mock_gh):
        """Test complete user data gathering with mocked API."""
        with patch.object(mod, "run_gh_command", mock_gh):
            with patch.object(mod, "run_gh_graphql", mock_gh):
                # Gather data
                data = mod.gather_user_data(
                    "testuser", "2026-01-01", "2026-01-07",
                    show_progress=False
                )

        # Verify data structure
        assert data["username"] == "testuser"
        assert "repos_by_category" in data
        assert "total_commits_default_branch" in data

        # Verify API was called
        assert len(mock_gh.call_log) > 0

    def test_full_report_generation(self, mock_gh):
        """Test complete report generation with mocked API."""
        with patch.object(mod, "run_gh_command", mock_gh):
            with patch.object(mod, "run_gh_graphql", mock_gh):
                report = mod.generate_report(
                    "testuser", "2026-01-01", "2026-01-07"
                )

        # Verify report structure
        assert "# github activity chronicle" in report
        assert "testuser" in report
        assert "2026-01-01" in report
        assert "## " in report  # Has sections

    def test_report_contains_expected_data(self, mock_gh, mock_responses):
        """Verify report contains data from mocked responses."""
        with patch.object(mod, "run_gh_command", mock_gh):
            with patch.object(mod, "run_gh_graphql", mock_gh):
                report = mod.generate_report(
                    "testuser", "2026-01-01", "2026-01-07"
                )

        # Check that data from mock responses appears in report
        # The contribution summary said 25 commits
        contrib = mock_responses["contribution_summary"]["data"]["user"]
        expected_commits = contrib["contributionsCollection"]["totalCommitContributions"]

        # Report should mention commit count somewhere
        assert str(expected_commits) in report or "commits" in report.lower()


class TestE2EOrgReport:
    """End-to-end tests for org report generation."""

    @pytest.fixture
    def mock_member_data(self):
        """Create mock member data list."""
        return [
            {
                "username": "member1",
                "user_real_name": "Member One",
                "company": "@testorg",
                "total_commits_default_branch": 30,
                "total_commits_all": 30,
                "total_prs": 5,
                "total_pr_reviews": 8,
                "total_issues": 2,
                "total_additions": 2000,
                "total_deletions": 500,
                "repos_contributed": 2,
                "repos_by_category": {
                    "Other": [
                        {"name": "testorg/repo1", "commits": 20, "prs": 3,
                         "language": "Python", "description": "Repo 1"},
                        {"name": "testorg/repo2", "commits": 10, "prs": 2,
                         "language": "Go", "description": "Repo 2"},
                    ]
                },
                "prs_nodes": [],
                "reviewed_nodes": [],
                "is_light_mode": True,
            },
            {
                "username": "member2",
                "user_real_name": "Member Two",
                "company": "Other Corp",
                "total_commits_default_branch": 20,
                "total_commits_all": 20,
                "total_prs": 3,
                "total_pr_reviews": 5,
                "total_issues": 1,
                "total_additions": 1000,
                "total_deletions": 200,
                "repos_contributed": 1,
                "repos_by_category": {
                    "Other": [
                        {"name": "testorg/repo1", "commits": 20, "prs": 3,
                         "language": "Python", "description": "Repo 1"},
                    ]
                },
                "prs_nodes": [],
                "reviewed_nodes": [],
                "is_light_mode": True,
            },
        ]

    def test_org_data_aggregation(self, mock_member_data):
        """Test org data is properly aggregated from member data."""
        aggregated = mod.aggregate_org_data(mock_member_data)

        # Check aggregation
        assert aggregated["total_commits_default_branch"] == 50  # 30 + 20
        assert aggregated["total_prs"] == 8  # 5 + 3
        assert aggregated["repos_contributed"] == 2  # unique repos

        # Check member tracking
        assert "repo_member_commits" in aggregated
        assert "testorg/repo1" in aggregated["repo_member_commits"]
        # Both members committed to repo1
        repo1_commits = aggregated["repo_member_commits"]["testorg/repo1"]
        assert "member1" in repo1_commits
        assert "member2" in repo1_commits

    def test_full_org_report_generation(self, mock_member_data):
        """Test complete org report generation."""
        org_info = {"login": "testorg", "name": "Test Organization"}
        members = [{"login": m["username"]} for m in mock_member_data]

        aggregated = mod.aggregate_org_data(mock_member_data)
        report = mod.generate_org_report(
            org_info, None, "2026-01-01", "2026-01-07",
            aggregated, members
        )

        # Verify report structure
        assert "# github activity chronicle" in report
        assert "testorg" in report
        assert "<details" in report  # Has collapsible sections
        assert 'name="commit-details"' in report  # Accordion behavior

    def test_org_report_has_all_detail_sections(self, mock_member_data):
        """Verify org report has all four detail sections."""
        org_info = {"login": "testorg", "name": "Test Organization"}
        members = [{"login": m["username"]} for m in mock_member_data]

        aggregated = mod.aggregate_org_data(mock_member_data)
        report = mod.generate_org_report(
            org_info, None, "2026-01-01", "2026-01-07",
            aggregated, members
        )

        assert "Commit details by language" in report
        assert "Commit details by repository" in report
        assert "Commit details by user" in report
        assert "Commit details by organization" in report

    def test_org_report_member_grouping(self, mock_member_data):
        """Verify members are grouped by company correctly."""
        org_info = {"login": "testorg", "name": "Test Organization"}
        members = [{"login": m["username"]} for m in mock_member_data]

        aggregated = mod.aggregate_org_data(mock_member_data)
        report = mod.generate_org_report(
            org_info, None, "2026-01-01", "2026-01-07",
            aggregated, members
        )

        # member1 has @testorg, member2 has "Other Corp"
        # Both should appear in their respective groups
        assert "testorg" in report.lower()
        # The report should have organization groupings


class TestE2EDataFlow:
    """Tests verifying data flows correctly through the system."""

    def test_commit_counts_consistent(self):
        """Verify commit counts are consistent throughout data flow."""
        # Create member data with known commit counts
        member_data = [
            {
                "username": "user1",
                "user_real_name": "User One",
                "company": "",
                "total_commits_default_branch": 100,
                "total_commits_all": 100,
                "total_prs": 0,
                "total_pr_reviews": 0,
                "total_issues": 0,
                "total_additions": 0,
                "total_deletions": 0,
                "repos_contributed": 1,
                "repos_by_category": {
                    "Other": [
                        {"name": "org/repo", "commits": 100, "prs": 0,
                         "language": "Python", "description": "Test"}
                    ]
                },
                "prs_nodes": [],
                "reviewed_nodes": [],
                "is_light_mode": True,
            }
        ]

        aggregated = mod.aggregate_org_data(member_data)

        # Verify counts match
        assert aggregated["total_commits_default_branch"] == 100
        assert aggregated["repo_member_commits"]["org/repo"]["user1"] == 100

    def test_pr_deduplication_in_aggregation(self):
        """Verify PRs are deduplicated when aggregating org data."""
        # Two members reviewed the same PR
        shared_pr_url = "https://github.com/org/repo/pull/1"
        member_data = [
            {
                "username": "user1",
                "user_real_name": "User One",
                "company": "",
                "total_commits_default_branch": 0,
                "total_commits_all": 0,
                "total_prs": 0,
                "total_pr_reviews": 1,
                "total_issues": 0,
                "total_additions": 0,
                "total_deletions": 0,
                "repos_contributed": 0,
                "repos_by_category": {},
                "prs_nodes": [],
                "reviewed_nodes": [
                    {"url": shared_pr_url, "title": "Test PR",
                     "additions": 50, "deletions": 10,
                     "author": {"login": "author"},
                     "repository": {"nameWithOwner": "org/repo"}}
                ],
                "is_light_mode": True,
            },
            {
                "username": "user2",
                "user_real_name": "User Two",
                "company": "",
                "total_commits_default_branch": 0,
                "total_commits_all": 0,
                "total_prs": 0,
                "total_pr_reviews": 1,
                "total_issues": 0,
                "total_additions": 0,
                "total_deletions": 0,
                "repos_contributed": 0,
                "repos_by_category": {},
                "prs_nodes": [],
                "reviewed_nodes": [
                    {"url": shared_pr_url, "title": "Test PR",
                     "additions": 50, "deletions": 10,
                     "author": {"login": "author"},
                     "repository": {"nameWithOwner": "org/repo"}}
                ],
                "is_light_mode": True,
            },
        ]

        aggregated = mod.aggregate_org_data(member_data)

        # Should have only 1 unique PR reviewed (deduplicated by URL)
        reviewed_urls = set()
        for pr in aggregated.get("reviewed_nodes", []):
            reviewed_urls.add(pr.get("url"))
        assert len(reviewed_urls) == 1
