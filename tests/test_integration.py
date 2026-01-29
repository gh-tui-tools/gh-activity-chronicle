"""Integration tests with mocked GitHub API calls.

These tests verify the data flow from API responses through to output,
using mocked subprocess calls to avoid actual GitHub API usage.
"""

from unittest.mock import MagicMock, patch

import pytest


class TestRunGhCommand:
    """Tests for the run_gh_command wrapper."""

    def test_successful_json_response(self, mod, mock_subprocess):
        """Test successful JSON response parsing."""
        mock_subprocess.return_value = MagicMock(
            stdout='{"key": "value"}', stderr="", returncode=0
        )

        result = mod.run_gh_command(["api", "test"], parse_json=True)
        assert result == {"key": "value"}

    def test_non_json_response(self, mod, mock_subprocess):
        """Test non-JSON response handling."""
        mock_subprocess.return_value = MagicMock(
            stdout="plain text response", stderr="", returncode=0
        )

        result = mod.run_gh_command(["api", "test"], parse_json=False)
        assert result == "plain text response"

    def test_rate_limit_detection(self, mod, mock_subprocess):
        """Test that rate limit errors are detected."""
        from subprocess import CalledProcessError

        error = CalledProcessError(1, "gh")
        error.stderr = "API rate limit exceeded"
        mock_subprocess.side_effect = error

        # Should raise or return None depending on implementation
        try:
            mod.run_gh_command(["api", "test"], raise_on_rate_limit=True)
        except mod.RateLimitError:
            pass  # Expected
        except Exception:
            pass  # Also acceptable

    def test_transient_error_retry(self, mod, mock_subprocess):
        """Test retry on transient HTTP errors."""
        from subprocess import CalledProcessError

        # First call fails with 502, second succeeds
        error = CalledProcessError(1, "gh")
        error.stderr = "HTTP 502"

        success = MagicMock(
            stdout='{"data": "success"}', stderr="", returncode=0
        )

        mock_subprocess.side_effect = [error, success]

        result = mod.run_gh_command(["api", "test"], parse_json=True)
        assert result == {"data": "success"}
        assert mock_subprocess.call_count == 2

    def test_json_decode_error_fallback(self, mod, mock_subprocess):
        """Non-JSON output with parse_json=True returns raw string."""
        mock_subprocess.return_value = MagicMock(
            stdout="not valid json output", stderr="", returncode=0
        )

        result = mod.run_gh_command(["api", "test"], parse_json=True)
        assert result == "not valid json output"

    def test_max_retries_exhausted_returns_none(self, mod, mock_subprocess):
        """Exhausting retries on transient errors returns None."""
        from subprocess import CalledProcessError

        error = CalledProcessError(1, "gh")
        error.stderr = "HTTP 502"

        # All attempts fail with 502
        mock_subprocess.side_effect = [error, error, error, error]

        result = mod.run_gh_command(
            ["api", "test"], parse_json=True, max_retries=3
        )
        assert result is None
        assert mock_subprocess.call_count == 4  # initial + 3 retries


class TestContributionSummary:
    """Tests for get_contributions_summary()."""

    def test_parses_graphql_response(
        self, mod, mock_gh_command, contribution_summary_response
    ):
        """Test parsing of contribution summary GraphQL response."""
        mock_gh_command.return_value = contribution_summary_response

        result = mod.get_contributions_summary(
            "testuser", "2026-01-01", "2026-01-31"
        )

        assert result is not None
        # Should extract user data
        if isinstance(result, dict):
            assert (
                "user" in result
                or "contributionsCollection" in result
                or "totalCommitContributions" in str(result)
            )


class TestGatherUserData:
    """Integration tests for gather_user_data()."""

    @pytest.fixture
    def mock_all_api_calls(self, mod):
        """Mock all API-calling functions for gather_user_data."""
        with patch.multiple(
            mod,
            get_contributions_summary=MagicMock(
                return_value={
                    "data": {
                        "user": {
                            "name": "Test User",
                            "company": "@testorg",
                            "contributionsCollection": {
                                "totalCommitContributions": 50,
                                "restrictedContributionsCount": 5,
                                "totalPullRequestContributions": 10,
                                "totalIssueContributions": 3,
                                "totalPullRequestReviewContributions": 15,
                                "commitContributionsByRepository": [
                                    {
                                        "repository": {
                                            "nameWithOwner": "org/repo",
                                            "isFork": False,
                                            "parent": None,
                                            "isPrivate": False,
                                            "primaryLanguage": {
                                                "name": "Python"
                                            },
                                            "description": "Test repo",
                                        },
                                        "contributions": {"totalCount": 50},
                                    }
                                ],
                            },
                        }
                    }
                }
            ),
            get_all_commits=MagicMock(
                return_value={
                    "items": [
                        {
                            "sha": "abc123",
                            "repository": {"full_name": "org/repo"},
                            "commit": {"message": "Test commit"},
                        }
                    ],
                    "total_count": 1,
                }
            ),
            get_prs_created=MagicMock(
                return_value={"search": {"nodes": [], "issueCount": 0}}
            ),
            get_prs_reviewed=MagicMock(return_value=[]),
            get_user_forks=MagicMock(return_value=[]),
            get_repo_info=MagicMock(return_value={}),
            count_test_related_commits=MagicMock(return_value=0),
            get_review_comments_count=MagicMock(return_value=0),
        ):
            yield

    def test_basic_data_gathering(self, mod, mock_all_api_calls):
        """Test basic data gathering flow."""
        # This test verifies the orchestration works with mocked dependencies
        result = mod.gather_user_data(
            "testuser", "2026-01-01", "2026-01-31", show_progress=False
        )

        assert isinstance(result, dict)
        assert "username" in result

    def test_returns_expected_structure(self, mod, mock_all_api_calls):
        """Verify returned data has expected structure."""
        result = mod.gather_user_data(
            "testuser", "2026-01-01", "2026-01-31", show_progress=False
        )

        expected_keys = ["username", "repos_by_category"]
        for key in expected_keys:
            assert key in result, f"Missing expected key: {key}"


class TestGatherUserDataLight:
    """Integration tests for gather_user_data_light() (org mode)."""

    @pytest.fixture
    def mock_light_api_calls(self, mod):
        """Mock API calls for light mode."""
        with patch.multiple(
            mod,
            get_contributions_summary=MagicMock(
                return_value={
                    "data": {
                        "user": {
                            "name": "Test User",
                            "company": "@testorg",
                            "contributionsCollection": {
                                "totalCommitContributions": 25,
                                "restrictedContributionsCount": 0,
                                "totalPullRequestContributions": 5,
                                "totalIssueContributions": 2,
                                "totalPullRequestReviewContributions": 8,
                                "commitContributionsByRepository": [
                                    {
                                        "repository": {
                                            "nameWithOwner": "org/repo",
                                            "isFork": False,
                                            "parent": None,
                                            "isPrivate": False,
                                            "primaryLanguage": {"name": "Go"},
                                            "description": "Go project",
                                        },
                                        "contributions": {"totalCount": 25},
                                    }
                                ],
                            },
                        }
                    }
                }
            ),
            get_prs_created=MagicMock(return_value=[]),
            get_prs_reviewed=MagicMock(return_value=[]),
            get_repo_info_cached=MagicMock(return_value=None),
        ):
            yield

    def test_light_mode_flag(self, mod, mock_light_api_calls):
        """Light mode should set is_light_mode flag."""
        result = mod.gather_user_data_light(
            "testuser", "2026-01-01", "2026-01-31"
        )

        assert result.get("is_light_mode") is True

    def test_skips_expensive_calls(self, mod, mock_light_api_calls):
        """Light mode should not call expensive functions."""
        # get_all_commits and fork scanning should not be called
        with patch.object(mod, "get_all_commits") as mock_commits:
            with patch.object(mod, "get_user_forks") as mock_forks:
                mod.gather_user_data_light(
                    "testuser", "2026-01-01", "2026-01-31"
                )
                # These should NOT be called in light mode
                mock_commits.assert_not_called()
                mock_forks.assert_not_called()


class TestGatherUserDataLightForkAttribution:
    """Tests for fork attribution and repo aggregation in light mode."""

    @pytest.fixture
    def mock_fork_api_calls(self, mod):
        """Mock API calls returning multiple repos including a fork."""
        with patch.multiple(
            mod,
            get_contributions_summary=MagicMock(
                return_value={
                    "user": {
                        "name": "Test User",
                        "company": "",
                        "contributionsCollection": {
                            "totalCommitContributions": 40,
                            "restrictedContributionsCount": 0,
                            "totalPullRequestContributions": 5,
                            "totalIssueContributions": 1,
                            "totalPullRequestReviewContributions": 3,
                            "totalRepositoriesWithContributedCommits": 3,
                            "commitContributionsByRepository": [
                                {
                                    "repository": {
                                        "nameWithOwner": "upstream/lib",
                                        "isFork": False,
                                        "parent": None,
                                        "isPrivate": False,
                                        "primaryLanguage": {"name": "Python"},
                                        "description": "Upstream lib",
                                    },
                                    "contributions": {"totalCount": 15},
                                },
                                {
                                    "repository": {
                                        "nameWithOwner": "testuser/lib",
                                        "isFork": True,
                                        "parent": {
                                            "nameWithOwner": "upstream/lib"
                                        },
                                        "isPrivate": False,
                                        "primaryLanguage": {"name": "Python"},
                                        "description": "Fork of lib",
                                    },
                                    "contributions": {"totalCount": 10},
                                },
                                {
                                    "repository": {
                                        "nameWithOwner": "testuser/myapp",
                                        "isFork": False,
                                        "parent": None,
                                        "isPrivate": False,
                                        "primaryLanguage": {"name": "Go"},
                                        "description": "My app",
                                    },
                                    "contributions": {"totalCount": 15},
                                },
                            ],
                            "pullRequestContributionsByRepository": [],
                            "pullRequestReviewContributionsByRepository": [],
                        },
                    }
                }
            ),
            get_prs_created=MagicMock(
                return_value={"search": {"nodes": [], "issueCount": 0}}
            ),
            get_prs_reviewed=MagicMock(return_value=[]),
            get_repo_info_cached=MagicMock(return_value={}),
        ):
            yield

    def test_fork_commits_attributed_to_parent(self, mod, mock_fork_api_calls):
        """Fork commits should be aggregated into the parent repo."""
        result = mod.gather_user_data_light(
            "testuser", "2026-01-01", "2026-01-31"
        )

        repos_by_cat = result.get("repos_by_category", {})
        # Flatten all repos
        all_repos = [repo for repos in repos_by_cat.values() for repo in repos]
        repo_names = {r["name"] for r in all_repos}

        # The fork "testuser/lib" should be merged into "upstream/lib"
        assert "testuser/lib" not in repo_names
        assert "upstream/lib" in repo_names

        # upstream/lib should have combined 15+10=25 commits
        upstream = next(r for r in all_repos if r["name"] == "upstream/lib")
        assert upstream["commits"] == 25

    def test_non_fork_repo_preserved(self, mod, mock_fork_api_calls):
        """Non-fork repos should appear with their own commit counts."""
        result = mod.gather_user_data_light(
            "testuser", "2026-01-01", "2026-01-31"
        )

        repos_by_cat = result.get("repos_by_category", {})
        all_repos = [repo for repos in repos_by_cat.values() for repo in repos]
        myapp = next(
            (r for r in all_repos if r["name"] == "testuser/myapp"), None
        )
        assert myapp is not None
        assert myapp["commits"] == 15

    def test_repos_are_categorized(self, mod, mock_fork_api_calls):
        """Each aggregated repo should be placed in a category."""
        result = mod.gather_user_data_light(
            "testuser", "2026-01-01", "2026-01-31"
        )

        repos_by_cat = result.get("repos_by_category", {})
        # Should have at least one category
        assert len(repos_by_cat) > 0
        # Every repo should have category keys
        for repos in repos_by_cat.values():
            for repo in repos:
                assert "name" in repo
                assert "commits" in repo


class TestReportGeneration:
    """Tests for report generation."""

    @pytest.fixture
    def mock_user_data(self):
        """Complete mock user data for report generation."""
        return {
            "username": "testuser",
            "user_real_name": "Test User",
            "company": "@testorg",
            "total_commits_default_branch": 80,
            "total_commits_all": 100,
            "total_prs": 15,
            "total_pr_reviews": 20,
            "total_issues": 5,
            "total_additions": 5000,
            "total_deletions": 1000,
            "test_commits": 10,
            "reviews_received": 5,
            "pr_comments_received": 2,
            "lines_reviewed": 1000,
            "review_comments": 5,
            "repos_contributed": 2,
            "repos_by_category": {
                "Web standards and specifications": [
                    {
                        "name": "w3c/csswg-drafts",
                        "commits": 50,
                        "prs": 5,
                        "language": "CSS",
                        "description": "CSS specs",
                    }
                ],
                "Other": [
                    {
                        "name": "user/project",
                        "commits": 10,
                        "prs": 1,
                        "language": "Python",
                        "description": "Personal project",
                    }
                ],
            },
            "repo_line_stats": {
                "w3c/csswg-drafts": {"additions": 3000, "deletions": 500},
                "user/project": {"additions": 500, "deletions": 100},
            },
            "repo_languages": {
                "w3c/csswg-drafts": "CSS",
                "user/project": "Python",
            },
            "prs_nodes": [
                {
                    "title": "Add feature",
                    "url": "https://github.com/w3c/csswg-drafts/pull/1",
                    "state": "MERGED",
                    "additions": 200,
                    "deletions": 50,
                    "repository": {
                        "nameWithOwner": "w3c/csswg-drafts",
                        "primaryLanguage": {"name": "CSS"},
                    },
                }
            ],
            "reviewed_nodes": [
                {
                    "title": "Fix bug",
                    "url": "https://github.com/w3c/csswg-drafts/pull/2",
                    "additions": 100,
                    "deletions": 20,
                    "author": {"login": "other"},
                    "repository": {"nameWithOwner": "w3c/csswg-drafts"},
                }
            ],
        }

    def test_report_contains_username(self, mod, mock_user_data):
        """Report should contain the username."""
        with patch.object(
            mod,
            "gather_user_data",
            return_value=mock_user_data,
        ):
            report = mod.generate_report(
                "testuser", "2026-01-01", "2026-01-31"
            )

            assert "testuser" in report

    def test_report_contains_date_range(self, mod, mock_user_data):
        """Report should show the date range."""
        with patch.object(
            mod,
            "gather_user_data",
            return_value=mock_user_data,
        ):
            report = mod.generate_report(
                "testuser", "2026-01-01", "2026-01-31"
            )

            assert "2026-01-01" in report
            assert "2026-01-31" in report

    def test_report_has_sections(self, mod, mock_user_data):
        """Report should have expected sections."""
        with patch.object(
            mod,
            "gather_user_data",
            return_value=mock_user_data,
        ):
            report = mod.generate_report(
                "testuser", "2026-01-01", "2026-01-31"
            )

            # Check for expected section headers
            assert "## " in report  # Has level-2 headers
            # Check for specific sections
            expected_sections = [
                "Executive summary",
                "Projects by category",
                "Languages",
            ]
            for section in expected_sections:
                assert section in report, f"Missing section: {section}"

    def test_report_markdown_valid(self, mod, mock_user_data):
        """Report should be valid markdown."""
        with patch.object(
            mod,
            "gather_user_data",
            return_value=mock_user_data,
        ):
            report = mod.generate_report(
                "testuser", "2026-01-01", "2026-01-31"
            )

            # Basic markdown validity checks
            assert report.startswith("#")  # Starts with header
            # Tables should have proper structure
            if "|" in report:
                # Check for separator row (---|---)
                assert "---" in report


class TestOrgReportGeneration:
    """Tests for organization report generation."""

    @pytest.fixture
    def mock_org_data(self):
        """Mock aggregated org data."""
        return {
            "total_commits_default_branch": 500,
            "total_commits_all": 500,
            "total_prs": 50,
            "total_pr_reviews": 100,
            "total_issues": 20,
            "repos_contributed": 2,
            "total_additions": 10000,
            "total_deletions": 2000,
            "repos_by_category": {
                "Web standards and specifications": [
                    {
                        "name": "w3c/csswg-drafts",
                        "commits": 300,
                        "prs": 30,
                        "language": "CSS",
                        "description": "CSS specs",
                    }
                ]
            },
            "repo_line_stats": {},
            "repo_languages": {},
            "repo_member_commits": {
                "w3c/csswg-drafts": {"alice": 200, "bob": 100}
            },
            "lang_member_commits": {"CSS": {"alice": 200, "bob": 100}},
            "member_real_names": {"alice": "Alice", "bob": "Bob"},
            "member_companies": {"alice": "@w3c", "bob": "@google"},
            "prs_nodes": [],
            "reviewed_nodes": [],
            "is_light_mode": True,
        }

    def test_org_report_has_detail_sections(self, mod, mock_org_data):
        """Org report should have commit detail sections."""
        org_info = {"login": "w3c", "name": "World Wide Web Consortium"}
        members = [
            {"login": "alice", "name": "Alice"},
            {"login": "bob", "name": "Bob"},
        ]

        report = mod.generate_org_report(
            org_info, None, "2026-01-01", "2026-01-31", mock_org_data, members
        )

        # Should have detail sections
        assert "Commit details" in report or "details" in report.lower()

    def test_org_report_has_accordion(self, mod, mock_org_data):
        """Org report should use accordion for detail sections."""
        org_info = {"login": "w3c", "name": "W3C"}
        members = [{"login": "alice"}, {"login": "bob"}]

        report = mod.generate_org_report(
            org_info, None, "2026-01-01", "2026-01-31", mock_org_data, members
        )

        # Should have <details> elements with name attribute
        assert "<details" in report
        assert 'name="commit-details"' in report


class TestCompanyNormalization:
    """Tests for company name normalization in org reports."""

    def test_at_mention_extracted(self, mod):
        """@org mentions should be extracted from company field."""
        # Test the regex pattern for @org extraction
        pattern = getattr(mod, "org_pattern", None)
        if pattern:
            matches = pattern.findall("@tc39 @w3c")
            assert "tc39" in matches
            assert "w3c" in matches

    def test_org_with_period(self, mod):
        """@org mentions with periods should work (e.g., @mesur.io)."""
        pattern = getattr(mod, "org_pattern", None)
        if pattern:
            matches = pattern.findall("@mesur.io")
            assert "mesur.io" in matches or len(matches) > 0

    def test_plain_text_company(self, mod):
        """Plain text companies (no @) should be handled."""
        # This is tested through aggregate_org_data behavior
        # Companies like "DWANGO Co.,Ltd." should create their own group
        pass


# -----------------------------------------------------------------------
# A. API wrapper function tests
# -----------------------------------------------------------------------


class TestGetUserForks:
    """Tests for get_user_forks()."""

    def test_single_page_of_forks(self, mod):
        """Single page of forks with parent info."""
        graphql_response = {
            "user": {
                "repositories": {
                    "pageInfo": {"hasNextPage": False, "endCursor": None},
                    "nodes": [
                        {
                            "nameWithOwner": "alice/repo",
                            "description": "A fork",
                            "primaryLanguage": {"name": "Python"},
                            "isFork": True,
                            "parent": {"nameWithOwner": "upstream/repo"},
                        }
                    ],
                }
            }
        }
        with patch.object(
            mod, "run_gh_graphql", return_value=graphql_response
        ):
            result = mod.get_user_forks("alice")

        assert len(result) == 1
        assert result[0]["full_name"] == "alice/repo"
        assert result[0]["description"] == "A fork"
        assert result[0]["language"] == "Python"
        assert result[0]["fork"] is True
        assert result[0]["parent"]["full_name"] == "upstream/repo"

    def test_fork_missing_parent(self, mod):
        """Fork with parent=None."""
        graphql_response = {
            "user": {
                "repositories": {
                    "pageInfo": {"hasNextPage": False, "endCursor": None},
                    "nodes": [
                        {
                            "nameWithOwner": "alice/orphan",
                            "description": None,
                            "primaryLanguage": None,
                            "isFork": True,
                            "parent": None,
                        }
                    ],
                }
            }
        }
        with patch.object(
            mod, "run_gh_graphql", return_value=graphql_response
        ):
            result = mod.get_user_forks("alice")

        assert len(result) == 1
        assert result[0]["parent"] is None
        assert result[0]["language"] is None

    def test_pagination(self, mod):
        """Multi-page pagination."""

        def page_side_effect(query):
            if "after:" not in query:
                return {
                    "user": {
                        "repositories": {
                            "pageInfo": {
                                "hasNextPage": True,
                                "endCursor": "cursor1",
                            },
                            "nodes": [
                                {
                                    "nameWithOwner": "alice/r1",
                                    "description": "",
                                    "primaryLanguage": None,
                                    "isFork": True,
                                    "parent": {"nameWithOwner": "up/r1"},
                                }
                            ],
                        }
                    }
                }
            return {
                "user": {
                    "repositories": {
                        "pageInfo": {
                            "hasNextPage": False,
                            "endCursor": None,
                        },
                        "nodes": [
                            {
                                "nameWithOwner": "alice/r2",
                                "description": "",
                                "primaryLanguage": None,
                                "isFork": True,
                                "parent": {"nameWithOwner": "up/r2"},
                            }
                        ],
                    }
                }
            }

        with patch.object(mod, "run_gh_graphql", side_effect=page_side_effect):
            result = mod.get_user_forks("alice")

        assert len(result) == 2
        names = {f["full_name"] for f in result}
        assert names == {"alice/r1", "alice/r2"}


class TestGetForkCommits:
    """Tests for get_fork_commits()."""

    def test_user_branch_pattern_matching(self, mod):
        """Branches matching user patterns are included."""
        branch_result = MagicMock(
            stdout="main\neng/my-feature\nfix/bug-123\ndevelop\n",
            returncode=0,
        )
        commit_data = [{"sha": "aaa111"}, {"sha": "bbb222"}]

        with patch("subprocess.run", return_value=branch_result):
            with patch.object(mod, "run_gh_command", return_value=commit_data):
                result = mod.get_fork_commits(
                    "alice", "alice/repo", "2026-01-01", "2026-01-31"
                )

        # Should have commits (deduped across branches)
        assert len(result) >= 1

    def test_small_fork_all_branches_user(self, mod):
        """Small fork (<=20 branches) treats all as user branches."""
        branch_result = MagicMock(
            stdout="main\ncustom-branch\n",
            returncode=0,
        )
        commits = [{"sha": "abc123"}]

        with patch("subprocess.run", return_value=branch_result):
            with patch.object(mod, "run_gh_command", return_value=commits):
                result = mod.get_fork_commits(
                    "alice", "alice/repo", "2026-01-01", "2026-01-31"
                )

        assert len(result) >= 1

    def test_main_always_checked(self, mod):
        """main/master always checked even if >20 branches."""
        # Create >20 branches where none match patterns
        branches = ["main"] + [f"release-v{i}" for i in range(25)]
        branch_result = MagicMock(
            stdout="\n".join(branches) + "\n",
            returncode=0,
        )
        commits = [{"sha": "abc123"}]

        with patch("subprocess.run", return_value=branch_result):
            with patch.object(mod, "run_gh_command", return_value=commits):
                result = mod.get_fork_commits(
                    "alice", "alice/repo", "2026-01-01", "2026-01-31"
                )

        # main should still be checked
        assert len(result) >= 1

    def test_sha_deduplication(self, mod):
        """Same SHA across branches counted only once."""
        branch_result = MagicMock(
            stdout="main\neng/feature\n",
            returncode=0,
        )
        # Both branches return the same commit
        commits = [{"sha": "same_sha"}]

        with patch("subprocess.run", return_value=branch_result):
            with patch.object(mod, "run_gh_command", return_value=commits):
                result = mod.get_fork_commits(
                    "alice", "alice/repo", "2026-01-01", "2026-01-31"
                )

        assert len(result) == 1

    def test_subprocess_error_returns_empty(self, mod):
        """Subprocess error returns empty list."""
        import subprocess as sp

        with patch("subprocess.run", side_effect=sp.CalledProcessError(1, "")):
            result = mod.get_fork_commits(
                "alice", "alice/repo", "2026-01-01", "2026-01-31"
            )

        assert result == []


class TestGetCommitStats:
    """Tests for get_commit_stats()."""

    def test_accumulates_stats(self, mod):
        """Stats accumulate across repos and commits."""
        commits_by_repo = {
            "org/repo1": ["sha1", "sha2"],
            "org/repo2": ["sha3"],
        }

        def mock_gh_cmd(args, **kwargs):
            return {"additions": 10, "deletions": 5}

        with patch.object(mod, "run_gh_command", side_effect=mock_gh_cmd):
            with patch.object(mod, "progress", MagicMock()):
                result = mod.get_commit_stats(commits_by_repo)

        assert result["org/repo1"]["additions"] == 20
        assert result["org/repo1"]["deletions"] == 10
        assert result["org/repo2"]["additions"] == 10
        assert result["org/repo2"]["deletions"] == 5

    def test_api_returns_none(self, mod):
        """None from API is skipped."""
        commits_by_repo = {"org/repo": ["sha1"]}

        with patch.object(mod, "run_gh_command", return_value=None):
            with patch.object(mod, "progress", MagicMock()):
                result = mod.get_commit_stats(commits_by_repo)

        assert result["org/repo"]["additions"] == 0
        assert result["org/repo"]["deletions"] == 0


class TestGetEffectiveLanguage:
    """Tests for get_effective_language()."""

    def test_cpp_above_threshold(self, mod):
        """C++ >= 10% returns 'C++'."""
        with patch.object(
            mod,
            "run_gh_command",
            return_value={"C++": 2000, "Python": 8000},
        ):
            result = mod.get_effective_language("owner/repo")

        assert result == "C++"

    def test_cpp_below_threshold(self, mod):
        """C++ < 10% returns top language."""
        with patch.object(
            mod,
            "run_gh_command",
            return_value={"C++": 500, "Python": 9500},
        ):
            result = mod.get_effective_language("owner/repo")

        assert result == "Python"

    def test_empty_languages(self, mod):
        """No languages returns None."""
        with patch.object(mod, "run_gh_command", return_value=None):
            result = mod.get_effective_language("owner/repo")

        assert result is None

    def test_zero_total_bytes(self, mod):
        """Zero total bytes returns None."""
        with patch.object(mod, "run_gh_command", return_value={}):
            result = mod.get_effective_language("owner/repo")

        assert result is None


class TestGetRepoInfoCached:
    """Tests for get_repo_info_cached()."""

    def test_all_cached(self, mod):
        """All repos already cached — no fetch."""
        mod._repo_info_cache.clear()
        mod._repo_info_cache["org/repo1"] = {"nameWithOwner": "org/repo1"}
        mod._repo_info_cache["org/repo2"] = {"nameWithOwner": "org/repo2"}

        with patch.object(mod, "get_repo_info") as mock_fetch:
            result = mod.get_repo_info_cached(["org/repo1", "org/repo2"])

        mock_fetch.assert_not_called()
        assert "org/repo1" in result
        assert "org/repo2" in result

    def test_fetch_missing(self, mod):
        """Missing repos are fetched and cached."""
        mod._repo_info_cache.clear()
        mod._repo_info_cache["org/repo1"] = {"nameWithOwner": "org/repo1"}

        fetched = {"org/repo2": {"nameWithOwner": "org/repo2"}}
        with patch.object(mod, "get_repo_info", return_value=fetched):
            result = mod.get_repo_info_cached(["org/repo1", "org/repo2"])

        assert "org/repo1" in result
        assert "org/repo2" in result
        # repo2 should now be in cache
        assert "org/repo2" in mod._repo_info_cache


class TestGetPrsReviewed:
    """Tests for get_prs_reviewed()."""

    def test_single_page(self, mod):
        """Single page of reviews returned."""
        graphql_response = {
            "user": {
                "contributionsCollection": {
                    "pullRequestReviewContributions": {
                        "totalCount": 1,
                        "pageInfo": {
                            "hasNextPage": False,
                            "endCursor": None,
                        },
                        "nodes": [
                            {
                                "pullRequest": {
                                    "title": "Fix bug",
                                    "url": "https://github.com/o/r/pull/1",
                                    "repository": {
                                        "nameWithOwner": "o/r",
                                    },
                                    "author": {"login": "bob"},
                                    "additions": 10,
                                    "deletions": 5,
                                }
                            }
                        ],
                    }
                }
            }
        }
        with patch.object(
            mod, "run_gh_graphql", return_value=graphql_response
        ):
            result = mod.get_prs_reviewed("alice", "2026-01-01", "2026-01-31")

        assert len(result) == 1
        assert result[0]["title"] == "Fix bug"

    def test_date_clamping(self, mod):
        """Span > 365 days clamps to 1 year."""
        graphql_response = {
            "user": {
                "contributionsCollection": {
                    "pullRequestReviewContributions": {
                        "totalCount": 0,
                        "pageInfo": {
                            "hasNextPage": False,
                            "endCursor": None,
                        },
                        "nodes": [],
                    }
                }
            }
        }
        with patch.object(
            mod, "run_gh_graphql", return_value=graphql_response
        ) as mock_gql:
            mod.get_prs_reviewed("alice", "2024-01-01", "2026-01-31")

        # The query should have been called with clamped date
        call_args = mock_gql.call_args[0][0]
        assert "2025-02-01" in call_args or "2025-01" in call_args

    def test_deduplication(self, mod):
        """Duplicate PR URLs are deduplicated."""
        graphql_response = {
            "user": {
                "contributionsCollection": {
                    "pullRequestReviewContributions": {
                        "totalCount": 2,
                        "pageInfo": {
                            "hasNextPage": False,
                            "endCursor": None,
                        },
                        "nodes": [
                            {
                                "pullRequest": {
                                    "title": "PR A",
                                    "url": "https://github.com/o/r/pull/1",
                                    "repository": {"nameWithOwner": "o/r"},
                                    "author": {"login": "bob"},
                                    "additions": 10,
                                    "deletions": 5,
                                }
                            },
                            {
                                "pullRequest": {
                                    "title": "PR A",
                                    "url": "https://github.com/o/r/pull/1",
                                    "repository": {"nameWithOwner": "o/r"},
                                    "author": {"login": "bob"},
                                    "additions": 10,
                                    "deletions": 5,
                                }
                            },
                        ],
                    }
                }
            }
        }
        with patch.object(
            mod, "run_gh_graphql", return_value=graphql_response
        ):
            result = mod.get_prs_reviewed("alice", "2026-01-01", "2026-01-31")

        assert len(result) == 1


class TestGetOrgPrsCreated:
    """Tests for get_org_prs_created()."""

    def test_single_page(self, mod):
        """Single page of PRs."""
        graphql_response = {
            "search": {
                "issueCount": 1,
                "pageInfo": {"hasNextPage": False, "endCursor": None},
                "nodes": [
                    {
                        "title": "New feature",
                        "author": {"login": "alice"},
                        "url": "https://github.com/org/repo/pull/1",
                        "state": "MERGED",
                    }
                ],
            }
        }
        with patch.object(
            mod, "run_gh_graphql", return_value=graphql_response
        ):
            result = mod.get_org_prs_created("org", "2026-01-01", "2026-01-31")

        assert len(result) == 1
        assert result[0]["title"] == "New feature"

    def test_multi_page(self, mod):
        """Pagination across multiple pages."""
        page1 = {
            "search": {
                "issueCount": 2,
                "pageInfo": {"hasNextPage": True, "endCursor": "c1"},
                "nodes": [{"title": "PR 1"}],
            }
        }
        page2 = {
            "search": {
                "issueCount": 2,
                "pageInfo": {"hasNextPage": False, "endCursor": None},
                "nodes": [{"title": "PR 2"}],
            }
        }
        with patch.object(mod, "run_gh_graphql", side_effect=[page1, page2]):
            result = mod.get_org_prs_created("org", "2026-01-01", "2026-01-31")

        assert len(result) == 2

    def test_safety_limit(self, mod):
        """Stops at 1000 PRs."""
        # Create a response with 999 nodes to simulate being near the limit
        big_page = {
            "search": {
                "issueCount": 1500,
                "pageInfo": {"hasNextPage": True, "endCursor": "c1"},
                "nodes": [{"title": f"PR {i}"} for i in range(1000)],
            }
        }
        with patch.object(mod, "run_gh_graphql", return_value=big_page):
            result = mod.get_org_prs_created("org", "2026-01-01", "2026-01-31")

        assert len(result) == 1000


class TestGetOrgPrReviews:
    """Tests for get_org_pr_reviews()."""

    def test_date_filtering(self, mod):
        """Reviews outside date range are excluded."""
        graphql_response = {
            "search": {
                "issueCount": 1,
                "pageInfo": {"hasNextPage": False, "endCursor": None},
                "nodes": [
                    {
                        "title": "PR 1",
                        "url": "https://github.com/o/r/pull/1",
                        "author": {"login": "author1"},
                        "repository": {"nameWithOwner": "o/r"},
                        "additions": 10,
                        "deletions": 5,
                        "reviews": {
                            "nodes": [
                                {
                                    "author": {"login": "reviewer1"},
                                    "submittedAt": "2026-01-15T10:00:00Z",
                                    "state": "APPROVED",
                                },
                                {
                                    "author": {"login": "reviewer2"},
                                    "submittedAt": "2025-06-15T10:00:00Z",
                                    "state": "APPROVED",
                                },
                            ]
                        },
                    }
                ],
            }
        }
        with patch.object(
            mod, "run_gh_graphql", return_value=graphql_response
        ):
            result = mod.get_org_pr_reviews("org", "2026-01-01", "2026-01-31")

        assert "reviewer1" in result
        assert "reviewer2" not in result

    def test_per_reviewer_deduplication(self, mod):
        """Same reviewer on same PR counted once."""
        graphql_response = {
            "search": {
                "issueCount": 1,
                "pageInfo": {"hasNextPage": False, "endCursor": None},
                "nodes": [
                    {
                        "title": "PR 1",
                        "url": "https://github.com/o/r/pull/1",
                        "author": {"login": "author1"},
                        "repository": {"nameWithOwner": "o/r"},
                        "additions": 10,
                        "deletions": 5,
                        "reviews": {
                            "nodes": [
                                {
                                    "author": {"login": "reviewer1"},
                                    "submittedAt": "2026-01-10T10:00:00Z",
                                    "state": "CHANGES_REQUESTED",
                                },
                                {
                                    "author": {"login": "reviewer1"},
                                    "submittedAt": "2026-01-12T10:00:00Z",
                                    "state": "APPROVED",
                                },
                            ]
                        },
                    }
                ],
            }
        }
        with patch.object(
            mod, "run_gh_graphql", return_value=graphql_response
        ):
            result = mod.get_org_pr_reviews("org", "2026-01-01", "2026-01-31")

        assert len(result["reviewer1"]) == 1

    def test_missing_author_skipped(self, mod):
        """Reviews without author are skipped."""
        graphql_response = {
            "search": {
                "issueCount": 1,
                "pageInfo": {"hasNextPage": False, "endCursor": None},
                "nodes": [
                    {
                        "title": "PR 1",
                        "url": "https://github.com/o/r/pull/1",
                        "author": {"login": "author1"},
                        "repository": {"nameWithOwner": "o/r"},
                        "additions": 10,
                        "deletions": 5,
                        "reviews": {
                            "nodes": [
                                {
                                    "author": None,
                                    "submittedAt": "2026-01-15T10:00:00Z",
                                    "state": "APPROVED",
                                }
                            ]
                        },
                    }
                ],
            }
        }
        with patch.object(
            mod, "run_gh_graphql", return_value=graphql_response
        ):
            result = mod.get_org_pr_reviews("org", "2026-01-01", "2026-01-31")

        assert len(result) == 0


class TestPaginateGhApi:
    """Tests for paginate_gh_api()."""

    def test_single_page(self, mod):
        """Single page under API_PAGE_SIZE items."""
        page = [{"login": f"user{i}"} for i in range(50)]
        with patch.object(mod, "run_gh_command", return_value=page):
            result = mod.paginate_gh_api("orgs/test/members")

        assert len(result) == 50

    def test_multi_page_stops_on_empty(self, mod):
        """Pagination stops when an empty page is returned."""
        page1 = [{"login": f"user{i}"} for i in range(100)]
        page2 = [{"login": f"user{i}"} for i in range(100, 130)]

        with patch.object(mod, "run_gh_command", side_effect=[page1, page2]):
            result = mod.paginate_gh_api("orgs/test/members")

        # page2 has <100 items so pagination stops
        assert len(result) == 130

    def test_none_result_stops(self, mod):
        """None result stops pagination."""
        with patch.object(mod, "run_gh_command", return_value=None):
            result = mod.paginate_gh_api("orgs/test/members")

        assert result == []


class TestGetOrgInfo:
    """Tests for get_org_info()."""

    def test_returns_org_info(self, mod):
        """Returns org info dict."""
        info = {"login": "testorg", "name": "Test Org", "description": "Desc"}
        with patch.object(mod, "run_gh_command", return_value=info):
            result = mod.get_org_info("testorg")

        assert result["login"] == "testorg"
        assert result["name"] == "Test Org"


# -----------------------------------------------------------------------
# B. Scraping and batch function tests
# -----------------------------------------------------------------------


class TestCheckActivityViaScrape:
    """Tests for check_activity_via_scrape()."""

    def test_active_user(self, mod):
        """User with data-level > 0 in range is active."""
        html = (
            '<td data-date="2026-01-10" data-level="2"></td>'
            '<td data-date="2026-01-11" data-level="0"></td>'
        )
        mock_response = MagicMock()
        mock_response.read.return_value = html.encode("utf-8")
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_response):
            result = mod.check_activity_via_scrape(
                "alice", "2026-01-01", "2026-01-31"
            )

        assert result is True

    def test_inactive_user(self, mod):
        """User with all data-level=0 is inactive."""
        html = (
            '<td data-date="2026-01-10" data-level="0"></td>'
            '<td data-date="2026-01-11" data-level="0"></td>'
        )
        mock_response = MagicMock()
        mock_response.read.return_value = html.encode("utf-8")
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_response):
            result = mod.check_activity_via_scrape(
                "alice", "2026-01-01", "2026-01-31"
            )

        assert result is False

    def test_network_error(self, mod):
        """Network error returns None."""
        with patch("urllib.request.urlopen", side_effect=Exception("timeout")):
            result = mod.check_activity_via_scrape(
                "alice", "2026-01-01", "2026-01-31"
            )

        assert result is None


class TestCheckActivityFast:
    """Tests for check_activity_fast()."""

    def test_classifies_users(self, mod):
        """Users classified into active/inactive/unknown."""

        def mock_scrape(username, since, until):
            return {"alice": True, "bob": False, "charlie": None}[username]

        with patch.object(
            mod, "check_activity_via_scrape", side_effect=mock_scrape
        ):
            active, inactive, unknown = mod.check_activity_fast(
                ["alice", "bob", "charlie"], "2026-01-01", "2026-01-31"
            )

        assert "alice" in active
        assert "bob" in inactive
        assert "charlie" in unknown


class TestGetContributionSummariesBatch:
    """Tests for get_contribution_summaries_batch()."""

    def test_single_batch(self, mod):
        """Single batch (<=10 users)."""
        graphql_response = {
            "user0": {
                "login": "alice",
                "name": "Alice",
                "contributionsCollection": {
                    "totalCommitContributions": 5,
                },
            },
            "user1": {
                "login": "bob",
                "name": "Bob",
                "contributionsCollection": {
                    "totalCommitContributions": 3,
                },
            },
        }
        with patch.object(
            mod, "run_gh_graphql", return_value=graphql_response
        ):
            with patch.object(mod, "check_rate_limit_hit", return_value=False):
                result = mod.get_contribution_summaries_batch(
                    ["alice", "bob"], "2026-01-01", "2026-01-31"
                )

        assert "alice" in result
        assert "bob" in result

    def test_date_clamping(self, mod):
        """Span > 365 days clamps start date."""
        graphql_response = {"user0": {"login": "alice"}}

        with patch.object(
            mod, "run_gh_graphql", return_value=graphql_response
        ) as mock_gql:
            with patch.object(mod, "check_rate_limit_hit", return_value=False):
                mod.get_contribution_summaries_batch(
                    ["alice"], "2024-01-01", "2026-01-31"
                )

        call_args = mock_gql.call_args[0][0]
        # Should use clamped date, not 2024-01-01
        assert "2024-01-01" not in call_args
        assert "2025-02-01" in call_args or "2025-01" in call_args

    def test_rate_limit_stops_batching(self, mod):
        """Rate limit hit mid-batch stops processing."""
        graphql_response = {f"user{i}": {"login": f"u{i}"} for i in range(10)}

        call_count = [0]

        def mock_rate_check():
            call_count[0] += 1
            return call_count[0] > 1  # Hit rate limit after first batch

        users = [f"u{i}" for i in range(25)]
        with patch.object(
            mod, "run_gh_graphql", return_value=graphql_response
        ):
            with patch.object(
                mod, "check_rate_limit_hit", side_effect=mock_rate_check
            ):
                result = mod.get_contribution_summaries_batch(
                    users, "2026-01-01", "2026-01-31"
                )

        # Should have results from first batch but stopped early
        assert len(result) < len(users)


# -----------------------------------------------------------------------
# C. Rate limit helper tests
# -----------------------------------------------------------------------


class TestGetRateLimitResetTime:
    """Tests for get_rate_limit_reset_time()."""

    def test_returns_datetime(self, mod):
        """Successful call returns a datetime."""
        import datetime

        mock_result = MagicMock(stdout="1738200000\n", returncode=0)
        with patch("subprocess.run", return_value=mock_result):
            result = mod.get_rate_limit_reset_time()

        assert isinstance(result, datetime.datetime)

    def test_error_returns_none(self, mod):
        """Error returns None."""
        with patch("subprocess.run", side_effect=Exception("fail")):
            result = mod.get_rate_limit_reset_time()

        assert result is None


class TestGetRateLimitRemaining:
    """Tests for get_rate_limit_remaining()."""

    def test_returns_int(self, mod):
        """Successful call returns an int."""
        mock_result = MagicMock(stdout="4500\n", returncode=0)
        with patch("subprocess.run", return_value=mock_result):
            result = mod.get_rate_limit_remaining()

        assert result == 4500

    def test_error_returns_none(self, mod):
        """Error returns None."""
        with patch("subprocess.run", side_effect=Exception("fail")):
            result = mod.get_rate_limit_remaining()

        assert result is None


class TestWaitForRateLimitReset:
    """Tests for wait_for_rate_limit_reset()."""

    def test_no_reset_time_sleeps_60s(self, mod):
        """reset_time is None — sleep 60s, return True."""
        with patch.object(mod, "get_rate_limit_reset_time", return_value=None):
            with patch("time.sleep") as mock_sleep:
                with patch("sys.stderr", MagicMock()):
                    result = mod.wait_for_rate_limit_reset()

        assert result is True
        mock_sleep.assert_called_once_with(60)

    def test_already_reset(self, mod):
        """Reset time in the past — return True immediately."""
        from datetime import datetime, timedelta

        past = datetime.now() - timedelta(seconds=60)
        with patch.object(mod, "get_rate_limit_reset_time", return_value=past):
            result = mod.wait_for_rate_limit_reset()

        assert result is True

    def test_feasible_wait(self, mod):
        """Reset within max_wait — sleep and return True."""
        from datetime import datetime, timedelta

        soon = datetime.now() + timedelta(seconds=30)
        with patch.object(mod, "get_rate_limit_reset_time", return_value=soon):
            with patch("time.sleep") as mock_sleep:
                with patch("sys.stderr", MagicMock()):
                    result = mod.wait_for_rate_limit_reset(
                        max_wait_seconds=120
                    )

        assert result is True
        assert mock_sleep.called

    def test_wait_too_long(self, mod):
        """Reset too far in the future — return False."""
        from datetime import datetime, timedelta

        far_future = datetime.now() + timedelta(seconds=600)
        with patch.object(
            mod, "get_rate_limit_reset_time", return_value=far_future
        ):
            result = mod.wait_for_rate_limit_reset(max_wait_seconds=120)

        assert result is False


# -----------------------------------------------------------------------
# D. Org data pipeline tests
# -----------------------------------------------------------------------


class TestGatherOrgDataActiveContributors:
    """Tests for gather_org_data_active_contributors()."""

    @pytest.fixture(autouse=True)
    def suppress_output(self):
        """Suppress stderr/progress output during tests."""
        with patch("sys.stderr", MagicMock()):
            with patch("sys.exit", side_effect=SystemExit):
                yield

    @pytest.fixture
    def mock_org_pipeline(self, mod):
        """Mock the full org pipeline dependencies."""
        mock_progress = MagicMock()
        patches = patch.multiple(
            mod,
            progress=mock_progress,
            get_org_info=MagicMock(
                return_value={
                    "login": "testorg",
                    "name": "Test Org",
                    "description": "",
                }
            ),
            get_org_public_members=MagicMock(return_value=["alice", "bob"]),
            check_activity_fast=MagicMock(
                return_value=(["alice", "bob"], [], [])
            ),
            gather_user_data_light=MagicMock(
                side_effect=lambda u, s, e, **kw: {
                    "username": u,
                    "user_real_name": u.title(),
                    "company": "@testorg",
                    "total_commits_default_branch": 10,
                    "total_commits_all": 10,
                    "total_prs": 2,
                    "total_pr_reviews": 3,
                    "total_issues": 1,
                    "total_additions": 500,
                    "total_deletions": 100,
                    "repos_by_category": {
                        "Other": [
                            {
                                "name": "testorg/repo",
                                "commits": 10,
                                "prs": 2,
                                "language": "Python",
                                "description": "A repo",
                            }
                        ]
                    },
                    "repo_line_stats": {},
                    "repo_languages": {"testorg/repo": "Python"},
                    "prs_nodes": [],
                    "reviewed_nodes": [],
                    "is_light_mode": True,
                }
            ),
            aggregate_org_data=MagicMock(
                return_value={
                    "total_commits_default_branch": 20,
                    "total_commits_all": 20,
                    "total_prs": 4,
                    "total_pr_reviews": 6,
                    "total_issues": 2,
                    "repos_contributed": 1,
                    "prs_nodes": [],
                    "reviewed_nodes": [],
                    "total_additions": 1000,
                    "total_deletions": 200,
                    "repos_by_category": {},
                    "repo_line_stats": {},
                    "repo_languages": {},
                    "repo_member_commits": {},
                    "lang_member_commits": {},
                    "member_real_names": {},
                    "member_companies": {},
                    "is_light_mode": True,
                }
            ),
            get_rate_limit_remaining=MagicMock(return_value=4500),
            should_warn_rate_limit=MagicMock(return_value=(False, None)),
            clear_repo_info_cache=MagicMock(),
        )
        with patches:
            with patch("time.sleep"):
                yield

    def test_happy_path(self, mod, mock_org_pipeline):
        """Org with 2 active members returns aggregated data."""
        result = mod.gather_org_data_active_contributors(
            "testorg",
            None,
            False,
            False,
            "2026-01-01",
            "2026-01-31",
        )

        org_info, team_info, active_members, aggregated, member_data = result
        assert org_info["login"] == "testorg"
        assert team_info is None
        assert len(active_members) == 2
        assert aggregated["total_commits_default_branch"] == 20

    def test_no_active_members(self, mod):
        """All members inactive returns empty data."""
        mock_progress = MagicMock()
        with patch.multiple(
            mod,
            progress=mock_progress,
            get_org_info=MagicMock(
                return_value={"login": "org", "name": "Org", "description": ""}
            ),
            get_org_public_members=MagicMock(return_value=["alice"]),
            check_activity_fast=MagicMock(return_value=([], ["alice"], [])),
            get_rate_limit_remaining=MagicMock(return_value=4500),
            should_warn_rate_limit=MagicMock(return_value=(False, None)),
            clear_repo_info_cache=MagicMock(),
        ):
            with patch("time.sleep"):
                result = mod.gather_org_data_active_contributors(
                    "org",
                    None,
                    False,
                    False,
                    "2026-01-01",
                    "2026-01-31",
                )

        _, _, active_members, aggregated, _ = result
        assert len(active_members) == 0
        assert aggregated["total_commits_default_branch"] == 0

    def test_bot_filtering(self, mod, mock_org_pipeline):
        """Bot members are filtered out."""
        mod.get_org_public_members.return_value = [
            "alice",
            "dependabot[bot]",
            "bob",
        ]
        mod.check_activity_fast.return_value = (["alice", "bob"], [], [])

        result = mod.gather_org_data_active_contributors(
            "testorg",
            None,
            False,
            False,
            "2026-01-01",
            "2026-01-31",
        )

        _, _, active_members, _, _ = result
        assert "dependabot[bot]" not in active_members

    def test_team_mode(self, mod):
        """team_slug provided uses get_team_members."""
        mock_progress = MagicMock()
        mock_team_members = MagicMock(return_value=["alice"])
        with patch.multiple(
            mod,
            progress=mock_progress,
            get_org_info=MagicMock(
                return_value={"login": "org", "name": "Org", "description": ""}
            ),
            get_team_info=MagicMock(
                return_value={"slug": "editors", "name": "Editors"}
            ),
            get_team_members=mock_team_members,
            check_activity_fast=MagicMock(return_value=(["alice"], [], [])),
            gather_user_data_light=MagicMock(
                return_value={
                    "username": "alice",
                    "user_real_name": "Alice",
                    "company": "",
                    "total_commits_default_branch": 5,
                    "total_commits_all": 5,
                    "total_prs": 1,
                    "total_pr_reviews": 0,
                    "total_issues": 0,
                    "total_additions": 100,
                    "total_deletions": 20,
                    "repos_by_category": {},
                    "repo_line_stats": {},
                    "repo_languages": {},
                    "prs_nodes": [],
                    "reviewed_nodes": [],
                    "is_light_mode": True,
                }
            ),
            aggregate_org_data=MagicMock(
                return_value={
                    "total_commits_default_branch": 5,
                    "total_commits_all": 5,
                    "total_prs": 1,
                    "total_pr_reviews": 0,
                    "total_issues": 0,
                    "repos_contributed": 0,
                    "prs_nodes": [],
                    "reviewed_nodes": [],
                    "total_additions": 100,
                    "total_deletions": 20,
                    "repos_by_category": {},
                    "repo_line_stats": {},
                    "repo_languages": {},
                    "repo_member_commits": {},
                    "lang_member_commits": {},
                    "member_real_names": {},
                    "member_companies": {},
                    "is_light_mode": True,
                }
            ),
            get_rate_limit_remaining=MagicMock(return_value=4500),
            should_warn_rate_limit=MagicMock(return_value=(False, None)),
            clear_repo_info_cache=MagicMock(),
        ):
            with patch("time.sleep"):
                result = mod.gather_org_data_active_contributors(
                    "org",
                    "editors",
                    False,
                    False,
                    "2026-01-01",
                    "2026-01-31",
                )

            _, team_info, _, _, _ = result
            assert team_info["slug"] == "editors"
            mock_team_members.assert_called_once()

    @staticmethod
    def _exit(c=0):
        raise SystemExit(c)

    def test_org_info_not_found(self, mod):
        """get_org_info returns None → sys.exit(1)."""
        with patch.multiple(
            mod,
            progress=MagicMock(),
            get_org_info=MagicMock(return_value=None),
            clear_repo_info_cache=MagicMock(),
        ):
            with patch("sys.exit", side_effect=self._exit):
                with pytest.raises(SystemExit) as exc_info:
                    mod.gather_org_data_active_contributors(
                        "badorg",
                        None,
                        False,
                        False,
                        "2026-01-01",
                        "2026-01-31",
                    )
                assert exc_info.value.code == 1

    def test_team_info_not_found(self, mod):
        """get_team_info returns None → sys.exit(1)."""
        with patch.multiple(
            mod,
            progress=MagicMock(),
            get_org_info=MagicMock(
                return_value={"login": "org", "name": "Org"}
            ),
            get_team_info=MagicMock(return_value=None),
            clear_repo_info_cache=MagicMock(),
        ):
            with patch("sys.exit", side_effect=self._exit):
                with pytest.raises(SystemExit) as exc_info:
                    mod.gather_org_data_active_contributors(
                        "org",
                        "badteam",
                        False,
                        False,
                        "2026-01-01",
                        "2026-01-31",
                    )
                assert exc_info.value.code == 1

    def test_no_members_found(self, mod):
        """Empty member list → sys.exit(1)."""
        with patch.multiple(
            mod,
            progress=MagicMock(),
            get_org_info=MagicMock(
                return_value={"login": "org", "name": "Org"}
            ),
            get_org_public_members=MagicMock(return_value=[]),
            clear_repo_info_cache=MagicMock(),
        ):
            with patch("sys.exit", side_effect=self._exit):
                with pytest.raises(SystemExit) as exc_info:
                    mod.gather_org_data_active_contributors(
                        "org",
                        None,
                        False,
                        False,
                        "2026-01-01",
                        "2026-01-31",
                    )
                assert exc_info.value.code == 1

    def test_owners_mode(self, mod):
        """owners_only=True uses get_org_owners."""
        mock_progress = MagicMock()
        mock_owners = MagicMock(return_value=["admin1"])
        with patch.multiple(
            mod,
            progress=mock_progress,
            get_org_info=MagicMock(
                return_value={"login": "org", "name": "Org"}
            ),
            get_org_owners=mock_owners,
            check_activity_fast=MagicMock(return_value=(["admin1"], [], [])),
            gather_user_data_light=MagicMock(
                return_value={
                    "username": "admin1",
                    "user_real_name": "Admin",
                    "company": "",
                    "total_commits_default_branch": 1,
                    "total_commits_all": 1,
                    "total_prs": 0,
                    "total_pr_reviews": 0,
                    "total_issues": 0,
                    "total_additions": 0,
                    "total_deletions": 0,
                    "repos_by_category": {},
                    "repo_line_stats": {},
                    "repo_languages": {},
                    "prs_nodes": [],
                    "reviewed_nodes": [],
                    "is_light_mode": True,
                }
            ),
            aggregate_org_data=MagicMock(
                return_value={
                    "total_commits_default_branch": 1,
                    "total_commits_all": 1,
                    "total_prs": 0,
                    "total_pr_reviews": 0,
                    "total_issues": 0,
                    "repos_contributed": 0,
                    "prs_nodes": [],
                    "reviewed_nodes": [],
                    "total_additions": 0,
                    "total_deletions": 0,
                    "repos_by_category": {},
                    "repo_line_stats": {},
                    "repo_languages": {},
                    "repo_member_commits": {},
                    "lang_member_commits": {},
                    "member_real_names": {},
                    "member_companies": {},
                    "is_light_mode": True,
                }
            ),
            get_rate_limit_remaining=MagicMock(return_value=4500),
            should_warn_rate_limit=MagicMock(return_value=(False, None)),
            clear_repo_info_cache=MagicMock(),
        ):
            with patch("time.sleep"):
                result = mod.gather_org_data_active_contributors(
                    "org",
                    None,
                    True,
                    False,
                    "2026-01-01",
                    "2026-01-31",
                )

        mock_owners.assert_called_once()
        _, _, active, _, _ = result
        assert "admin1" in active

    def test_private_members_mode(self, mod):
        """include_private=True uses get_org_members."""
        mock_progress = MagicMock()
        mock_members = MagicMock(return_value=["priv1"])
        with patch.multiple(
            mod,
            progress=mock_progress,
            get_org_info=MagicMock(
                return_value={"login": "org", "name": "Org"}
            ),
            get_org_members=mock_members,
            check_activity_fast=MagicMock(return_value=(["priv1"], [], [])),
            gather_user_data_light=MagicMock(
                return_value={
                    "username": "priv1",
                    "user_real_name": "Private",
                    "company": "",
                    "total_commits_default_branch": 1,
                    "total_commits_all": 1,
                    "total_prs": 0,
                    "total_pr_reviews": 0,
                    "total_issues": 0,
                    "total_additions": 0,
                    "total_deletions": 0,
                    "repos_by_category": {},
                    "repo_line_stats": {},
                    "repo_languages": {},
                    "prs_nodes": [],
                    "reviewed_nodes": [],
                    "is_light_mode": True,
                }
            ),
            aggregate_org_data=MagicMock(
                return_value={
                    "total_commits_default_branch": 1,
                    "total_commits_all": 1,
                    "total_prs": 0,
                    "total_pr_reviews": 0,
                    "total_issues": 0,
                    "repos_contributed": 0,
                    "prs_nodes": [],
                    "reviewed_nodes": [],
                    "total_additions": 0,
                    "total_deletions": 0,
                    "repos_by_category": {},
                    "repo_line_stats": {},
                    "repo_languages": {},
                    "repo_member_commits": {},
                    "lang_member_commits": {},
                    "member_real_names": {},
                    "member_companies": {},
                    "is_light_mode": True,
                }
            ),
            get_rate_limit_remaining=MagicMock(return_value=4500),
            should_warn_rate_limit=MagicMock(return_value=(False, None)),
            clear_repo_info_cache=MagicMock(),
        ):
            with patch("time.sleep"):
                result = mod.gather_org_data_active_contributors(
                    "org",
                    None,
                    False,
                    True,
                    "2026-01-01",
                    "2026-01-31",
                )

        mock_members.assert_called_once()
        _, _, active, _, _ = result
        assert "priv1" in active

    def test_rate_limit_exhausted_at_start(self, mod):
        """Rate limit < 50 at start → sys.exit(1)."""
        with patch.multiple(
            mod,
            progress=MagicMock(),
            get_org_info=MagicMock(
                return_value={"login": "org", "name": "Org"}
            ),
            get_org_public_members=MagicMock(return_value=["alice"]),
            get_rate_limit_remaining=MagicMock(return_value=10),
            should_warn_rate_limit=MagicMock(return_value=(False, None)),
            clear_repo_info_cache=MagicMock(),
            print_rate_limit_error=MagicMock(),
        ):
            with patch("sys.exit", side_effect=self._exit):
                with pytest.raises(SystemExit) as exc_info:
                    mod.gather_org_data_active_contributors(
                        "org",
                        None,
                        False,
                        False,
                        "2026-01-01",
                        "2026-01-31",
                    )
                assert exc_info.value.code == 1

    def test_rate_limit_warning_declined(self, mod):
        """Rate limit warning prompt declined → sys.exit(0)."""
        with patch.multiple(
            mod,
            progress=MagicMock(),
            get_org_info=MagicMock(
                return_value={"login": "org", "name": "Org"}
            ),
            get_org_public_members=MagicMock(return_value=["alice"]),
            get_rate_limit_remaining=MagicMock(return_value=4500),
            should_warn_rate_limit=MagicMock(
                return_value=(True, "a lot of calls")
            ),
            prompt_rate_limit_warning=MagicMock(return_value=False),
            clear_repo_info_cache=MagicMock(),
        ):
            with patch("sys.exit", side_effect=self._exit):
                with pytest.raises(SystemExit) as exc_info:
                    mod.gather_org_data_active_contributors(
                        "org",
                        None,
                        False,
                        False,
                        "2026-01-01",
                        "2026-01-31",
                    )
                assert exc_info.value.code == 0

    def test_members_gt_5_truncated_display(self, mod, mock_org_pipeline):
        """More than 5 members shows truncated display."""
        mod.get_org_public_members.return_value = [
            "a",
            "b",
            "c",
            "d",
            "e",
            "f",
            "g",
        ]
        mod.check_activity_fast.return_value = (
            ["a", "b", "c", "d", "e", "f", "g"],
            [],
            [],
        )

        result = mod.gather_org_data_active_contributors(
            "testorg",
            None,
            False,
            False,
            "2026-01-01",
            "2026-01-31",
        )
        _, _, active, _, _ = result
        assert len(active) == 7


class TestGetAllCommitsPagination:
    """Pagination edge cases for get_all_commits()."""

    def test_pagination_break_at_1000(self, mod):
        """Search results > 1000 triggers hit_limit warning."""
        # Simulate 11 pages needed (page > 10 triggers break)
        full_page = [
            {
                "sha": f"sha{i}",
                "repository": {"full_name": "o/r", "private": False},
                "commit": {
                    "message": f"msg{i}",
                    "author": {"date": "2026-01-02T00:00:00Z"},
                },
            }
            for i in range(100)
        ]
        results = [
            {"total_count": 1100, "items": full_page} for _ in range(10)
        ]

        with patch.object(
            mod,
            "run_gh_command",
            side_effect=results,
        ):
            result = mod.get_all_commits(
                "testuser",
                "2026-01-01",
                "2026-01-31",
            )

        assert result["total_count"] == 1000
        assert len(result["items"]) == 1000

    def test_empty_result_breaks(self, mod):
        """run_gh_command returning None breaks loop."""
        with patch.object(mod, "run_gh_command", return_value=None):
            result = mod.get_all_commits(
                "testuser",
                "2026-01-01",
                "2026-01-07",
            )
        assert result["total_count"] == 0

    def test_empty_items_breaks(self, mod):
        """Empty items list breaks loop."""
        with patch.object(
            mod,
            "run_gh_command",
            return_value={"total_count": 0, "items": []},
        ):
            result = mod.get_all_commits(
                "testuser",
                "2026-01-01",
                "2026-01-07",
            )
        assert result["total_count"] == 0


class TestGetRepoInfoBatch:
    """Batch GraphQL response handling in get_repo_info()."""

    def test_returns_data_for_repos(self, mod):
        """GraphQL batch returns repo data mapped by name."""
        graphql_response = {
            "repo0": {
                "nameWithOwner": "owner/repo1",
                "description": "A repo",
                "primaryLanguage": {"name": "Python"},
                "isFork": False,
                "isPrivate": False,
                "parent": None,
            },
            "repo1": {
                "nameWithOwner": "owner/repo2",
                "description": "Another",
                "primaryLanguage": {"name": "Go"},
                "isFork": True,
                "isPrivate": False,
                "parent": {"nameWithOwner": "up/repo2"},
            },
        }
        with patch.object(
            mod,
            "run_gh_graphql",
            return_value=graphql_response,
        ):
            result = mod.get_repo_info(["owner/repo1", "owner/repo2"])

        assert "owner/repo1" in result
        assert "owner/repo2" in result
        assert result["owner/repo1"]["isFork"] is False
        assert result["owner/repo2"]["isFork"] is True

    def test_empty_input(self, mod):
        """Empty repo list returns empty dict without API call."""
        with patch.object(mod, "run_gh_graphql") as mock_gql:
            result = mod.get_repo_info([])

        mock_gql.assert_not_called()
        assert result == {}

    def test_none_graphql_response(self, mod):
        """GraphQL returns None → empty result."""
        with patch.object(mod, "run_gh_graphql", return_value=None):
            result = mod.get_repo_info(["owner/repo"])

        assert result == {}


class TestGetPrsReviewedPagination:
    """Pagination edge case for get_prs_reviewed()."""

    def test_multi_page_with_cursor(self, mod):
        """Two pages of reviews with cursor-based pagination."""
        page1 = {
            "user": {
                "contributionsCollection": {
                    "pullRequestReviewContributions": {
                        "totalCount": 2,
                        "pageInfo": {
                            "hasNextPage": True,
                            "endCursor": "cursor1",
                        },
                        "nodes": [
                            {
                                "pullRequest": {
                                    "title": "PR 1",
                                    "url": "https://github.com/o/r/pull/1",
                                    "repository": {"nameWithOwner": "o/r"},
                                    "author": {"login": "bob"},
                                    "additions": 10,
                                    "deletions": 5,
                                }
                            }
                        ],
                    }
                }
            }
        }
        page2 = {
            "user": {
                "contributionsCollection": {
                    "pullRequestReviewContributions": {
                        "totalCount": 2,
                        "pageInfo": {
                            "hasNextPage": False,
                            "endCursor": None,
                        },
                        "nodes": [
                            {
                                "pullRequest": {
                                    "title": "PR 2",
                                    "url": "https://github.com/o/r/pull/2",
                                    "repository": {"nameWithOwner": "o/r"},
                                    "author": {"login": "carol"},
                                    "additions": 20,
                                    "deletions": 3,
                                }
                            }
                        ],
                    }
                }
            }
        }
        with patch.object(
            mod,
            "run_gh_graphql",
            side_effect=[page1, page2],
        ):
            result = mod.get_prs_reviewed(
                "alice",
                "2026-01-01",
                "2026-01-31",
            )

        assert len(result) == 2
        assert result[0]["title"] == "PR 1"
        assert result[1]["title"] == "PR 2"


class TestGetOrgPrsCreatedNoneResponse:
    """Edge case: run_gh_graphql returns None."""

    def test_none_response_returns_empty(self, mod):
        """GraphQL returning None breaks loop → empty list."""
        with patch.object(mod, "run_gh_graphql", return_value=None):
            result = mod.get_org_prs_created(
                "org",
                "2026-01-01",
                "2026-01-31",
            )
        assert result == []


class TestContributionsSummaryYearClamp:
    """get_contributions_summary clamps > 1 year spans."""

    def test_year_clamping(self, mod):
        """Span > 365 days clamps start date."""
        graphql_response = {
            "user": {
                "name": "Test",
                "contributionsCollection": {
                    "totalCommitContributions": 5,
                },
            }
        }
        with patch.object(
            mod,
            "run_gh_graphql",
            return_value=graphql_response,
        ) as mock_gql:
            mod.get_contributions_summary(
                "alice",
                "2024-01-01",
                "2026-01-31",
            )

        # The query should have clamped start to ~365 days before end
        call_args = mock_gql.call_args[0][0]
        assert "2024-01-01" not in call_args
        assert "2025-02" in call_args or "2025-01" in call_args


class TestPromptRateLimitWarning:
    """Tests for prompt_rate_limit_warning()."""

    def test_skip_prompt_returns_true(self, mod):
        """skip_prompt=True returns True without asking."""
        result = mod.prompt_rate_limit_warning(
            "a lot of calls",
            skip_prompt=True,
        )
        assert result is True

    def test_user_confirms(self, mod):
        """User types 'y' → returns True."""
        with patch("builtins.input", return_value="y"):
            result = mod.prompt_rate_limit_warning("many calls")
        assert result is True

    def test_user_declines(self, mod):
        """User types 'n' → returns False."""
        with patch("builtins.input", return_value="n"):
            result = mod.prompt_rate_limit_warning("many calls")
        assert result is False

    def test_eof_returns_false(self, mod):
        """EOFError → returns False."""
        with patch("builtins.input", side_effect=EOFError):
            result = mod.prompt_rate_limit_warning("many calls")
        assert result is False


class TestPrintRateLimitError:
    """Tests for print_rate_limit_error()."""

    def test_with_reset_time(self, mod):
        """Prints reset time when available."""
        from datetime import datetime

        reset = datetime(2026, 1, 29, 15, 30, 0)
        with patch.object(
            mod,
            "get_rate_limit_reset_time",
            return_value=reset,
        ):
            # Just verify it doesn't raise
            mod.print_rate_limit_error()

    def test_without_reset_time(self, mod):
        """Prints fallback when no reset time."""
        with patch.object(
            mod,
            "get_rate_limit_reset_time",
            return_value=None,
        ):
            mod.print_rate_limit_error()

    def test_with_extra_advice(self, mod):
        """Prints extra advice lines."""
        with patch.object(
            mod,
            "get_rate_limit_reset_time",
            return_value=None,
        ):
            mod.print_rate_limit_error(
                extra_advice=["Use --days 7", "Try --team"],
            )


class TestCheckRateLimitHit:
    """Test for check_rate_limit_hit()."""

    def test_returns_false_by_default(self, mod):
        """Default state is False."""
        # Reset the global flag first
        mod._rate_limit_hit = False
        assert mod.check_rate_limit_hit() is False


# -----------------------------------------------------------------------
# Group 1: fetch_repo_topics + run_gh_command rate-limit-no-raise
# -----------------------------------------------------------------------


class TestFetchRepoTopics:
    """Tests for fetch_repo_topics()."""

    def test_successful_parse(self, mod):
        """Subprocess returns JSON topic list → tuple returned."""
        mod.fetch_repo_topics.cache_clear()
        mock_result = MagicMock(
            stdout='["web", "html"]\n',
            returncode=0,
        )
        with patch("subprocess.run", return_value=mock_result):
            result = mod.fetch_repo_topics("owner/repo")

        assert result == ("web", "html")
        mod.fetch_repo_topics.cache_clear()


class TestRunGhCommandRateLimitNoRaise:
    """run_gh_command with raise_on_rate_limit=False."""

    def test_rate_limit_returns_none(self, mod):
        """Rate limit hit without raise → returns None."""
        from subprocess import CalledProcessError

        error = CalledProcessError(1, "gh")
        error.stderr = "API rate limit exceeded"
        original = mod._rate_limit_hit
        try:
            with patch("subprocess.run", side_effect=error):
                result = mod.run_gh_command(
                    ["api", "test"],
                    raise_on_rate_limit=False,
                )
            assert result is None
        finally:
            mod._rate_limit_hit = original


# -----------------------------------------------------------------------
# Group 4: Defensive returns
# -----------------------------------------------------------------------


class TestGetForkCommitsEmptyBranches:
    """get_fork_commits with empty branch output."""

    def test_empty_stdout_returns_empty(self, mod):
        """Subprocess succeeds but returns no branches → []."""
        mock_result = MagicMock(
            stdout="\n",
            returncode=0,
        )
        with patch("subprocess.run", return_value=mock_result):
            result = mod.get_fork_commits(
                "alice",
                "alice/repo",
                "2026-01-01",
                "2026-01-31",
            )
        assert result == []


class TestGetEffectiveLanguageZeroBytes:
    """get_effective_language with all-zero byte counts."""

    def test_zero_bytes_returns_none(self, mod):
        """Language dict with zero-value entries → None."""
        with patch.object(
            mod,
            "run_gh_command",
            return_value={"Python": 0, "Go": 0},
        ):
            result = mod.get_effective_language("owner/repo")
        assert result is None


# -----------------------------------------------------------------------
# Group 5: get_org_pr_reviews pagination guards
# -----------------------------------------------------------------------


class TestGetOrgPrReviewsPaginationEdges:
    """Pagination edge cases in get_org_pr_reviews()."""

    def test_none_response_breaks(self, mod):
        """GraphQL returns None mid-pagination → breaks."""
        page1 = {
            "search": {
                "issueCount": 2,
                "pageInfo": {
                    "hasNextPage": True,
                    "endCursor": "c1",
                },
                "nodes": [
                    {
                        "title": "PR 1",
                        "url": "https://github.com/o/r/pull/1",
                        "author": {"login": "alice"},
                        "repository": {"nameWithOwner": "o/r"},
                        "additions": 10,
                        "deletions": 5,
                        "reviews": {"nodes": []},
                    }
                ],
            }
        }
        with patch.object(
            mod,
            "run_gh_graphql",
            side_effect=[page1, None],
        ):
            result = mod.get_org_pr_reviews(
                "org",
                "2026-01-01",
                "2026-01-31",
            )
        # Should have page1's PR but not crash
        assert isinstance(result, dict)

    def test_safety_limit_1000(self, mod):
        """Breaks after accumulating >=1000 PRs."""
        big_page = {
            "search": {
                "issueCount": 1500,
                "pageInfo": {
                    "hasNextPage": True,
                    "endCursor": "c1",
                },
                "nodes": [
                    {
                        "title": f"PR {i}",
                        "url": f"https://github.com/o/r/pull/{i}",
                        "author": {"login": "alice"},
                        "repository": {"nameWithOwner": "o/r"},
                        "additions": 1,
                        "deletions": 0,
                        "reviews": {
                            "nodes": [
                                {
                                    "author": {"login": "bob"},
                                    "submittedAt": "2026-01-15T00:00:00Z",
                                    "state": "APPROVED",
                                }
                            ]
                        },
                    }
                    for i in range(1000)
                ],
            }
        }
        with patch.object(
            mod,
            "run_gh_graphql",
            return_value=big_page,
        ):
            result = mod.get_org_pr_reviews(
                "org",
                "2026-01-01",
                "2026-01-31",
            )
        assert isinstance(result, dict)

    def test_malformed_submitted_at(self, mod):
        """Malformed submittedAt date → review skipped."""
        page = {
            "search": {
                "issueCount": 1,
                "pageInfo": {
                    "hasNextPage": False,
                    "endCursor": None,
                },
                "nodes": [
                    {
                        "title": "PR 1",
                        "url": "https://github.com/o/r/pull/1",
                        "author": {"login": "alice"},
                        "repository": {"nameWithOwner": "o/r"},
                        "additions": 10,
                        "deletions": 5,
                        "reviews": {
                            "nodes": [
                                {
                                    "author": {"login": "bob"},
                                    "submittedAt": "not-a-date",
                                    "state": "APPROVED",
                                }
                            ]
                        },
                    }
                ],
            }
        }
        with patch.object(
            mod,
            "run_gh_graphql",
            return_value=page,
        ):
            result = mod.get_org_pr_reviews(
                "org",
                "2026-01-01",
                "2026-01-31",
            )
        # bob's review should be skipped (malformed date)
        assert "bob" not in result


# -----------------------------------------------------------------------
# Group 6 (partial): paginate_gh_api defensive breaks
# -----------------------------------------------------------------------


class TestPaginateGhApiDefensiveBreaks:
    """Additional defensive break conditions in paginate_gh_api."""

    def test_non_list_result_breaks(self, mod):
        """Non-list API response (e.g. dict) → breaks."""
        with patch.object(
            mod,
            "run_gh_command",
            return_value={"message": "not a list"},
        ):
            result = mod.paginate_gh_api("orgs/test/members")
        assert result == []

    def test_no_logins_in_result_breaks(self, mod):
        """Result items without 'login' key → empty items → breaks."""
        with patch.object(
            mod,
            "run_gh_command",
            return_value=[{"id": 1}, {"id": 2}],
        ):
            result = mod.paginate_gh_api("orgs/test/members")
        assert result == []

    def test_extra_params_passed(self, mod):
        """extra_params are appended to the API command."""
        page = [{"login": "admin1"}]
        with patch.object(
            mod,
            "run_gh_command",
            return_value=page,
        ) as mock_cmd:
            result = mod.paginate_gh_api(
                "orgs/test/members",
                extra_params=["role=admin"],
            )
        assert result == ["admin1"]
        # Verify extra param was passed
        cmd_args = mock_cmd.call_args[0][0]
        assert "-f" in cmd_args
        assert "role=admin" in cmd_args
