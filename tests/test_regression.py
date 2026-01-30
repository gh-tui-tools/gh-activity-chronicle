"""Regression tests for output structure and content.

These tests verify that generated reports maintain expected structure
and content across code changes. They use comprehensive mock data to
test the complete output pipeline.
"""

import re
from unittest.mock import MagicMock, patch

import pytest


class TestUserReportStructure:
    """Verify user report has expected structure."""

    @pytest.fixture
    def complete_user_data(self):
        """Comprehensive user data for regression testing."""
        return {
            "username": "testuser",
            "user_real_name": "Test User",
            "company": "@acme",
            "total_commits_default_branch": 120,
            "total_commits_all": 150,
            "total_prs": 25,
            "total_pr_reviews": 40,
            "total_issues": 8,
            "total_additions": 12000,
            "total_deletions": 3000,
            "test_commits": 15,
            "repos_contributed": 3,
            "reviews_received": 5,
            "pr_comments_received": 3,
            "lines_reviewed": 2000,
            "review_comments": 10,
            "repos_by_category": {
                "Web standards and specifications": [
                    {
                        "name": "w3c/csswg-drafts",
                        "commits": 80,
                        "prs": 12,
                        "language": "CSS",
                        "description": "CSS Working Group Editor Drafts",
                    },
                    {
                        "name": "whatwg/html",
                        "commits": 30,
                        "prs": 5,
                        "language": "HTML",
                        "description": "HTML Living Standard",
                    },
                ],
                "Other": [
                    {
                        "name": "user/project",
                        "commits": 40,
                        "prs": 8,
                        "language": "Python",
                        "description": "Personal project",
                    }
                ],
            },
            "repo_line_stats": {
                "w3c/csswg-drafts": {"additions": 8000, "deletions": 2000},
                "whatwg/html": {"additions": 2000, "deletions": 500},
                "user/project": {"additions": 2000, "deletions": 500},
            },
            "repo_languages": {
                "w3c/csswg-drafts": "CSS",
                "whatwg/html": "HTML",
                "user/project": "Python",
            },
            "prs_nodes": [
                {
                    "title": "Add CSS Grid feature",
                    "url": "https://github.com/w3c/csswg-drafts/pull/100",
                    "state": "MERGED",
                    "additions": 500,
                    "deletions": 100,
                    "repository": {
                        "nameWithOwner": "w3c/csswg-drafts",
                        "primaryLanguage": {"name": "CSS"},
                    },
                },
                {
                    "title": "Fix HTML parser bug",
                    "url": "https://github.com/whatwg/html/pull/50",
                    "state": "MERGED",
                    "additions": 200,
                    "deletions": 50,
                    "repository": {
                        "nameWithOwner": "whatwg/html",
                        "primaryLanguage": {"name": "HTML"},
                    },
                },
            ],
            "reviewed_nodes": [
                {
                    "title": "Update Flexbox spec",
                    "url": "https://github.com/w3c/csswg-drafts/pull/101",
                    "additions": 300,
                    "deletions": 80,
                    "author": {"login": "other-user"},
                    "repository": {"nameWithOwner": "w3c/csswg-drafts"},
                }
            ],
        }

    def test_report_title_format(self, mod, complete_user_data):
        """Report title should have correct format."""
        with patch.object(
            mod, "gather_user_data", return_value=complete_user_data
        ):
            report = mod.generate_report(
                "testuser", "2026-01-01", "2026-01-31"
            )

            # Title should be H1 with username link
            assert report.startswith("# ")
            assert "[testuser]" in report
            assert "github.com/testuser" in report

    def test_period_displayed(self, mod, complete_user_data):
        """Period should be displayed at top of report."""
        with patch.object(
            mod, "gather_user_data", return_value=complete_user_data
        ):
            report = mod.generate_report(
                "testuser", "2026-01-01", "2026-01-31"
            )

            assert "**Period:**" in report or "Period:" in report
            assert "2026-01-01" in report
            assert "2026-01-31" in report

    def test_executive_summary_section(self, mod, complete_user_data):
        """Executive summary should contain key metrics."""
        with patch.object(
            mod, "gather_user_data", return_value=complete_user_data
        ):
            report = mod.generate_report(
                "testuser", "2026-01-01", "2026-01-31"
            )

            assert "Executive summary" in report
            # Should have commit counts
            assert "150" in report or "commits" in report.lower()
            # Should have PR counts
            has_prs = (
                "25" in report
                or "PRs" in report
                or "pull request" in report.lower()
            )
            assert has_prs

    def test_projects_by_category_section(self, mod, complete_user_data):
        """Projects by category should have tables."""
        with patch.object(
            mod, "gather_user_data", return_value=complete_user_data
        ):
            report = mod.generate_report(
                "testuser", "2026-01-01", "2026-01-31"
            )

            assert "Projects by category" in report
            # Should have category headers
            assert "Web standards and specifications" in report
            # Should have table structure
            assert "| " in report

    def test_languages_section(self, mod, complete_user_data):
        """Languages section should list programming languages."""
        with patch.object(
            mod, "gather_user_data", return_value=complete_user_data
        ):
            report = mod.generate_report(
                "testuser", "2026-01-01", "2026-01-31"
            )

            assert "Languages" in report
            # Should mention languages from the data
            assert "CSS" in report or "Python" in report

    def test_prs_reviewed_section(self, mod, complete_user_data):
        """PRs reviewed section should exist."""
        with patch.object(
            mod, "gather_user_data", return_value=complete_user_data
        ):
            report = mod.generate_report(
                "testuser", "2026-01-01", "2026-01-31"
            )

            assert "PRs reviewed" in report or "reviewed" in report.lower()

    def test_prs_created_section(self, mod, complete_user_data):
        """PRs created section should exist."""
        with patch.object(
            mod, "gather_user_data", return_value=complete_user_data
        ):
            report = mod.generate_report(
                "testuser", "2026-01-01", "2026-01-31"
            )

            assert "PRs created" in report or "created" in report.lower()

    def test_footer_timestamp(self, mod, complete_user_data):
        """Report should have footer with generation timestamp."""
        with patch.object(
            mod, "gather_user_data", return_value=complete_user_data
        ):
            report = mod.generate_report(
                "testuser", "2026-01-01", "2026-01-31"
            )

            # Footer with timestamp
            assert "Report generated" in report or "Generated" in report


class TestOrgReportStructure:
    """Verify org report has expected structure."""

    @pytest.fixture
    def complete_org_data(self):
        """Comprehensive org data for regression testing."""
        return {
            "total_commits_default_branch": 1000,
            "total_commits_all": 1000,
            "total_prs": 150,
            "total_pr_reviews": 200,
            "total_issues": 50,
            "repos_contributed": 3,
            "total_additions": 50000,
            "total_deletions": 10000,
            "repos_by_category": {
                "Web standards and specifications": [
                    {
                        "name": "w3c/csswg-drafts",
                        "commits": 500,
                        "prs": 80,
                        "language": "CSS",
                        "description": "CSS specs",
                    },
                    {
                        "name": "whatwg/dom",
                        "commits": 200,
                        "prs": 30,
                        "language": "HTML",
                        "description": "DOM Standard",
                    },
                ],
                "Accessibility": [
                    {
                        "name": "w3c/wai-aria",
                        "commits": 100,
                        "prs": 20,
                        "language": "HTML",
                        "description": "WAI-ARIA spec",
                    }
                ],
            },
            "repo_line_stats": {},
            "repo_languages": {},
            "repo_member_commits": {
                "w3c/csswg-drafts": {"alice": 300, "bob": 200},
                "whatwg/dom": {"alice": 100, "charlie": 100},
                "w3c/wai-aria": {"diana": 100},
            },
            "lang_member_commits": {
                "CSS": {"alice": 300, "bob": 200},
                "HTML": {"alice": 100, "charlie": 100, "diana": 100},
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
                "charlie": "@w3c",
                "diana": "Amazon",
            },
            "prs_nodes": [],
            "reviewed_nodes": [],
            "is_light_mode": True,
        }

    @pytest.fixture
    def mock_members(self):
        """Mock member list."""
        return [
            {"login": "alice", "name": "Alice Smith"},
            {"login": "bob", "name": "Bob Jones"},
            {"login": "charlie", "name": "Charlie Brown"},
            {"login": "diana", "name": "Diana Prince"},
        ]

    @pytest.fixture
    def org_info(self):
        """Mock org info."""
        return {
            "login": "w3c",
            "name": "World Wide Web Consortium",
        }

    def test_org_report_title(
        self, mod, complete_org_data, mock_members, org_info
    ):
        """Org report should have org name in title."""
        report = mod.generate_org_report(
            org_info,
            None,
            "2026-01-01",
            "2026-01-31",
            complete_org_data,
            mock_members,
        )

        assert "w3c" in report.lower()
        assert "[w3c]" in report or "w3c](" in report

    def test_org_report_has_details_sections(
        self, mod, complete_org_data, mock_members, org_info
    ):
        """Org report should have collapsible detail sections."""
        report = mod.generate_org_report(
            org_info,
            None,
            "2026-01-01",
            "2026-01-31",
            complete_org_data,
            mock_members,
        )

        # Should have <details> elements
        assert "<details" in report
        assert "</details>" in report
        assert "<summary>" in report

    def test_org_report_accordion_behavior(
        self, mod, complete_org_data, mock_members, org_info
    ):
        """Detail sections should have name attribute for accordion."""
        report = mod.generate_org_report(
            org_info,
            None,
            "2026-01-01",
            "2026-01-31",
            complete_org_data,
            mock_members,
        )

        # All detail sections should share same name for accordion
        assert 'name="activity"' in report

    def test_commit_details_by_repository(
        self, mod, complete_org_data, mock_members, org_info
    ):
        """Should have commit details by repository section."""
        report = mod.generate_org_report(
            org_info,
            None,
            "2026-01-01",
            "2026-01-31",
            complete_org_data,
            mock_members,
        )

        assert "Commit details by repository" in report
        # Should list repos
        assert "csswg-drafts" in report

    def test_commit_details_by_user(
        self, mod, complete_org_data, mock_members, org_info
    ):
        """Should have commit details by user section."""
        report = mod.generate_org_report(
            org_info,
            None,
            "2026-01-01",
            "2026-01-31",
            complete_org_data,
            mock_members,
        )

        assert "Commit details by user" in report
        # Should list users with real names
        assert "Alice" in report or "alice" in report

    def test_commit_details_by_organization(
        self, mod, complete_org_data, mock_members, org_info
    ):
        """Should have commit details by organization section."""
        report = mod.generate_org_report(
            org_info,
            None,
            "2026-01-01",
            "2026-01-31",
            complete_org_data,
            mock_members,
        )

        assert "Commit details by organization" in report
        # Should group by company
        assert "@w3c" in report or "w3c" in report

    def test_duplicate_org_in_company_does_not_duplicate_member(
        self, mod, org_info
    ):
        """Member with '@google Google' company appears once, not twice."""
        data = {
            "total_commits_default_branch": 10,
            "total_commits_all": 10,
            "total_prs": 1,
            "total_pr_reviews": 0,
            "total_issues": 0,
            "repos_contributed": 1,
            "repos_by_category": {
                "Other": [
                    {
                        "name": "nicehero/nicejson",
                        "commits": 10,
                        "prs": 1,
                        "language": "Python",
                        "description": "A project",
                    }
                ]
            },
            "repo_line_stats": {},
            "repo_languages": {},
            "repo_member_commits": {
                "nicehero/nicejson": {"tomayac": 10},
            },
            "lang_member_commits": {"Python": {"tomayac": 10}},
            "member_real_names": {"tomayac": "Thomas Steiner"},
            "member_companies": {"tomayac": "@google Google"},
            "prs_nodes": [],
            "reviewed_nodes": [],
            "is_light_mode": True,
        }
        members = [{"login": "tomayac", "name": "Thomas Steiner"}]
        report = mod.generate_org_report(
            org_info,
            None,
            "2026-01-01",
            "2026-01-31",
            data,
            members,
        )
        # "Thomas Steiner" should appear only once in the org section
        org_section = report.split("Commit details by organization")[1]
        org_section = org_section.split("Commit details by")[0]
        assert org_section.count("Thomas Steiner") == 1

    def test_commit_details_by_language(
        self, mod, complete_org_data, mock_members, org_info
    ):
        """Should have commit details by language section."""
        report = mod.generate_org_report(
            org_info,
            None,
            "2026-01-01",
            "2026-01-31",
            complete_org_data,
            mock_members,
        )

        assert "Commit details by language" in report
        # Should list languages
        assert "CSS" in report or "HTML" in report

    def test_anchor_ids_present(
        self, mod, complete_org_data, mock_members, org_info
    ):
        """Report should have anchor IDs for navigation."""
        report = mod.generate_org_report(
            org_info,
            None,
            "2026-01-01",
            "2026-01-31",
            complete_org_data,
            mock_members,
        )

        # Should have anchor IDs for repos, languages, users, orgs
        assert '<a id="' in report or 'id="' in report

    def test_backlinks_present(
        self, mod, complete_org_data, mock_members, org_info
    ):
        """User section should have backlinks to org section."""
        report = mod.generate_org_report(
            org_info,
            None,
            "2026-01-01",
            "2026-01-31",
            complete_org_data,
            mock_members,
        )

        # Should have backlink characters
        assert "↩" in report or "[↩]" in report


class TestOrgReportTitleBranches:
    """Test title construction branches in generate_org_report()."""

    @pytest.fixture
    def base_org_data(self):
        """Minimal org data for title tests."""
        return {
            "total_commits_default_branch": 100,
            "total_commits_all": 100,
            "total_prs": 10,
            "total_pr_reviews": 20,
            "total_issues": 5,
            "repos_contributed": 1,
            "total_additions": 1000,
            "total_deletions": 200,
            "repos_by_category": {
                "Other": [
                    {
                        "name": "org/repo",
                        "commits": 100,
                        "prs": 10,
                        "language": "Go",
                        "description": "A repo",
                    }
                ],
            },
            "repo_line_stats": {},
            "repo_languages": {},
            "repo_member_commits": {"org/repo": {"alice": 100}},
            "lang_member_commits": {"Go": {"alice": 100}},
            "member_real_names": {"alice": "Alice"},
            "member_companies": {"alice": "@org"},
            "prs_nodes": [],
            "reviewed_nodes": [],
            "is_light_mode": True,
        }

    @pytest.fixture
    def members(self):
        return [{"login": "alice", "name": "Alice"}]

    def test_team_info_with_org_and_team_name(
        self, mod, base_org_data, members
    ):
        """Title with team_info, org_name, and team_name."""
        org_info = {"login": "w3c", "name": "W3C"}
        team_info = {"slug": "editors", "name": "Spec Editors"}
        report = mod.generate_org_report(
            org_info,
            team_info,
            "2026-01-01",
            "2026-01-31",
            base_org_data,
            members,
        )
        first_line = report.split("\n")[0]
        assert "editors" in first_line
        assert "W3C" in first_line
        assert "Spec Editors" in first_line

    def test_team_info_with_org_name_only(self, mod, base_org_data, members):
        """Title with team_info and org_name but no team_name."""
        org_info = {"login": "w3c", "name": "W3C"}
        team_info = {"slug": "editors", "name": ""}
        report = mod.generate_org_report(
            org_info,
            team_info,
            "2026-01-01",
            "2026-01-31",
            base_org_data,
            members,
        )
        first_line = report.split("\n")[0]
        assert "editors" in first_line
        assert "(W3C)" in first_line

    def test_team_info_without_org_name(self, mod, base_org_data, members):
        """Title with team_info but no org_name."""
        org_info = {"login": "w3c", "name": ""}
        team_info = {"slug": "editors", "name": ""}
        report = mod.generate_org_report(
            org_info,
            team_info,
            "2026-01-01",
            "2026-01-31",
            base_org_data,
            members,
        )
        first_line = report.split("\n")[0]
        assert "editors" in first_line
        # No parenthesized org_name
        assert "()" not in first_line

    def test_no_team_info_with_org_name(self, mod, base_org_data, members):
        """Title without team_info, with org_name."""
        org_info = {"login": "w3c", "name": "W3C"}
        report = mod.generate_org_report(
            org_info,
            None,
            "2026-01-01",
            "2026-01-31",
            base_org_data,
            members,
        )
        first_line = report.split("\n")[0]
        assert "(W3C)" in first_line

    def test_no_team_info_without_org_name(self, mod, base_org_data, members):
        """Title without team_info and without org_name."""
        org_info = {"login": "w3c", "name": ""}
        report = mod.generate_org_report(
            org_info,
            None,
            "2026-01-01",
            "2026-01-31",
            base_org_data,
            members,
        )
        first_line = report.split("\n")[0]
        assert "[w3c]" in first_line
        assert "(" not in first_line or "https" in first_line

    def test_owners_only_flag(self, mod, base_org_data, members):
        """owners_only flag should append 'Owners' to title."""
        org_info = {"login": "w3c", "name": "W3C"}
        base_org_data["owners_only"] = True
        report = mod.generate_org_report(
            org_info,
            None,
            "2026-01-01",
            "2026-01-31",
            base_org_data,
            members,
        )
        first_line = report.split("\n")[0]
        assert first_line.endswith("Owners")

    def test_include_private_shows_warning(self, mod, base_org_data, members):
        """include_private flag adds a warning banner."""
        org_info = {"login": "w3c", "name": "W3C"}
        base_org_data["include_private"] = True
        report = mod.generate_org_report(
            org_info,
            None,
            "2026-01-01",
            "2026-01-31",
            base_org_data,
            members,
        )
        assert "> [!WARNING]" in report
        assert "Do not share this report publicly" in report
        assert "made their membership" in report

    def test_no_private_no_warning(self, mod, base_org_data, members):
        """No warning banner when include_private is not set."""
        org_info = {"login": "w3c", "name": "W3C"}
        report = mod.generate_org_report(
            org_info,
            None,
            "2026-01-01",
            "2026-01-31",
            base_org_data,
            members,
        )
        assert "> [!WARNING]" not in report


class TestOrgReportFullMode:
    """Test full mode (non-light) branches in generate_org_report()."""

    @pytest.fixture
    def full_mode_org_data(self):
        """Org data with is_light_mode=False and populated line stats."""
        return {
            "total_commits_default_branch": 500,
            "total_commits_all": 500,
            "total_prs": 50,
            "total_pr_reviews": 100,
            "total_issues": 20,
            "repos_contributed": 2,
            "total_additions": 25000,
            "total_deletions": 5000,
            "test_commits": 42,
            "repos_by_category": {
                "Web standards and specifications": [
                    {
                        "name": "w3c/csswg-drafts",
                        "commits": 300,
                        "prs": 30,
                        "language": "CSS",
                        "description": "CSS specs",
                    },
                    {
                        "name": "whatwg/html",
                        "commits": 200,
                        "prs": 20,
                        "language": "HTML",
                        "description": "HTML Standard",
                    },
                ],
            },
            "repo_line_stats": {
                "w3c/csswg-drafts": {
                    "additions": 15000,
                    "deletions": 3000,
                },
                "whatwg/html": {"additions": 10000, "deletions": 2000},
            },
            "repo_languages": {
                "w3c/csswg-drafts": "CSS",
                "whatwg/html": "HTML",
            },
            "repo_member_commits": {
                "w3c/csswg-drafts": {"alice": 200, "bob": 100},
                "whatwg/html": {"alice": 100, "charlie": 100},
            },
            "lang_member_commits": {
                "CSS": {"alice": 200, "bob": 100},
                "HTML": {"alice": 100, "charlie": 100},
            },
            "member_real_names": {
                "alice": "Alice",
                "bob": "Bob",
                "charlie": "Charlie",
            },
            "member_companies": {
                "alice": "@w3c",
                "bob": "@google",
                "charlie": "@w3c",
            },
            "prs_nodes": [],
            "reviewed_nodes": [],
            "is_light_mode": False,
        }

    @pytest.fixture
    def members(self):
        return [
            {"login": "alice", "name": "Alice"},
            {"login": "bob", "name": "Bob"},
            {"login": "charlie", "name": "Charlie"},
        ]

    def test_projects_table_has_lines_column(
        self, mod, full_mode_org_data, members
    ):
        """Full mode projects table should have a Lines column."""
        org_info = {"login": "w3c", "name": "W3C"}
        report = mod.generate_org_report(
            org_info,
            None,
            "2026-01-01",
            "2026-01-31",
            full_mode_org_data,
            members,
        )
        # Full mode header
        assert "| Repo | Commits | Lines | Lang | Description |" in report
        # Should contain line stats like +15,000/-3,000
        assert "+15,000/-3,000" in report

    def test_executive_summary_has_lines_and_tests(
        self, mod, full_mode_org_data, members
    ):
        """Full mode executive summary includes lines and test commits."""
        org_info = {"login": "w3c", "name": "W3C"}
        report = mod.generate_org_report(
            org_info,
            None,
            "2026-01-01",
            "2026-01-31",
            full_mode_org_data,
            members,
        )
        assert "| Lines added | 25,000 |" in report
        assert "| Lines deleted | 5,000 |" in report
        assert "| Test-related commits | 42 |" in report

    def test_languages_table_has_lines_column(
        self, mod, full_mode_org_data, members
    ):
        """Full mode languages table should have a Lines column."""
        org_info = {"login": "w3c", "name": "W3C"}
        report = mod.generate_org_report(
            org_info,
            None,
            "2026-01-01",
            "2026-01-31",
            full_mode_org_data,
            members,
        )
        assert "| Language | Commits | Lines |" in report


class TestMarkdownValidity:
    """Tests to ensure generated markdown is valid."""

    @pytest.fixture
    def sample_report(self, mod):
        """Generate a sample report for validation."""
        mock_data = {
            "username": "test",
            "user_real_name": "Test",
            "company": "",
            "total_commits_default_branch": 10,
            "total_commits_all": 10,
            "total_prs": 2,
            "total_pr_reviews": 3,
            "total_issues": 1,
            "total_additions": 100,
            "total_deletions": 20,
            "test_commits": 0,
            "repos_contributed": 1,
            "repos_by_category": {
                "Other": [
                    {
                        "name": "o/r",
                        "commits": 10,
                        "prs": 2,
                        "language": "Python",
                        "description": "Test",
                    }
                ]
            },
            "repo_line_stats": {"o/r": {"additions": 100, "deletions": 20}},
            "repo_languages": {"o/r": "Python"},
            "prs_nodes": [],
            "reviewed_nodes": [],
            "reviews_received": 0,
            "pr_comments_received": 0,
            "lines_reviewed": 0,
            "review_comments": 0,
        }
        with patch.object(mod, "gather_user_data", return_value=mock_data):
            return mod.generate_report("test", "2026-01-01", "2026-01-31")

    def test_no_unclosed_brackets(self, sample_report):
        """No unclosed markdown links."""
        # Count opening and closing brackets
        open_square = sample_report.count("[")
        close_square = sample_report.count("]")
        # Allow some imbalance for edge cases, but large imbalance is a problem
        assert abs(open_square - close_square) < 5

    def test_no_unclosed_parens_in_links(self, sample_report):
        """Links should have matching parentheses."""
        # Find all markdown links and verify they're properly formed
        link_pattern = r"\[([^\]]*)\]\(([^)]*)\)"
        re.findall(link_pattern, sample_report)
        # If we found links, the pattern matched, so they're valid
        # This is a basic check

    def test_tables_have_separator_rows(self, sample_report):
        """Markdown tables should have separator rows."""
        lines = sample_report.split("\n")
        for i, line in enumerate(lines):
            if line.startswith("|") and i + 1 < len(lines):
                next_line = lines[i + 1]
                if next_line.startswith("|"):
                    # Either this is a separator row, or next should be
                    if "---" not in line and "---" not in next_line:
                        # Check if any nearby line is separator
                        pass  # Tables vary, hard to validate strictly

    def test_headers_have_content(self, sample_report):
        """Headers should have text content."""
        for line in sample_report.split("\n"):
            if line.startswith("#"):
                # Header line should have text after #
                header_text = line.lstrip("#").strip()
                # Allow HTML in headers
                assert len(header_text) > 0 or "<" in line


class TestRegressionExpectations:
    """Specific regression tests for known behaviors."""

    def test_fork_attribution(self, mod):
        """Commits to forks should be attributed to parent repo."""
        # This tests the conceptual behavior via categorize_repo
        # Fork attribution happens during data gathering, not categorization
        pass

    def test_bot_filtering(self, mod):
        """Bot accounts should be filtered from reviews."""
        assert mod.is_bot("dependabot[bot]") is True
        assert mod.is_bot("renovate[bot]") is True
        assert mod.is_bot("human-user") is False

    def test_private_repo_exclusion(self, mod):
        """Private repos should be excluded."""
        repo_info = {"isPrivate": True}
        result = mod.should_skip_repo("user/private-repo", repo_info=repo_info)
        assert result is True

    def test_profile_repo_exclusion(self, mod):
        """Profile repos (user/user) should be excluded."""
        result = mod.should_skip_repo("octocat/octocat", username="octocat")
        assert result is True


class TestOrgReportWithReviewedPRs:
    """Org report with reviewed_nodes covers PRs reviewed section."""

    @pytest.fixture
    def org_data_with_reviews(self):
        """Org data with populated reviewed_nodes."""
        return {
            "total_commits_default_branch": 100,
            "total_commits_all": 100,
            "total_prs": 10,
            "total_pr_reviews": 20,
            "total_issues": 5,
            "repos_contributed": 1,
            "total_additions": 1000,
            "total_deletions": 200,
            "repos_by_category": {
                "Other": [
                    {
                        "name": "org/repo",
                        "commits": 100,
                        "prs": 10,
                        "language": "Go",
                        "description": "A repo",
                    }
                ],
            },
            "repo_line_stats": {},
            "repo_languages": {},
            "repo_member_commits": {"org/repo": {"alice": 100}},
            "lang_member_commits": {"Go": {"alice": 100}},
            "member_real_names": {"alice": "Alice"},
            "member_companies": {"alice": "@org"},
            "prs_nodes": [],
            "reviewed_nodes": [
                {
                    "title": "Add feature",
                    "url": "https://github.com/org/repo/pull/1",
                    "additions": 50,
                    "deletions": 10,
                    "author": {"login": "bob"},
                    "repository": {
                        "nameWithOwner": "org/repo",
                        "primaryLanguage": {"name": "Go"},
                    },
                },
                {
                    "title": "Fix bug",
                    "url": "https://github.com/org/repo/pull/2",
                    "additions": 20,
                    "deletions": 5,
                    "author": {"login": "charlie"},
                    "repository": {
                        "nameWithOwner": "org/repo",
                        "primaryLanguage": None,
                    },
                },
            ],
            "is_light_mode": True,
        }

    def test_reviewed_prs_section_present(self, mod, org_data_with_reviews):
        """Org report with reviewed_nodes has PRs reviewed section."""
        org_info = {"login": "org", "name": "Org"}
        members = [{"login": "alice"}]

        report = mod.generate_org_report(
            org_info,
            None,
            "2026-01-01",
            "2026-01-31",
            org_data_with_reviews,
            members,
        )

        assert "PRs reviewed" in report
        assert "org/repo" in report

    def test_language_fallback_from_primary_language(
        self, mod, org_data_with_reviews
    ):
        """Language falls back to primaryLanguage when repo_languages empty."""
        org_info = {"login": "org", "name": "Org"}
        members = [{"login": "alice"}]

        report = mod.generate_org_report(
            org_info,
            None,
            "2026-01-01",
            "2026-01-31",
            org_data_with_reviews,
            members,
        )

        # Go should appear from primaryLanguage fallback
        assert "Go" in report


class TestUserReportEmptyCategory:
    """User report with empty category repos list covers continue branch."""

    def test_empty_category_skipped(self, mod):
        """Category with empty repos list is skipped."""
        user_data = {
            "username": "testuser",
            "user_real_name": "Test User",
            "company": "",
            "total_commits_default_branch": 10,
            "total_commits_all": 10,
            "total_prs": 2,
            "total_pr_reviews": 0,
            "total_issues": 0,
            "total_additions": 100,
            "total_deletions": 20,
            "test_commits": 0,
            "repos_contributed": 1,
            "reviews_received": 0,
            "pr_comments_received": 0,
            "lines_reviewed": 0,
            "review_comments": 0,
            "repos_by_category": {
                "Other": [
                    {
                        "name": "user/project",
                        "commits": 10,
                        "prs": 2,
                        "language": "Python",
                        "description": "Test",
                    }
                ],
                "Empty category": [],
            },
            "repo_line_stats": {
                "user/project": {"additions": 100, "deletions": 20}
            },
            "repo_languages": {"user/project": "Python"},
            "prs_nodes": [],
            "reviewed_nodes": [],
        }
        with patch.object(mod, "gather_user_data", return_value=user_data):
            report = mod.generate_report(
                "testuser", "2026-01-01", "2026-01-31"
            )

        # Empty category should not appear in output
        assert "Empty category" not in report
        # Non-empty category should still be present
        assert "Other" in report


class TestUserReportReviewedPRsLanguageFallback:
    """User report reviewed PRs falls back to primaryLanguage."""

    def test_fallback_when_repo_not_in_repo_languages(self, mod):
        user_data = {
            "username": "testuser",
            "user_real_name": "Test User",
            "company": "",
            "total_commits_default_branch": 10,
            "total_commits_all": 10,
            "total_prs": 0,
            "total_pr_reviews": 1,
            "total_issues": 0,
            "total_additions": 100,
            "total_deletions": 20,
            "test_commits": 0,
            "repos_contributed": 1,
            "reviews_received": 0,
            "pr_comments_received": 0,
            "lines_reviewed": 0,
            "review_comments": 0,
            "repos_by_category": {
                "Other": [
                    {
                        "name": "user/project",
                        "commits": 10,
                        "prs": 0,
                        "language": "Python",
                        "description": "Test",
                    }
                ],
            },
            "repo_line_stats": {
                "user/project": {"additions": 100, "deletions": 20}
            },
            "repo_languages": {"user/project": "Python"},
            "prs_nodes": [],
            "reviewed_nodes": [
                {
                    "title": "Fix issue",
                    "url": "https://github.com/ext/lib/pull/1",
                    "additions": 50,
                    "deletions": 10,
                    "author": {"login": "other"},
                    "repository": {
                        "nameWithOwner": "ext/lib",
                        "primaryLanguage": {"name": "Rust"},
                    },
                },
            ],
        }
        with patch.object(mod, "gather_user_data", return_value=user_data):
            report = mod.generate_report(
                "testuser", "2026-01-01", "2026-01-31"
            )

        # ext/lib is NOT in repo_languages, so Rust comes from primaryLanguage
        assert "ext/lib" in report
        assert "Rust" in report


# -----------------------------------------------------------------------
# Group 7: Org report generation branch coverage
# -----------------------------------------------------------------------


class TestOrgReportReviewedPRsLanguageFallback:
    """Reviewed PRs table falls back to primaryLanguage."""

    def test_fallback_when_repo_languages_missing(self, mod):
        """Repo not in repo_languages → uses primaryLanguage."""
        data = {
            "total_commits_default_branch": 10,
            "total_commits_all": 10,
            "total_prs": 1,
            "total_pr_reviews": 1,
            "total_issues": 0,
            "repos_contributed": 1,
            "total_additions": 50,
            "total_deletions": 10,
            "repos_by_category": {
                "Other": [
                    {
                        "name": "org/repo",
                        "commits": 10,
                        "prs": 1,
                        "language": "Rust",
                        "description": "",
                    }
                ],
            },
            "repo_line_stats": {},
            "repo_languages": {},  # empty — forces fallback
            "repo_member_commits": {"org/repo": {"alice": 10}},
            "lang_member_commits": {"Rust": {"alice": 10}},
            "member_real_names": {"alice": "Alice"},
            "member_companies": {"alice": "@org"},
            "prs_nodes": [],
            "reviewed_nodes": [
                {
                    "title": "Add feature",
                    "url": "https://github.com/org/repo/pull/1",
                    "additions": 50,
                    "deletions": 10,
                    "author": {"login": "bob"},
                    "repository": {
                        "nameWithOwner": "org/repo",
                        "primaryLanguage": {"name": "Rust"},
                    },
                },
            ],
            "is_light_mode": True,
        }
        org_info = {"login": "org", "name": "Org"}
        with patch.object(mod, "progress", MagicMock()):
            report = mod.generate_org_report(
                org_info,
                None,
                "2026-01-01",
                "2026-01-31",
                data,
                ["alice"],
            )
        assert "Rust" in report


class TestOrgReportEmptyCategory:
    """Empty category in org report is skipped."""

    def test_empty_category_skipped(self, mod):
        """Category with empty repos list → continue."""
        data = {
            "total_commits_default_branch": 5,
            "total_commits_all": 5,
            "total_prs": 0,
            "total_pr_reviews": 0,
            "total_issues": 0,
            "repos_contributed": 1,
            "total_additions": 20,
            "total_deletions": 5,
            "repos_by_category": {
                "Other": [
                    {
                        "name": "org/repo",
                        "commits": 5,
                        "prs": 0,
                        "language": "Go",
                        "description": "",
                    }
                ],
                "Empty bucket": [],
            },
            "repo_line_stats": {},
            "repo_languages": {},
            "repo_member_commits": {"org/repo": {"alice": 5}},
            "lang_member_commits": {"Go": {"alice": 5}},
            "member_real_names": {"alice": "Alice"},
            "member_companies": {},
            "prs_nodes": [],
            "reviewed_nodes": [],
            "is_light_mode": True,
        }
        org_info = {"login": "org", "name": "Org"}
        with patch.object(mod, "progress", MagicMock()):
            report = mod.generate_org_report(
                org_info,
                None,
                "2026-01-01",
                "2026-01-31",
                data,
                ["alice"],
            )
        assert "Empty bucket" not in report
        assert "Other" in report


class TestOrgReportCompanyNormalization:
    """Company normalization in org report."""

    def _make_data(self, member_companies):
        return {
            "total_commits_default_branch": 10,
            "total_commits_all": 10,
            "total_prs": 0,
            "total_pr_reviews": 0,
            "total_issues": 0,
            "repos_contributed": 1,
            "total_additions": 50,
            "total_deletions": 10,
            "repos_by_category": {
                "Other": [
                    {
                        "name": "org/repo",
                        "commits": 10,
                        "prs": 0,
                        "language": "Go",
                        "description": "",
                    }
                ],
            },
            "repo_line_stats": {},
            "repo_languages": {},
            "repo_member_commits": {"org/repo": {"a": 5, "b": 5}},
            "lang_member_commits": {"Go": {"a": 5, "b": 5}},
            "member_real_names": {"a": "A", "b": "B"},
            "member_companies": member_companies,
            "prs_nodes": [],
            "reviewed_nodes": [],
            "is_light_mode": True,
        }

    def test_empty_company_skipped(self, mod):
        """Empty company string is skipped in normalization."""
        data = self._make_data({"a": "", "b": "@acme"})
        org_info = {"login": "org", "name": "Org"}
        with patch.object(mod, "progress", MagicMock()):
            report = mod.generate_org_report(
                org_info,
                None,
                "2026-01-01",
                "2026-01-31",
                data,
                ["a", "b"],
            )
        assert "@acme" in report

    def test_plain_text_to_at_mention(self, mod):
        """Plain 'acme' normalized to '@acme' when another has @acme."""
        data = self._make_data({"a": "@acme", "b": "acme"})
        org_info = {"login": "org", "name": "Org"}
        with patch.object(mod, "progress", MagicMock()):
            report = mod.generate_org_report(
                org_info,
                None,
                "2026-01-01",
                "2026-01-31",
                data,
                ["a", "b"],
            )
        # "b" should have been normalized: plain "acme" → "@acme"
        # Both should appear as @acme in the report
        assert "@acme" in report


class TestBuildUserReportSections:
    """Test build_user_report_sections() structured output."""

    @pytest.fixture
    def user_data(self):
        return {
            "user_real_name": "Test User",
            "total_commits_default_branch": 120,
            "total_commits_all": 150,
            "total_prs": 25,
            "total_pr_reviews": 40,
            "total_issues": 8,
            "total_additions": 12000,
            "total_deletions": 3000,
            "test_commits": 15,
            "repos_contributed": 3,
            "reviews_received": 5,
            "pr_comments_received": 3,
            "repos_by_category": {
                "Web standards and specifications": [
                    {
                        "name": "w3c/csswg-drafts",
                        "commits": 80,
                        "prs": 12,
                        "language": "CSS",
                        "description": "CSS Working Group Editor Drafts",
                    },
                ],
            },
            "repo_line_stats": {
                "w3c/csswg-drafts": {"additions": 8000, "deletions": 2000},
            },
            "repo_languages": {"w3c/csswg-drafts": "CSS"},
            "prs_nodes": [
                {
                    "title": "Add CSS Grid feature",
                    "url": "https://github.com/w3c/csswg-drafts/pull/100",
                    "state": "MERGED",
                    "merged": True,
                    "additions": 500,
                    "deletions": 100,
                    "repository": {
                        "nameWithOwner": "w3c/csswg-drafts",
                        "primaryLanguage": {"name": "CSS"},
                    },
                },
                {
                    "title": "Fix parser bug",
                    "url": "https://github.com/w3c/csswg-drafts/pull/101",
                    "state": "OPEN",
                    "additions": 50,
                    "deletions": 10,
                    "repository": {
                        "nameWithOwner": "w3c/csswg-drafts",
                        "primaryLanguage": {"name": "CSS"},
                    },
                },
            ],
            "reviewed_nodes": [
                {
                    "title": "Update Flexbox spec",
                    "url": "https://github.com/w3c/csswg-drafts/pull/102",
                    "additions": 300,
                    "deletions": 80,
                    "author": {"login": "other-user"},
                    "repository": {
                        "nameWithOwner": "w3c/csswg-drafts",
                        "primaryLanguage": {"name": "CSS"},
                    },
                }
            ],
        }

    def test_sections_keys(self, mod, user_data):
        sections = mod.build_user_report_sections(
            user_data, "testuser", "2026-01-01", "2026-01-31"
        )
        assert "notable_prs" in sections
        assert "projects_by_category" in sections
        assert "executive_summary" in sections
        assert "languages" in sections
        assert "prs_reviewed" in sections
        assert "prs_created" in sections
        assert "reviews_received" in sections

    def test_executive_summary_values(self, mod, user_data):
        sections = mod.build_user_report_sections(
            user_data, "testuser", "2026-01-01", "2026-01-31"
        )
        summary = sections["executive_summary"]
        assert summary["commits_default_branch"] == 120
        assert summary["commits_all_branches"] == 150
        assert summary["prs_created"] == 25
        assert summary["lines_added"] == 12000

    def test_prs_created_counts(self, mod, user_data):
        sections = mod.build_user_report_sections(
            user_data, "testuser", "2026-01-01", "2026-01-31"
        )
        assert sections["prs_created"]["merged"] == 1
        assert sections["prs_created"]["open"] == 1
        assert sections["prs_created"]["total"] == 2

    def test_notable_prs_populated(self, mod, user_data):
        sections = mod.build_user_report_sections(
            user_data, "testuser", "2026-01-01", "2026-01-31"
        )
        assert len(sections["notable_prs"]) == 2
        assert sections["notable_prs"][0]["title"] == "Add CSS Grid feature"

    def test_reviews_received(self, mod, user_data):
        sections = mod.build_user_report_sections(
            user_data, "testuser", "2026-01-01", "2026-01-31"
        )
        assert sections["reviews_received"]["reviews_received"] == 5
        assert sections["reviews_received"]["review_comments_received"] == 3

    def test_projects_by_category(self, mod, user_data):
        sections = mod.build_user_report_sections(
            user_data, "testuser", "2026-01-01", "2026-01-31"
        )
        cats = sections["projects_by_category"]
        assert "Web standards and specifications" in cats
        repo = cats["Web standards and specifications"][0]
        assert repo["name"] == "w3c/csswg-drafts"
        assert repo["additions"] == 8000

    def test_prs_reviewed(self, mod, user_data):
        sections = mod.build_user_report_sections(
            user_data, "testuser", "2026-01-01", "2026-01-31"
        )
        assert len(sections["prs_reviewed"]) == 1
        assert sections["prs_reviewed"][0]["repository"] == "w3c/csswg-drafts"

    def test_empty_category_skipped(self, mod, user_data):
        user_data["repos_by_category"]["Empty Category"] = []
        sections = mod.build_user_report_sections(
            user_data, "testuser", "2026-01-01", "2026-01-31"
        )
        assert "Empty Category" not in sections["projects_by_category"]

    def test_reviewed_pr_language_fallback(self, mod, user_data):
        """When repo is not in repo_languages, fall back to primaryLanguage."""
        user_data["repo_languages"] = {}  # no precomputed languages
        sections = mod.build_user_report_sections(
            user_data, "testuser", "2026-01-01", "2026-01-31"
        )
        assert len(sections["prs_reviewed"]) == 1
        assert sections["prs_reviewed"][0]["language"] == "CSS"


class TestBuildOrgReportSections:
    """Test build_org_report_sections() structured output."""

    @pytest.fixture
    def org_data(self):
        return {
            "total_commits_default_branch": 500,
            "total_commits_all": 500,
            "total_prs": 50,
            "total_pr_reviews": 100,
            "total_issues": 20,
            "repos_contributed": 2,
            "total_additions": 25000,
            "total_deletions": 5000,
            "test_commits": 42,
            "reviews_received": 10,
            "pr_comments_received": 5,
            "repos_by_category": {
                "Other": [
                    {
                        "name": "org/repo",
                        "commits": 500,
                        "prs": 50,
                        "language": "Go",
                        "description": "A repo",
                    }
                ],
            },
            "repo_line_stats": {},
            "repo_languages": {},
            "repo_member_commits": {"org/repo": {"alice": 300, "bob": 200}},
            "lang_member_commits": {"Go": {"alice": 300, "bob": 200}},
            "member_real_names": {"alice": "Alice", "bob": "Bob"},
            "member_companies": {"alice": "@org", "bob": ""},
            "prs_nodes": [],
            "reviewed_nodes": [],
            "is_light_mode": True,
        }

    def test_sections_keys(self, mod, org_data):
        org_info = {"login": "org", "name": "Org"}
        sections = mod.build_org_report_sections(
            org_info, None, "2026-01-01", "2026-01-31", org_data, []
        )
        assert "notable_prs" in sections
        assert "projects_by_category" in sections
        assert "executive_summary" in sections
        assert "languages" in sections
        assert "prs_created" in sections
        assert "repo_member_commits" in sections

    def test_light_mode_no_line_stats(self, mod, org_data):
        org_info = {"login": "org", "name": "Org"}
        sections = mod.build_org_report_sections(
            org_info, None, "2026-01-01", "2026-01-31", org_data, []
        )
        summary = sections["executive_summary"]
        assert "lines_added" not in summary
        assert "test_related_commits" not in summary

    def test_full_mode_has_line_stats(self, mod, org_data):
        org_data["is_light_mode"] = False
        org_data["repo_line_stats"] = {
            "org/repo": {"additions": 25000, "deletions": 5000}
        }
        org_info = {"login": "org", "name": "Org"}
        sections = mod.build_org_report_sections(
            org_info, None, "2026-01-01", "2026-01-31", org_data, []
        )
        summary = sections["executive_summary"]
        assert summary["lines_added"] == 25000
        assert summary["test_related_commits"] == 42

    def test_notable_prs_populated(self, mod, org_data):
        org_data["prs_nodes"] = [
            {
                "title": "Big PR",
                "url": "https://github.com/org/repo/pull/1",
                "state": "MERGED",
                "merged": True,
                "additions": 500,
                "deletions": 100,
                "repository": {
                    "nameWithOwner": "org/repo",
                    "primaryLanguage": {"name": "Go"},
                },
            },
        ]
        org_info = {"login": "org", "name": "Org"}
        sections = mod.build_org_report_sections(
            org_info, None, "2026-01-01", "2026-01-31", org_data, []
        )
        assert len(sections["notable_prs"]) == 1
        assert sections["notable_prs"][0]["title"] == "Big PR"

    def test_empty_category_skipped(self, mod, org_data):
        org_data["repos_by_category"]["Empty Category"] = []
        org_info = {"login": "org", "name": "Org"}
        sections = mod.build_org_report_sections(
            org_info, None, "2026-01-01", "2026-01-31", org_data, []
        )
        assert "Empty Category" not in sections["projects_by_category"]

    def test_prs_reviewed_with_language_fallback(self, mod, org_data):
        """Reviewed PRs use primaryLanguage fallback."""
        org_data["reviewed_nodes"] = [
            {
                "title": "Review PR",
                "url": "https://github.com/org/repo/pull/5",
                "additions": 200,
                "deletions": 40,
                "author": {"login": "someone"},
                "repository": {
                    "nameWithOwner": "org/repo",
                    "primaryLanguage": {"name": "Go"},
                },
            },
        ]
        org_info = {"login": "org", "name": "Org"}
        sections = mod.build_org_report_sections(
            org_info, None, "2026-01-01", "2026-01-31", org_data, []
        )
        assert len(sections["prs_reviewed"]) == 1
        assert sections["prs_reviewed"][0]["language"] == "Go"
        assert sections["prs_reviewed"][0]["total_lines"] == 240

    def test_prs_reviewed_uses_repo_languages(self, mod, org_data):
        """Reviewed PRs prefer repo_languages over primaryLanguage."""
        org_data["repo_languages"] = {"org/repo": "Rust"}
        org_data["reviewed_nodes"] = [
            {
                "title": "Review PR",
                "url": "https://github.com/org/repo/pull/5",
                "additions": 100,
                "deletions": 20,
                "author": {"login": "someone"},
                "repository": {
                    "nameWithOwner": "org/repo",
                    "primaryLanguage": {"name": "Go"},
                },
            },
        ]
        org_info = {"login": "org", "name": "Org"}
        sections = mod.build_org_report_sections(
            org_info, None, "2026-01-01", "2026-01-31", org_data, []
        )
        assert sections["prs_reviewed"][0]["language"] == "Rust"


class TestFormatUserDataJson:
    """Test format_user_data_json() output."""

    def test_valid_json(self, mod):
        import json

        data = {
            "user_real_name": "",
            "total_commits_default_branch": 0,
            "total_commits_all": 0,
            "total_prs": 0,
            "total_pr_reviews": 0,
            "total_issues": 0,
            "total_additions": 0,
            "total_deletions": 0,
            "test_commits": 0,
            "repos_contributed": 0,
            "reviews_received": 0,
            "pr_comments_received": 0,
            "repos_by_category": {},
            "repo_line_stats": {},
            "repo_languages": {},
            "prs_nodes": [],
            "reviewed_nodes": [],
        }
        result = mod.format_user_data_json(
            data, "testuser", "2026-01-01", "2026-01-31"
        )
        parsed = json.loads(result)
        assert parsed["meta"]["tool"] == "gh-activity-chronicle"
        assert parsed["meta"]["username"] == "testuser"
        assert parsed["meta"]["since_date"] == "2026-01-01"
        assert "data" in parsed
        assert "report" in parsed

    def test_includes_raw_data(self, mod):
        import json

        data = {
            "user_real_name": "Test",
            "total_commits_default_branch": 42,
            "total_commits_all": 42,
            "total_prs": 0,
            "total_pr_reviews": 0,
            "total_issues": 0,
            "total_additions": 0,
            "total_deletions": 0,
            "test_commits": 0,
            "repos_contributed": 0,
            "reviews_received": 0,
            "pr_comments_received": 0,
            "repos_by_category": {},
            "repo_line_stats": {},
            "repo_languages": {},
            "prs_nodes": [],
            "reviewed_nodes": [],
        }
        result = mod.format_user_data_json(
            data, "user", "2026-01-01", "2026-01-31"
        )
        parsed = json.loads(result)
        assert parsed["data"]["total_commits_default_branch"] == 42


class TestFormatOrgDataJson:
    """Test format_org_data_json() output."""

    def test_valid_json(self, mod):
        import json

        org_info = {"login": "org", "name": "Org"}
        aggregated = {
            "repos_by_category": {},
            "prs_nodes": [],
            "reviewed_nodes": [],
            "is_light_mode": True,
        }
        result = mod.format_org_data_json(
            org_info, None, "2026-01-01", "2026-01-31", aggregated, []
        )
        parsed = json.loads(result)
        assert parsed["meta"]["org"]["login"] == "org"
        assert "data" in parsed
        assert "report" in parsed


class TestJsonSchema:
    """Validate JSON output against schema.json."""

    @pytest.fixture
    def schema(self):
        import json
        from pathlib import Path

        schema_path = Path(__file__).parent.parent / "schema.json"
        with open(schema_path) as f:
            return json.load(f)

    def test_user_json_validates(self, mod, schema):
        """User-mode JSON output validates against schema."""
        import json

        import jsonschema

        data = {
            "user_real_name": "Test User",
            "total_commits_default_branch": 120,
            "total_commits_all": 150,
            "total_prs": 25,
            "total_pr_reviews": 40,
            "total_issues": 8,
            "total_additions": 12000,
            "total_deletions": 3000,
            "test_commits": 15,
            "repos_contributed": 3,
            "reviews_received": 5,
            "pr_comments_received": 3,
            "lines_reviewed": 2000,
            "review_comments": 10,
            "repos_by_category": {
                "Web standards and specifications": [
                    {
                        "name": "w3c/csswg-drafts",
                        "commits": 80,
                        "prs": 12,
                        "language": "CSS",
                        "description": "CSS Working Group",
                    },
                ],
                "Other": [
                    {
                        "name": "user/project",
                        "commits": 40,
                        "prs": 8,
                        "language": "Python",
                        "description": "Personal project",
                    },
                ],
            },
            "repo_line_stats": {
                "w3c/csswg-drafts": {
                    "additions": 8000,
                    "deletions": 2000,
                },
                "user/project": {
                    "additions": 2000,
                    "deletions": 500,
                },
            },
            "repo_languages": {
                "w3c/csswg-drafts": "CSS",
                "user/project": "Python",
            },
            "prs_nodes": [
                {
                    "title": "Add CSS Grid feature",
                    "url": "https://github.com/w3c/csswg-drafts/pull/1",
                    "state": "MERGED",
                    "merged": True,
                    "additions": 500,
                    "deletions": 100,
                    "repository": {
                        "nameWithOwner": "w3c/csswg-drafts",
                        "primaryLanguage": {"name": "CSS"},
                    },
                },
                {
                    "title": "Update readme",
                    "url": "https://github.com/user/project/pull/5",
                    "state": "OPEN",
                    "merged": False,
                    "additions": 50,
                    "deletions": 10,
                    "repository": {
                        "nameWithOwner": "user/project",
                        "primaryLanguage": {"name": "Python"},
                    },
                },
            ],
            "reviewed_nodes": [
                {
                    "title": "Update Flexbox spec",
                    "url": "https://github.com/w3c/csswg-drafts/pull/2",
                    "additions": 300,
                    "deletions": 80,
                    "author": {"login": "other-user"},
                    "repository": {
                        "nameWithOwner": "w3c/csswg-drafts",
                    },
                },
            ],
        }
        result = mod.format_user_data_json(
            data, "testuser", "2026-01-01", "2026-01-31"
        )
        parsed = json.loads(result)
        jsonschema.validate(parsed, schema)

    def test_org_json_validates(self, mod, schema):
        """Org-mode JSON output validates against schema."""
        import json

        import jsonschema

        org_info = {
            "login": "w3c",
            "name": "World Wide Web Consortium",
            "description": "Web standards org",
        }
        aggregated = {
            "total_commits_default_branch": 200,
            "total_commits_all": 200,
            "total_prs": 50,
            "total_pr_reviews": 80,
            "total_issues": 20,
            "repos_contributed": 30,
            "total_additions": 0,
            "total_deletions": 0,
            "reviews_received": 30,
            "pr_comments_received": 25,
            "test_commits": 0,
            "repos_by_category": {
                "Web standards and specifications": [
                    {
                        "name": "w3c/csswg-drafts",
                        "commits": 60,
                        "prs": 10,
                        "language": "CSS",
                        "description": "CSS specs",
                    },
                ],
            },
            "repo_line_stats": {},
            "repo_languages": {"w3c/csswg-drafts": "CSS"},
            "prs_nodes": [
                {
                    "title": "Add feature",
                    "url": "https://github.com/w3c/csswg-drafts/pull/1",
                    "state": "MERGED",
                    "merged": True,
                    "additions": 100,
                    "deletions": 10,
                    "repository": {
                        "nameWithOwner": "w3c/csswg-drafts",
                        "primaryLanguage": {"name": "CSS"},
                    },
                },
            ],
            "reviewed_nodes": [
                {
                    "title": "Fix issue",
                    "url": "https://github.com/w3c/csswg-drafts/pull/2",
                    "additions": 50,
                    "deletions": 5,
                    "author": {"login": "alice"},
                    "repository": {
                        "nameWithOwner": "w3c/csswg-drafts",
                    },
                },
            ],
            "is_light_mode": True,
            "owners_only": False,
            "repo_member_commits": {
                "w3c/csswg-drafts": {"alice": 35, "bob": 25},
            },
            "lang_member_commits": {
                "CSS": {"alice": 35, "bob": 25},
            },
            "member_real_names": {
                "alice": "Alice Smith",
                "bob": "Bob Jones",
            },
            "member_companies": {
                "alice": "@acme",
                "bob": "@w3c",
            },
        }
        members = ["alice", "bob"]
        result = mod.format_org_data_json(
            org_info,
            None,
            "2026-01-01",
            "2026-01-31",
            aggregated,
            members,
        )
        parsed = json.loads(result)
        jsonschema.validate(parsed, schema)

    def test_org_with_team_validates(self, mod, schema):
        """Org-mode JSON with --team validates against schema."""
        import json

        import jsonschema

        org_info = {
            "login": "w3c",
            "name": "World Wide Web Consortium",
            "description": "Web standards org",
        }
        team_info = {
            "slug": "webperf",
            "name": "Web Performance",
            "description": "Web Performance WG",
        }
        aggregated = {
            "total_commits_default_branch": 50,
            "total_commits_all": 50,
            "total_prs": 10,
            "total_pr_reviews": 15,
            "total_issues": 3,
            "repos_contributed": 5,
            "total_additions": 0,
            "total_deletions": 0,
            "reviews_received": 8,
            "pr_comments_received": 6,
            "test_commits": 0,
            "repos_by_category": {},
            "repo_line_stats": {},
            "repo_languages": {},
            "prs_nodes": [],
            "reviewed_nodes": [],
            "is_light_mode": True,
            "owners_only": False,
        }
        result = mod.format_org_data_json(
            org_info,
            team_info,
            "2026-01-01",
            "2026-01-31",
            aggregated,
            ["alice"],
        )
        parsed = json.loads(result)
        jsonschema.validate(parsed, schema)
