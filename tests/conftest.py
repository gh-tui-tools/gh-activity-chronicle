"""Shared pytest fixtures and configuration for gh-activity-chronicle tests."""

import importlib.machinery
import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


def pytest_addoption(parser):
    """Add custom command line options."""
    parser.addoption(
        "--update-golden",
        action="store_true",
        default=False,
        help="Update golden snapshot files instead of comparing"
    )


# ---------------------------------------------------------------------------
# Import the main script (which has no .py extension)
# ---------------------------------------------------------------------------

def load_chronicle_module():
    """Load gh-activity-chronicle as a module despite lacking .py extension."""
    script_path = Path(__file__).parent.parent / "gh-activity-chronicle"

    # Use machinery.SourceFileLoader for broader Python version compatibility
    loader = importlib.machinery.SourceFileLoader("chronicle", str(script_path))
    spec = importlib.util.spec_from_loader("chronicle", loader)
    module = importlib.util.module_from_spec(spec)

    # Add to sys.modules before exec to handle circular imports
    sys.modules["chronicle"] = module

    # Prevent the script from running main() on import
    # We patch __name__ check and sys.exit
    with patch.object(sys, "exit"):
        spec.loader.exec_module(module)

    return module


# Load once at module level for efficiency
chronicle = load_chronicle_module()


@pytest.fixture
def mod():
    """Provide access to the chronicle module."""
    return chronicle


# ---------------------------------------------------------------------------
# Sample data fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_pr_nodes():
    """Sample PR data for testing PR table generation."""
    return [
        {
            "title": "Add new feature",
            "url": "https://github.com/owner/repo/pull/1",
            "state": "MERGED",
            "additions": 500,
            "deletions": 100,
            "repository": {
                "nameWithOwner": "owner/repo",
                "primaryLanguage": {"name": "Python"}
            }
        },
        {
            "title": "Fix critical bug",
            "url": "https://github.com/owner/repo/pull/2",
            "state": "MERGED",
            "additions": 50,
            "deletions": 200,
            "repository": {
                "nameWithOwner": "owner/repo",
                "primaryLanguage": {"name": "Python"}
            }
        },
        {
            "title": "Update documentation",
            "url": "https://github.com/other/docs/pull/5",
            "state": "OPEN",
            "additions": 1000,
            "deletions": 0,
            "repository": {
                "nameWithOwner": "other/docs",
                "primaryLanguage": None
            }
        },
    ]


@pytest.fixture
def sample_repos_by_category():
    """Sample categorized repos for testing aggregation."""
    return {
        "Web standards and specifications": [
            {"name": "w3c/csswg-drafts", "commits": 10, "prs": 2,
             "language": "CSS", "description": "CSS specs"},
            {"name": "whatwg/html", "commits": 5, "prs": 1,
             "language": "HTML", "description": "HTML Standard"},
        ],
        "Browser engines": [
            {"name": "nicehero/nicejson", "commits": 3, "prs": 0,
             "language": "C++", "description": "JSON library"},
        ],
        "Other": [
            {"name": "user/random-project", "commits": 1, "prs": 0,
             "language": "Python", "description": "Something else"},
        ],
    }


@pytest.fixture
def sample_repo_line_stats():
    """Sample line stats by repo."""
    return {
        "w3c/csswg-drafts": {"additions": 500, "deletions": 100},
        "whatwg/html": {"additions": 200, "deletions": 50},
        "nicehero/nicejson": {"additions": 150, "deletions": 30},
        "user/random-project": {"additions": 10, "deletions": 5},
    }


@pytest.fixture
def sample_member_data():
    """Sample member data for testing org aggregation.

    This matches the structure returned by gather_user_data_light().
    """
    return [
        {
            "username": "alice",
            "user_real_name": "Alice Smith",
            "company": "@acme",
            "total_commits_default_branch": 50,
            "total_commits_all": 50,
            "total_prs": 5,
            "total_pr_reviews": 10,
            "total_issues": 2,
            "total_additions": 1000,
            "total_deletions": 200,
            "repos_by_category": {
                "Web standards and specifications": [
                    {"name": "w3c/csswg-drafts", "commits": 30, "prs": 3,
                     "language": "CSS", "description": "CSS specs"},
                    {"name": "whatwg/html", "commits": 20, "prs": 2,
                     "language": "HTML", "description": "HTML Standard"},
                ]
            },
            "prs_nodes": [
                {"url": "https://github.com/w3c/csswg-drafts/pull/1",
                 "title": "Add feature", "state": "MERGED",
                 "additions": 100, "deletions": 10,
                 "repository": {"nameWithOwner": "w3c/csswg-drafts"}}
            ],
            "reviewed_nodes": [
                {"url": "https://github.com/whatwg/html/pull/5",
                 "title": "Fix issue", "state": "MERGED",
                 "additions": 50, "deletions": 5,
                 "author": {"login": "bob"},
                 "repository": {"nameWithOwner": "whatwg/html"}}
            ],
            "is_light_mode": True,
        },
        {
            "username": "bob",
            "user_real_name": "Bob Jones",
            "company": "@acme @w3c",
            "total_commits_default_branch": 30,
            "total_commits_all": 30,
            "total_prs": 3,
            "total_pr_reviews": 5,
            "total_issues": 1,
            "total_additions": 500,
            "total_deletions": 100,
            "repos_by_category": {
                "Web standards and specifications": [
                    {"name": "w3c/csswg-drafts", "commits": 30, "prs": 3,
                     "language": "CSS", "description": "CSS specs"},
                ]
            },
            "prs_nodes": [
                {"url": "https://github.com/w3c/csswg-drafts/pull/2",
                 "title": "Another feature", "state": "OPEN",
                 "additions": 200, "deletions": 20,
                 "repository": {"nameWithOwner": "w3c/csswg-drafts"}}
            ],
            "reviewed_nodes": [
                # Same PR as alice reviewed - should be deduplicated
                {"url": "https://github.com/whatwg/html/pull/5",
                 "title": "Fix issue", "state": "MERGED",
                 "additions": 50, "deletions": 5,
                 "author": {"login": "charlie"},
                 "repository": {"nameWithOwner": "whatwg/html"}}
            ],
            "is_light_mode": True,
        },
    ]


# ---------------------------------------------------------------------------
# Mock fixtures for API calls
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_gh_command():
    """Fixture to mock run_gh_command for integration tests."""
    with patch.object(chronicle, "run_gh_command") as mock:
        yield mock


@pytest.fixture
def mock_subprocess():
    """Fixture to mock subprocess.run for lower-level tests."""
    with patch("subprocess.run") as mock:
        yield mock


# ---------------------------------------------------------------------------
# API response fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def contribution_summary_response():
    """Sample GraphQL response for contribution summary."""
    return {
        "data": {
            "user": {
                "name": "Test User",
                "company": "@testorg",
                "contributionsCollection": {
                    "totalCommitContributions": 100,
                    "restrictedContributionsCount": 10,
                    "totalPullRequestContributions": 15,
                    "totalIssueContributions": 5,
                    "totalPullRequestReviewContributions": 20,
                    "commitContributionsByRepository": [
                        {
                            "repository": {
                                "nameWithOwner": "owner/repo1",
                                "isFork": False,
                                "parent": None,
                                "isPrivate": False,
                                "primaryLanguage": {"name": "Python"},
                                "description": "A test repo"
                            },
                            "contributions": {"totalCount": 50}
                        },
                        {
                            "repository": {
                                "nameWithOwner": "owner/repo2",
                                "isFork": True,
                                "parent": {"nameWithOwner": "upstream/repo2"},
                                "isPrivate": False,
                                "primaryLanguage": {"name": "JavaScript"},
                                "description": "Forked repo"
                            },
                            "contributions": {"totalCount": 30}
                        }
                    ]
                }
            }
        }
    }


@pytest.fixture
def commits_search_response():
    """Sample REST API response for commit search."""
    return {
        "total_count": 2,
        "items": [
            {
                "sha": "abc123",
                "commit": {
                    "message": "Add new feature\n\nDetailed description",
                    "author": {"date": "2026-01-15T10:00:00Z"}
                },
                "repository": {
                    "full_name": "owner/repo1",
                    "fork": False
                }
            },
            {
                "sha": "def456",
                "commit": {
                    "message": "Fix bug",
                    "author": {"date": "2026-01-16T14:30:00Z"}
                },
                "repository": {
                    "full_name": "owner/repo2",
                    "fork": True
                }
            }
        ]
    }
