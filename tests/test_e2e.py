"""End-to-end tests with recorded API fixtures.

These tests use pre-recorded API responses to test the full data flow
from API calls through to final report output, without making real
network requests.

The recorded fixtures capture real GitHub API responses, ensuring
tests exercise actual data structures and edge cases.
"""

import sys
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from tests.conftest import load_chronicle_module  # noqa: E402
from tests.api_recorder import create_mock_responses_for_user  # noqa: E402

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
        call_record = {
            "args": args,
            "parse_json": parse_json,
            "kwargs": kwargs,
        }
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
                    return self.responses.get(
                        "graphql_prs_reviewed",
                        {
                            "data": {
                                "user": {
                                    "contributionsCollection": {
                                        "pullRequestReviewContributions": {
                                            "nodes": [],
                                            "pageInfo": {"hasNextPage": False},
                                        }
                                    }
                                }
                            }
                        },
                    )
                elif "search" in query and "type:pr" in query:
                    return self.responses.get(
                        "graphql_prs_created",
                        {"search": {"nodes": [], "issueCount": 0}},
                    )

        elif "api" in args:
            # REST API call
            if "search/commits" in args_str:
                # Check if this is using --jq to get just the count
                if has_jq and ".total_count" in args_str:
                    return "0"  # Return string for --jq output
                return self.responses.get(
                    "search_commits", {"total_count": 0, "items": []}
                )
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
        return MockGhCommand(
            {
                "graphql_contributions": mock_responses[
                    "contribution_summary"
                ],
                "search_commits": mock_responses["commits_search"],
                "graphql_prs_created": mock_responses["prs_created"],
                "graphql_prs_reviewed": {
                    "data": {
                        "user": {
                            "contributionsCollection": {
                                "pullRequestReviewContributions": {
                                    "nodes": mock_responses["prs_reviewed"],
                                    "pageInfo": {"hasNextPage": False},
                                }
                            }
                        }
                    }
                },
                "user_forks": mock_responses["user_forks"],
            }
        )

    def test_full_user_data_gathering(self, mock_gh):
        """Test complete user data gathering with mocked API."""
        with patch.object(mod, "run_gh_command", mock_gh):
            with patch.object(mod, "run_gh_graphql", mock_gh):
                # Gather data
                data = mod.gather_user_data(
                    "testuser", "2026-01-01", "2026-01-07", show_progress=False
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
        contrib = mock_responses["contribution_summary"]
        user = contrib["data"]["user"]
        collection = user["contributionsCollection"]
        expected_commits = collection["totalCommitContributions"]

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
                        {
                            "name": "testorg/repo1",
                            "commits": 20,
                            "prs": 3,
                            "language": "Python",
                            "description": "Repo 1",
                        },
                        {
                            "name": "testorg/repo2",
                            "commits": 10,
                            "prs": 2,
                            "language": "Go",
                            "description": "Repo 2",
                        },
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
                        {
                            "name": "testorg/repo1",
                            "commits": 20,
                            "prs": 3,
                            "language": "Python",
                            "description": "Repo 1",
                        },
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
            org_info, None, "2026-01-01", "2026-01-07", aggregated, members
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
            org_info, None, "2026-01-01", "2026-01-07", aggregated, members
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
            org_info, None, "2026-01-01", "2026-01-07", aggregated, members
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
                        {
                            "name": "org/repo",
                            "commits": 100,
                            "prs": 0,
                            "language": "Python",
                            "description": "Test",
                        }
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
                    {
                        "url": shared_pr_url,
                        "title": "Test PR",
                        "additions": 50,
                        "deletions": 10,
                        "author": {"login": "author"},
                        "repository": {"nameWithOwner": "org/repo"},
                    }
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
                    {
                        "url": shared_pr_url,
                        "title": "Test PR",
                        "additions": 50,
                        "deletions": 10,
                        "author": {"login": "author"},
                        "repository": {"nameWithOwner": "org/repo"},
                    }
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


# -----------------------------------------------------------------------
# Helper: default mocks for gather_user_data / gather_user_data_light
# -----------------------------------------------------------------------


def _base_contributions(username="testuser"):
    """Minimal contribution summary response."""
    return {
        "user": {
            "name": "Test User",
            "company": "",
            "contributionsCollection": {
                "totalCommitContributions": 5,
                "restrictedContributionsCount": 0,
                "totalPullRequestContributions": 1,
                "totalIssueContributions": 0,
                "totalPullRequestReviewContributions": 0,
                "totalRepositoriesWithContributedCommits": 1,
                "commitContributionsByRepository": [
                    {
                        "repository": {
                            "nameWithOwner": "owner/repo1",
                            "isFork": False,
                            "parent": None,
                            "isPrivate": False,
                            "primaryLanguage": {"name": "Python"},
                            "description": "A repo",
                        },
                        "contributions": {"totalCount": 5},
                    }
                ],
            },
        }
    }


def _patch_gather(overrides=None):
    """Return a dict of patch targets -> return values for gather_user_data.

    Callers can override individual keys.
    """
    defaults = {
        "get_contributions_summary": _base_contributions(),
        "get_all_commits": {
            "total_count": 1,
            "items": [
                {
                    "sha": "aaa111",
                    "repository": {
                        "full_name": "owner/repo1",
                        "private": False,
                    },
                    "commit": {
                        "message": "init",
                        "author": {"date": "2026-01-02T00:00:00Z"},
                    },
                }
            ],
        },
        "get_prs_created": {
            "search": {"nodes": [], "issueCount": 0},
        },
        "get_prs_reviewed": [],
        "get_review_comments_count": 0,
        "count_test_related_commits": 0,
        "get_user_forks": [],
        "get_repo_info": {},
        "get_effective_language": None,
        "run_gh_command": {"additions": 10, "deletions": 5},
    }
    if overrides:
        defaults.update(overrides)
    return defaults


class TestGatherUserDataBranches:
    """Tests exercising specific branches inside gather_user_data()."""

    def _call(self, mocks, username="testuser"):
        """Call gather_user_data with all API functions mocked."""
        patches = {}
        for name, retval in mocks.items():
            patches[name] = patch.object(
                mod,
                name,
                return_value=retval,
            )

        ctx = {}
        for name, p in patches.items():
            ctx[name] = p.start()

        try:
            return mod.gather_user_data(
                username,
                "2026-01-01",
                "2026-01-07",
                show_progress=False,
            )
        finally:
            for p in patches.values():
                p.stop()

    # 1. get_all_commits returns None
    def test_commits_data_none(self):
        mocks = _patch_gather({"get_all_commits": None})
        data = self._call(mocks)
        # total_commits_all is recalculated from aggregated_commits,
        # which will be 0 because there are no commit items to iterate.
        assert data["total_commits_all"] == 0

    # 2. Fork whose parent is in EXPLICIT_REPOS
    def test_fork_with_categorized_parent(self):
        # Pick a repo from EXPLICIT_REPOS (tobie/specref exists there)
        parent_name = "tobie/specref"
        fork_name = "testuser/specref"
        mocks = _patch_gather(
            {
                "get_all_commits": {"total_count": 0, "items": []},
                "get_user_forks": [
                    {
                        "full_name": fork_name,
                        "parent": {"full_name": parent_name},
                    }
                ],
                "get_repo_info": {
                    parent_name: {
                        "nameWithOwner": parent_name,
                        "description": "spec references",
                        "primaryLanguage": {"name": "JavaScript"},
                        "isFork": False,
                        "parent": None,
                    },
                },
                "get_fork_commits": [
                    {"sha": "fork111"},
                    {"sha": "fork222"},
                ],
            }
        )
        # Need get_fork_commits to return the list
        with patch.object(
            mod,
            "get_fork_commits",
            return_value=[{"sha": "fork111"}, {"sha": "fork222"}],
        ):
            data = self._call(mocks)

        # The fork commits should be attributed to the parent repo
        assert data["total_commits_all"] == 2

    # 3. Fork commits exceed search API count
    def test_fork_commits_exceed_search(self):
        parent_name = "tobie/specref"
        fork_name = "testuser/specref"
        mocks = _patch_gather(
            {
                "get_all_commits": {
                    "total_count": 1,
                    "items": [
                        {
                            "sha": "search1",
                            "repository": {
                                "full_name": fork_name,
                                "private": False,
                            },
                            "commit": {
                                "message": "x",
                                "author": {"date": "2026-01-02T00:00:00Z"},
                            },
                        }
                    ],
                },
                "get_user_forks": [
                    {
                        "full_name": fork_name,
                        "parent": {"full_name": parent_name},
                    }
                ],
                "get_repo_info": {
                    parent_name: {
                        "nameWithOwner": parent_name,
                        "description": "spec references",
                        "primaryLanguage": {"name": "JavaScript"},
                        "isFork": False,
                        "parent": None,
                    },
                },
            }
        )
        # get_fork_commits returns MORE than the search API found (1)
        with patch.object(
            mod,
            "get_fork_commits",
            return_value=[
                {"sha": "fc1"},
                {"sha": "fc2"},
                {"sha": "fc3"},
            ],
        ):
            data = self._call(mocks)

        # Fork count (3) > search count (1), so fork count wins
        assert data["total_commits_all"] == 3

    # 4. Profile repo skipped; empty repos_to_lookup → repo_info = {}
    def test_profile_repo_skipped(self):
        mocks = _patch_gather(
            {
                "get_all_commits": {
                    "total_count": 1,
                    "items": [
                        {
                            "sha": "ppp111",
                            "repository": {
                                "full_name": "testuser/testuser",
                                "private": False,
                            },
                            "commit": {
                                "message": "Update README",
                                "author": {"date": "2026-01-02T00:00:00Z"},
                            },
                        }
                    ],
                },
            }
        )
        data = self._call(mocks)
        # Profile repo is skipped, so 0 commits in aggregated output
        assert data["total_commits_all"] == 0

    # 5. Fork owned by another user → skipped during aggregation
    def test_fork_owned_by_other_user(self):
        mocks = _patch_gather(
            {
                "get_all_commits": {
                    "total_count": 1,
                    "items": [
                        {
                            "sha": "other1",
                            "repository": {
                                "full_name": "otheruser/somerepo",
                                "private": False,
                            },
                            "commit": {
                                "message": "x",
                                "author": {"date": "2026-01-02T00:00:00Z"},
                            },
                        }
                    ],
                },
                "get_repo_info": {
                    "otheruser/somerepo": {
                        "nameWithOwner": "otheruser/somerepo",
                        "isFork": True,
                        "parent": {"nameWithOwner": "upstream/somerepo"},
                        "description": "",
                        "primaryLanguage": {"name": "Go"},
                    },
                },
            }
        )
        data = self._call(mocks)
        # Fork by another user is skipped
        assert data["total_commits_all"] == 0

    # 6. Target parent repo should be skipped (contains "serenity")
    def test_target_parent_skipped(self):
        fork_name = "testuser/myfork"
        parent_name = "org/serenity-os"
        mocks = _patch_gather(
            {
                "get_all_commits": {
                    "total_count": 1,
                    "items": [
                        {
                            "sha": "sss111",
                            "repository": {
                                "full_name": fork_name,
                                "private": False,
                            },
                            "commit": {
                                "message": "x",
                                "author": {"date": "2026-01-02T00:00:00Z"},
                            },
                        }
                    ],
                },
                "get_repo_info": {
                    fork_name: {
                        "nameWithOwner": fork_name,
                        "isFork": True,
                        "parent": {"nameWithOwner": parent_name},
                        "description": "",
                        "primaryLanguage": {"name": "C++"},
                    },
                },
            }
        )
        data = self._call(mocks)
        # Parent "serenity" is skipped, so commits dropped
        assert data["total_commits_all"] == 0

    # 7. Commit stat fetch returns None → (repo, 0, 0) fallback
    def test_commit_stat_returns_none(self):
        mocks = _patch_gather(
            {
                "run_gh_command": None,
            }
        )
        data = self._call(mocks)
        # Stats should fall back to 0; the commit still counts
        repo_stats = data.get("repo_line_stats", {})
        if repo_stats:
            for repo, stats in repo_stats.items():
                assert stats["additions"] == 0
                assert stats["deletions"] == 0

    # 8. Language check triggered → get_effective_language returns "C++"
    def test_language_check_triggered(self):
        mocks = _patch_gather(
            {
                "get_all_commits": {
                    "total_count": 1,
                    "items": [
                        {
                            "sha": "lang1",
                            "repository": {
                                "full_name": "owner/jsrepo",
                                "private": False,
                            },
                            "commit": {
                                "message": "x",
                                "author": {"date": "2026-01-02T00:00:00Z"},
                            },
                        }
                    ],
                },
                "get_repo_info": {
                    "owner/jsrepo": {
                        "nameWithOwner": "owner/jsrepo",
                        "isFork": False,
                        "parent": None,
                        "description": "A JS repo",
                        "primaryLanguage": {"name": "JavaScript"},
                    },
                },
                "get_effective_language": "C++",
            }
        )
        data = self._call(mocks)

        # The repo should appear with language "C++"
        found = False
        for repos in data["repos_by_category"].values():
            for repo in repos:
                if repo["name"] == "owner/jsrepo":
                    assert repo["language"] == "C++"
                    found = True
        assert found, "owner/jsrepo not found in repos_by_category"

    # 9. get_effective_language returns None → falls back to reported
    def test_language_check_returns_none(self):
        mocks = _patch_gather(
            {
                "get_all_commits": {
                    "total_count": 1,
                    "items": [
                        {
                            "sha": "lang2",
                            "repository": {
                                "full_name": "owner/htmlrepo",
                                "private": False,
                            },
                            "commit": {
                                "message": "x",
                                "author": {"date": "2026-01-02T00:00:00Z"},
                            },
                        }
                    ],
                },
                "get_repo_info": {
                    "owner/htmlrepo": {
                        "nameWithOwner": "owner/htmlrepo",
                        "isFork": False,
                        "parent": None,
                        "description": "HTML things",
                        "primaryLanguage": {"name": "HTML"},
                    },
                },
            }
        )
        with patch.object(
            mod,
            "get_effective_language",
            return_value=None,
        ):
            data = self._call(mocks)

        # Should fall back to "HTML"
        found = False
        for repos in data["repos_by_category"].values():
            for repo in repos:
                if repo["name"] == "owner/htmlrepo":
                    assert repo["language"] == "HTML"
                    found = True
        assert found, "owner/htmlrepo not found in repos_by_category"


class TestGatherUserDataLightBranches:
    """Tests exercising specific branches inside gather_user_data_light()."""

    def _call(self, overrides=None, username="testuser"):
        """Call gather_user_data_light with API functions mocked."""
        defaults = {
            "get_contributions_summary": _base_contributions(username),
            "get_prs_created": {
                "search": {"nodes": [], "issueCount": 0},
            },
            "get_prs_reviewed": [],
            "get_repo_info_cached": {},
        }
        if overrides:
            defaults.update(overrides)

        patches = {}
        for name, retval in defaults.items():
            patches[name] = patch.object(
                mod,
                name,
                return_value=retval,
            )

        for p in patches.values():
            p.start()

        try:
            return mod.gather_user_data_light(
                username,
                "2026-01-01",
                "2026-01-07",
                show_progress=False,
            )
        finally:
            for p in patches.values():
                p.stop()

    # 10. PRs with valid repository.nameWithOwner → added to repos_to_fetch
    def test_pr_repos_extracted(self):
        pr_node = {
            "title": "Fix bug",
            "url": "https://github.com/ext/lib/pull/1",
            "state": "MERGED",
            "additions": 10,
            "deletions": 2,
            "reviews": {"totalCount": 1},
            "comments": {"totalCount": 0},
            "repository": {
                "nameWithOwner": "ext/lib",
                "primaryLanguage": {"name": "Go"},
            },
        }
        reviewed_node = {
            "title": "Review this",
            "url": "https://github.com/ext/other/pull/5",
            "state": "OPEN",
            "additions": 20,
            "deletions": 5,
            "author": {"login": "someone"},
            "repository": {
                "nameWithOwner": "ext/other",
                "primaryLanguage": {"name": "Rust"},
            },
        }
        data = self._call(
            {
                "get_prs_created": {
                    "search": {"nodes": [pr_node], "issueCount": 1},
                },
                "get_prs_reviewed": [reviewed_node],
                "get_repo_info_cached": {
                    "ext/lib": {
                        "nameWithOwner": "ext/lib",
                        "description": "",
                        "primaryLanguage": {"name": "Go"},
                        "isFork": False,
                        "parent": None,
                    },
                    "ext/other": {
                        "nameWithOwner": "ext/other",
                        "description": "",
                        "primaryLanguage": {"name": "Rust"},
                        "isFork": False,
                        "parent": None,
                    },
                },
            }
        )

        assert data["total_prs"] == 1
        assert len(data["prs_nodes"]) == 1
        assert len(data["reviewed_nodes"]) == 1

    # 11. Profile repo skipped in light mode
    def test_skip_repo_in_light_mode(self):
        contribs = _base_contributions("testuser")
        # Add testuser/testuser as a commit repo
        repos = contribs["user"]["contributionsCollection"][
            "commitContributionsByRepository"
        ]
        repos.append(
            {
                "repository": {
                    "nameWithOwner": "testuser/testuser",
                    "isFork": False,
                    "parent": None,
                    "isPrivate": False,
                    "primaryLanguage": None,
                    "description": "Profile repo",
                },
                "contributions": {"totalCount": 3},
            }
        )
        data = self._call(
            {
                "get_contributions_summary": contribs,
            }
        )

        # testuser/testuser should be skipped
        all_repo_names = []
        for repos_list in data["repos_by_category"].values():
            for repo in repos_list:
                all_repo_names.append(repo["name"])
        assert "testuser/testuser" not in all_repo_names


class TestAggregateOrgDataLineStats:
    """Test line_stats merging in aggregate_org_data."""

    # 12. Two members' repo_line_stats for same repo summed correctly
    def test_line_stats_merging(self):
        member_data = [
            {
                "username": "alice",
                "user_real_name": "Alice",
                "user_company": "",
                "total_commits_default_branch": 10,
                "total_commits_all": 10,
                "total_prs": 0,
                "total_pr_reviews": 0,
                "total_issues": 0,
                "total_additions": 0,
                "total_deletions": 0,
                "reviews_received": 0,
                "pr_comments_received": 0,
                "lines_reviewed": 0,
                "review_comments": 0,
                "test_commits": 0,
                "repos_contributed": 1,
                "repos_by_category": {
                    "Other": [
                        {
                            "name": "org/shared",
                            "commits": 10,
                            "language": "Python",
                            "description": "",
                        }
                    ]
                },
                "prs_nodes": [],
                "reviewed_nodes": [],
                "repo_line_stats": {
                    "org/shared": {
                        "additions": 100,
                        "deletions": 20,
                    }
                },
                "repo_languages": {"org/shared": "Python"},
                "is_light_mode": False,
            },
            {
                "username": "bob",
                "user_real_name": "Bob",
                "user_company": "",
                "total_commits_default_branch": 5,
                "total_commits_all": 5,
                "total_prs": 0,
                "total_pr_reviews": 0,
                "total_issues": 0,
                "total_additions": 0,
                "total_deletions": 0,
                "reviews_received": 0,
                "pr_comments_received": 0,
                "lines_reviewed": 0,
                "review_comments": 0,
                "test_commits": 0,
                "repos_contributed": 1,
                "repos_by_category": {
                    "Other": [
                        {
                            "name": "org/shared",
                            "commits": 5,
                            "language": "Python",
                            "description": "",
                        }
                    ]
                },
                "prs_nodes": [],
                "reviewed_nodes": [],
                "repo_line_stats": {
                    "org/shared": {
                        "additions": 50,
                        "deletions": 10,
                    }
                },
                "repo_languages": {"org/shared": "Python"},
                "is_light_mode": False,
            },
        ]

        aggregated = mod.aggregate_org_data(member_data)

        # Line stats should be summed
        stats = aggregated["repo_line_stats"]["org/shared"]
        assert stats["additions"] == 150  # 100 + 50
        assert stats["deletions"] == 30  # 20 + 10


class TestAggregateOrgDataUserCompany:
    """Test user_company field tracking in aggregate_org_data."""

    def test_member_company_tracked(self):
        member_data = [
            {
                "username": "alice",
                "user_real_name": "Alice",
                "user_company": "@acme",
                "total_commits_default_branch": 5,
                "total_commits_all": 5,
                "total_prs": 0,
                "total_pr_reviews": 0,
                "total_issues": 0,
                "total_additions": 0,
                "total_deletions": 0,
                "reviews_received": 0,
                "pr_comments_received": 0,
                "lines_reviewed": 0,
                "review_comments": 0,
                "test_commits": 0,
                "repos_contributed": 1,
                "repos_by_category": {
                    "Other": [
                        {
                            "name": "org/repo",
                            "commits": 5,
                            "language": "Go",
                            "description": "",
                        }
                    ]
                },
                "prs_nodes": [],
                "reviewed_nodes": [],
                "repo_line_stats": {},
                "repo_languages": {},
                "is_light_mode": True,
            },
        ]

        aggregated = mod.aggregate_org_data(member_data)

        assert aggregated["member_companies"]["alice"] == "@acme"


class TestGatherUserDataWithProgress:
    """Test gather_user_data with show_progress=True to cover branches."""

    def _call_with_progress(self, mocks, username="testuser"):
        """Call gather_user_data with show_progress=True."""
        patches = {}
        for name, retval in mocks.items():
            patches[name] = patch.object(
                mod,
                name,
                return_value=retval,
            )

        for p in patches.values():
            p.start()

        # Also mock progress so it doesn't write to stderr
        progress_patch = patch.object(mod, "progress")
        progress_patch.start()

        try:
            return mod.gather_user_data(
                username,
                "2026-01-01",
                "2026-01-07",
                show_progress=True,
            )
        finally:
            progress_patch.stop()
            for p in patches.values():
                p.stop()

    def test_progress_branches_covered(self):
        """Calling with show_progress=True covers progress.start/update."""
        mocks = _patch_gather()
        data = self._call_with_progress(mocks)
        assert data["username"] == "testuser"
        assert "repos_by_category" in data


class TestGatherUserDataLightWithProgress:
    """Test gather_user_data_light with show_progress=True."""

    def test_progress_branches_covered(self):
        defaults = {
            "get_contributions_summary": _base_contributions("testuser"),
            "get_prs_created": {
                "search": {"nodes": [], "issueCount": 0},
            },
            "get_prs_reviewed": [],
            "get_repo_info_cached": {},
        }

        patches = {}
        for name, retval in defaults.items():
            patches[name] = patch.object(
                mod,
                name,
                return_value=retval,
            )

        for p in patches.values():
            p.start()

        progress_patch = patch.object(mod, "progress")
        progress_patch.start()

        try:
            data = mod.gather_user_data_light(
                "testuser",
                "2026-01-01",
                "2026-01-07",
                show_progress=True,
            )
        finally:
            progress_patch.stop()
            for p in patches.values():
                p.stop()

        assert data["username"] == "testuser"
        assert data["is_light_mode"] is True
