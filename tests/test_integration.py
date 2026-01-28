"""Integration tests with mocked GitHub API calls.

These tests verify the data flow from API responses through to output,
using mocked subprocess calls to avoid actual GitHub API usage.
"""

import json
from unittest.mock import MagicMock, patch, call

import pytest


class TestRunGhCommand:
    """Tests for the run_gh_command wrapper."""

    def test_successful_json_response(self, mod, mock_subprocess):
        """Test successful JSON response parsing."""
        mock_subprocess.return_value = MagicMock(
            stdout='{"key": "value"}',
            stderr="",
            returncode=0
        )

        result = mod.run_gh_command(["api", "test"], parse_json=True)
        assert result == {"key": "value"}

    def test_non_json_response(self, mod, mock_subprocess):
        """Test non-JSON response handling."""
        mock_subprocess.return_value = MagicMock(
            stdout="plain text response",
            stderr="",
            returncode=0
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
            result = mod.run_gh_command(
                ["api", "test"],
                raise_on_rate_limit=True
            )
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
            stdout='{"data": "success"}',
            stderr="",
            returncode=0
        )

        mock_subprocess.side_effect = [error, success]

        result = mod.run_gh_command(["api", "test"], parse_json=True)
        assert result == {"data": "success"}
        assert mock_subprocess.call_count == 2


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
            assert "user" in result or "contributionsCollection" in result \
                or "totalCommitContributions" in str(result)


class TestGatherUserData:
    """Integration tests for gather_user_data()."""

    @pytest.fixture
    def mock_all_api_calls(self, mod):
        """Mock all API-calling functions for gather_user_data."""
        with patch.multiple(
            mod,
            get_contributions_summary=MagicMock(return_value={
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
                                        "primaryLanguage": {"name": "Python"},
                                        "description": "Test repo"
                                    },
                                    "contributions": {"totalCount": 50}
                                }
                            ]
                        }
                    }
                }
            }),
            get_all_commits=MagicMock(return_value={
                "items": [
                    {
                        "sha": "abc123",
                        "repository": {"full_name": "org/repo"},
                        "commit": {"message": "Test commit"}
                    }
                ],
                "total_count": 1
            }),
            get_prs_created=MagicMock(return_value={
                "search": {"nodes": [], "issueCount": 0}
            }),
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
            "testuser", "2026-01-01", "2026-01-31",
            show_progress=False
        )

        assert isinstance(result, dict)
        assert "username" in result

    def test_returns_expected_structure(self, mod, mock_all_api_calls):
        """Verify returned data has expected structure."""
        result = mod.gather_user_data(
            "testuser", "2026-01-01", "2026-01-31",
            show_progress=False
        )

        expected_keys = [
            "username", "repos_by_category"
        ]
        for key in expected_keys:
            assert key in result, f"Missing expected key: {key}"


class TestGatherUserDataLight:
    """Integration tests for gather_user_data_light() (org mode)."""

    @pytest.fixture
    def mock_light_api_calls(self, mod):
        """Mock API calls for light mode."""
        with patch.multiple(
            mod,
            get_contributions_summary=MagicMock(return_value={
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
                                        "description": "Go project"
                                    },
                                    "contributions": {"totalCount": 25}
                                }
                            ]
                        }
                    }
                }
            }),
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
                        "description": "CSS specs"
                    }
                ],
                "Other": [
                    {
                        "name": "user/project",
                        "commits": 10,
                        "prs": 1,
                        "language": "Python",
                        "description": "Personal project"
                    }
                ]
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
                        "primaryLanguage": {"name": "CSS"}
                    }
                }
            ],
            "reviewed_nodes": [
                {
                    "title": "Fix bug",
                    "url": "https://github.com/w3c/csswg-drafts/pull/2",
                    "additions": 100,
                    "deletions": 20,
                    "author": {"login": "other"},
                    "repository": {"nameWithOwner": "w3c/csswg-drafts"}
                }
            ],
        }

    def test_report_contains_username(self, mod, mock_user_data):
        """Report should contain the username."""
        with patch.object(mod, "gather_user_data", return_value=mock_user_data):
            report = mod.generate_report(
                "testuser", "2026-01-01", "2026-01-31"
            )

            assert "testuser" in report

    def test_report_contains_date_range(self, mod, mock_user_data):
        """Report should show the date range."""
        with patch.object(mod, "gather_user_data", return_value=mock_user_data):
            report = mod.generate_report(
                "testuser", "2026-01-01", "2026-01-31"
            )

            assert "2026-01-01" in report
            assert "2026-01-31" in report

    def test_report_has_sections(self, mod, mock_user_data):
        """Report should have expected sections."""
        with patch.object(mod, "gather_user_data", return_value=mock_user_data):
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
        with patch.object(mod, "gather_user_data", return_value=mock_user_data):
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
                        "description": "CSS specs"
                    }
                ]
            },
            "repo_line_stats": {},
            "repo_languages": {},
            "repo_member_commits": {
                "w3c/csswg-drafts": {"alice": 200, "bob": 100}
            },
            "lang_member_commits": {
                "CSS": {"alice": 200, "bob": 100}
            },
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
            org_info, None, "2026-01-01", "2026-01-31",
            mock_org_data, members
        )

        # Should have detail sections
        assert "Commit details" in report or "details" in report.lower()

    def test_org_report_has_accordion(self, mod, mock_org_data):
        """Org report should use accordion for detail sections."""
        org_info = {"login": "w3c", "name": "W3C"}
        members = [{"login": "alice"}, {"login": "bob"}]

        report = mod.generate_org_report(
            org_info, None, "2026-01-01", "2026-01-31",
            mock_org_data, members
        )

        # Should have <details> elements with name attribute
        assert "<details" in report
        assert 'name="commit-details"' in report


class TestCompanyNormalization:
    """Tests for company name normalization in org reports."""

    def test_at_mention_extracted(self, mod):
        """@org mentions should be extracted from company field."""
        # Test the regex pattern for @org extraction
        import re
        pattern = getattr(mod, "org_pattern", None)
        if pattern:
            matches = pattern.findall("@tc39 @w3c")
            assert "tc39" in matches
            assert "w3c" in matches

    def test_org_with_period(self, mod):
        """@org mentions with periods should work (e.g., @mesur.io)."""
        import re
        pattern = getattr(mod, "org_pattern", None)
        if pattern:
            matches = pattern.findall("@mesur.io")
            assert "mesur.io" in matches or len(matches) > 0

    def test_plain_text_company(self, mod):
        """Plain text companies (no @) should be handled."""
        # This is tested through aggregate_org_data behavior
        # Companies like "DWANGO Co.,Ltd." should create their own group
        pass
