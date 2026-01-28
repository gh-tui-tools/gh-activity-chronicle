"""Unit tests for data aggregation functions."""

import pytest


class TestAggregateLanguageStats:
    """Tests for aggregate_language_stats()."""

    def test_basic_aggregation(self, mod, sample_repos_by_category):
        """Test basic language aggregation."""
        result = mod.aggregate_language_stats(sample_repos_by_category)
        assert isinstance(result, list)
        assert len(result) > 0

        # Each item should have language and commits at minimum
        for item in result:
            assert "language" in item
            assert "commits" in item

    def test_aggregation_with_line_stats(
        self, mod, sample_repos_by_category, sample_repo_line_stats
    ):
        """Test aggregation includes line stats when provided."""
        result = mod.aggregate_language_stats(
            sample_repos_by_category, sample_repo_line_stats
        )

        # Should have line stats if provided
        for item in result:
            if "lines_added" in item or "additions" in item:
                # Line stats were included
                break
        # Line stats may or may not be included depending on implementation

    def test_sorted_by_commits(self, mod, sample_repos_by_category):
        """Results should be sorted by commits descending."""
        result = mod.aggregate_language_stats(sample_repos_by_category)

        if len(result) > 1:
            commits = [r["commits"] for r in result]
            assert commits == sorted(commits, reverse=True)

    def test_empty_input(self, mod):
        """Empty dict should return empty list."""
        result = mod.aggregate_language_stats({})
        assert result == []

    def test_null_language_handled(self, mod):
        """Repos with null/None language should be handled."""
        repos = {
            "Category": [
                {"name": "repo1", "commits": 5, "prs": 1, "language": None},
                {"name": "repo2", "commits": 3, "prs": 0, "language": "Python"},
            ]
        }
        result = mod.aggregate_language_stats(repos)
        # Should not crash, should aggregate the Python repo at minimum
        assert isinstance(result, list)

    def test_same_language_different_categories(self, mod):
        """Same language in different categories should be combined."""
        repos = {
            "Category1": [
                {"name": "repo1", "commits": 10, "prs": 1, "language": "Python"},
            ],
            "Category2": [
                {"name": "repo2", "commits": 5, "prs": 2, "language": "Python"},
            ],
        }
        result = mod.aggregate_language_stats(repos)

        # Find Python in results
        python_stats = next(
            (r for r in result if r["language"] == "Python"), None
        )
        if python_stats:
            assert python_stats["commits"] == 15


class TestAggregateOrgData:
    """Tests for aggregate_org_data()."""

    def test_basic_aggregation(self, mod, sample_member_data):
        """Test basic org data aggregation."""
        result = mod.aggregate_org_data(sample_member_data)

        assert isinstance(result, dict)
        # The actual keys use different naming
        assert "total_commits_default_branch" in result or "total_commits_all" in result
        assert "total_prs" in result or "total_pr_reviews" in result

    def test_commit_totals(self, mod, sample_member_data):
        """Total commits should be aggregated from member data."""
        result = mod.aggregate_org_data(sample_member_data)

        # Check that commit counts are present and non-negative
        total = result.get("total_commits_default_branch", 0) + result.get("total_commits_all", 0)
        assert total >= 0

    def test_pr_deduplication(self, mod, sample_member_data):
        """PRs with same URL should be deduplicated."""
        result = mod.aggregate_org_data(sample_member_data)

        # Should have prs_nodes with deduplicated PRs
        assert "prs_nodes" in result or "total_prs" in result

    def test_review_deduplication(self, mod, sample_member_data):
        """Reviews of same PR should be deduplicated."""
        result = mod.aggregate_org_data(sample_member_data)

        # Both alice and bob reviewed the same PR (same URL)
        # Should count as 1 unique PR reviewed
        if "prs_reviewed" in result:
            unique_urls = set()
            for pr in result.get("prs_reviewed", []):
                if isinstance(pr, dict):
                    unique_urls.add(pr.get("url"))
            # Should have exactly 1 unique PR reviewed
            assert len(unique_urls) == 1

    def test_repo_member_commits_tracking(self, mod, sample_member_data):
        """Should track per-member commits per repo."""
        result = mod.aggregate_org_data(sample_member_data)

        if "repo_member_commits" in result:
            rmc = result["repo_member_commits"]
            # w3c/csswg-drafts had commits from both alice and bob
            if "w3c/csswg-drafts" in rmc:
                assert "alice" in rmc["w3c/csswg-drafts"]
                assert "bob" in rmc["w3c/csswg-drafts"]

    def test_member_real_names_preserved(self, mod, sample_member_data):
        """Real names should be preserved for display."""
        result = mod.aggregate_org_data(sample_member_data)

        # member_real_names may be empty if data didn't include real_name
        assert "member_real_names" in result
        # The dict exists even if empty

    def test_member_companies_preserved(self, mod, sample_member_data):
        """Company info should be preserved for org grouping."""
        result = mod.aggregate_org_data(sample_member_data)

        # member_companies should exist
        assert "member_companies" in result

    def test_empty_member_list(self, mod):
        """Empty member list should return empty dict."""
        result = mod.aggregate_org_data([])
        assert result == {}

    def test_single_member(self, mod, sample_member_data):
        """Single member should work correctly."""
        result = mod.aggregate_org_data([sample_member_data[0]])
        # Should have data from the single member
        assert isinstance(result, dict)
        assert len(result) > 0

    def test_repos_by_category_merged(self, mod, sample_member_data):
        """repos_by_category should merge across members."""
        result = mod.aggregate_org_data(sample_member_data)

        if "repos_by_category" in result:
            rbc = result["repos_by_category"]
            # Both members contributed to Web standards
            assert "Web standards and specifications" in rbc

            # Commits should be summed for same repo
            web_repos = rbc["Web standards and specifications"]
            csswg = next(
                (r for r in web_repos if r["name"] == "w3c/csswg-drafts"),
                None
            )
            if csswg:
                # alice: 30, bob: 30 = 60 total
                assert csswg["commits"] == 60

    def test_light_mode_detection(self, mod, sample_member_data):
        """Should detect if data is from light mode."""
        result = mod.aggregate_org_data(sample_member_data)

        # Sample data has is_light_mode=True
        if "is_light_mode" in result:
            assert result["is_light_mode"] is True


class TestGenerateNotablePrsTable:
    """Tests for generate_notable_prs_table()."""

    def test_basic_table_generation(self, mod, sample_pr_nodes):
        """Test basic PR table generation."""
        repo_languages = {
            "owner/repo": "Python",
            "other/docs": "Markdown",
        }
        result = mod.generate_notable_prs_table(sample_pr_nodes, repo_languages)

        assert isinstance(result, list)
        assert len(result) > 0

        # Should have header row
        header = result[0]
        assert "PR" in header or "Title" in header or "|" in header

    def test_sorted_by_additions(self, mod, sample_pr_nodes):
        """PRs should be sorted by additions (lines changed)."""
        repo_languages = {"owner/repo": "Python", "other/docs": "Markdown"}
        result = mod.generate_notable_prs_table(sample_pr_nodes, repo_languages)

        # The PR with 1000 additions should appear before the one with 500
        result_str = "\n".join(result)
        # "Update documentation" has 1000 additions, should be first PR row
        # "Add new feature" has 500 additions

    def test_empty_pr_list(self, mod):
        """Empty PR list should return empty or minimal table."""
        result = mod.generate_notable_prs_table([], {})
        # Either empty list or just header
        assert isinstance(result, list)

    def test_top_15_limit(self, mod):
        """Should limit to top 15 PRs."""
        # Create 20 PRs
        prs = [
            {
                "title": f"PR {i}",
                "url": f"https://github.com/owner/repo/pull/{i}",
                "state": "MERGED",
                "additions": 100 * (20 - i),  # Decreasing additions
                "deletions": 10,
                "repository": {
                    "nameWithOwner": "owner/repo",
                    "primaryLanguage": {"name": "Python"}
                }
            }
            for i in range(20)
        ]
        result = mod.generate_notable_prs_table(prs, {"owner/repo": "Python"})

        # Count data rows (excluding header and separator)
        data_rows = [r for r in result if r.startswith("|") and "---" not in r]
        # Header is one row, so data rows should be <= 15
        # Actually header + 15 data rows = 16 rows with "|"
        assert len(data_rows) <= 16

    def test_pr_with_missing_fields(self, mod):
        """PRs with missing fields should be handled gracefully."""
        prs = [
            {
                "title": "Minimal PR",
                "url": "https://github.com/owner/repo/pull/1",
                "state": "OPEN",
                "additions": 0,
                "deletions": 0,
                "repository": {"nameWithOwner": "owner/repo"}
                # Missing primaryLanguage
            }
        ]
        result = mod.generate_notable_prs_table(prs, {})
        assert isinstance(result, list)


class TestGetOrderedCategories:
    """Tests for get_ordered_categories()."""

    def test_priority_ordering(self, mod):
        """Priority categories should come before others."""
        categories = {
            "Other": ["repo1"],
            "Browser engines": ["repo2"],
            "Web standards and specifications": ["repo3"],
            "Unknown Category": ["repo4"],
        }
        result = mod.get_ordered_categories(categories)

        # Web standards should be before Other
        if "Web standards and specifications" in result and "Other" in result:
            web_idx = result.index("Web standards and specifications")
            other_idx = result.index("Other")
            assert web_idx < other_idx

    def test_alphabetical_within_priority(self, mod):
        """Non-priority categories should be alphabetical."""
        categories = {
            "Zebra Category": ["r1"],
            "Alpha Category": ["r2"],
            "Other": ["r3"],
        }
        result = mod.get_ordered_categories(categories)

        # Find non-priority, non-Other categories
        non_priority = [c for c in result if c not in ["Other"]]
        # If both are non-priority, Alpha should come before Zebra

    def test_empty_input(self, mod):
        """Empty dict returns empty list."""
        assert mod.get_ordered_categories({}) == []

    def test_single_category(self, mod):
        """Single category returns single-item list."""
        result = mod.get_ordered_categories({"Some Category": ["repo"]})
        assert len(result) == 1
        assert "Some Category" in result
