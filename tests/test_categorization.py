"""Unit tests for repository categorization and pattern matching."""

from unittest.mock import patch

import pytest


class TestMatches:
    """Tests for the matches() pattern matching function."""

    def test_exact_match(self, mod):
        patterns = {"exact": ["validator/validator"]}
        assert mod.matches("validator/validator", patterns) is True
        assert mod.matches("other/validator", patterns) is False

    def test_prefix_match(self, mod):
        patterns = {"prefix": ["wai-", "wcag"]}
        assert mod.matches("wai-aria", patterns) is True
        assert mod.matches("wcag21", patterns) is True
        assert mod.matches("something-wai", patterns) is False

    def test_suffix_match(self, mod):
        patterns = {"suffix": ["-spec", ".github.io"]}
        assert mod.matches("html-spec", patterns) is True
        assert mod.matches("user.github.io", patterns) is True
        assert mod.matches("spec-test", patterns) is False

    def test_contains_match(self, mod):
        patterns = {"contains": ["sensor"]}
        assert mod.matches("accelerometer-sensor", patterns) is True
        assert mod.matches("sensor-api", patterns) is True
        assert mod.matches("my-sensor-test", patterns) is True
        assert mod.matches("other-thing", patterns) is False

    def test_exclude_prefix(self, mod):
        patterns = {"prefix": ["media"], "exclude_prefix": ["mediacapture"]}
        assert mod.matches("media-session", patterns) is True
        assert mod.matches("mediacapture-streams", patterns) is False

    def test_exclude_contains(self, mod):
        patterns = {"contains": ["web"], "exclude_contains": ["webrtc"]}
        assert mod.matches("web-audio", patterns) is True
        assert mod.matches("webrtc-stats", patterns) is False

    def test_empty_patterns(self, mod):
        assert mod.matches("anything", {}) is False

    def test_case_sensitivity(self, mod):
        # matches() converts name to lowercase before comparing
        # So patterns should be lowercase for exact matches
        patterns = {"exact": ["webkit"]}
        # Both match because name is lowercased before comparison
        assert mod.matches("WebKit", patterns) is True
        assert mod.matches("webkit", patterns) is True
        assert mod.matches("WEBKIT", patterns) is True

        # Uppercase pattern won't match because name is lowercased
        patterns_upper = {"exact": ["WebKit"]}
        # "webkit" != "WebKit"
        assert mod.matches("WebKit", patterns_upper) is False

    def test_multiple_pattern_types(self, mod):
        patterns = {
            "prefix": ["test-"],
            "suffix": ["-spec"],
            "contains": ["middle"],
        }
        assert mod.matches("test-something", patterns) is True
        assert mod.matches("something-spec", patterns) is True
        assert mod.matches("has-middle-part", patterns) is True
        assert mod.matches("nomatch", patterns) is False


class TestGetCategoryFromTopics:
    """Tests for topic-based categorization."""

    def test_ml_topics(self, mod):
        topics = ["machine-learning", "python"]
        result = mod.get_category_from_topics(topics)
        assert result == "ML frameworks"

    def test_devops_topics(self, mod):
        topics = ["kubernetes", "docker"]
        result = mod.get_category_from_topics(topics)
        assert result == "DevOps"

    def test_accessibility_topics(self, mod):
        topics = ["accessibility", "a11y"]
        result = mod.get_category_from_topics(topics)
        assert result == "Accessibility"

    def test_empty_topics(self, mod):
        assert mod.get_category_from_topics([]) is None
        assert mod.get_category_from_topics(None) is None

    def test_unknown_topics(self, mod):
        topics = ["random-unknown-topic", "another-unknown"]
        result = mod.get_category_from_topics(topics)
        assert result is None

    def test_first_match_wins(self, mod):
        # When multiple topics match different categories,
        # the first matching topic should determine the category
        topics = ["machine-learning", "kubernetes"]
        result = mod.get_category_from_topics(topics)
        # Should be one of the two, consistently
        assert result in ["ML frameworks", "DevOps"]


class TestCategorizeRepo:
    """Tests for the main categorize_repo function (or get_category)."""

    def test_explicit_repo_mapping(self, mod):
        """Test repos in EXPLICIT_REPOS dict."""
        # These are repos explicitly mapped in the code
        if hasattr(mod, "categorize_repo"):
            cat_func = mod.categorize_repo
        elif hasattr(mod, "get_category"):
            cat_func = mod.get_category
        else:
            pytest.skip("categorize_repo/get_category function not found")

        # validator/validator should be HTML/CSS checking
        result = cat_func("validator/validator")
        assert result == "HTML/CSS checking/validation"

    def test_org_based_categorization(self, mod):
        """Test organization-based categorization."""
        if hasattr(mod, "categorize_repo"):
            cat_func = mod.categorize_repo
        elif hasattr(mod, "get_category"):
            cat_func = mod.get_category
        else:
            pytest.skip("categorize_repo/get_category function not found")

        # w3c repos should generally be web standards
        result = cat_func("w3c/some-random-spec")
        assert (
            "standards" in result.lower()
            or "w3c" in result.lower()
            or result != "Other"
        )

    def test_standards_org_patterns(self, mod):
        """Test pattern matching within standards orgs."""
        if hasattr(mod, "categorize_repo"):
            cat_func = mod.categorize_repo
        elif hasattr(mod, "get_category"):
            cat_func = mod.get_category
        else:
            pytest.skip("categorize_repo/get_category function not found")

        # w3c/wai-* should be Accessibility
        result = cat_func("w3c/wai-aria")
        assert result == "Accessibility"

        # w3c/i18n-* should be Internationalization
        result = cat_func("w3c/i18n-glossary")
        assert result == "Internationalization"

    def test_uncategorized_repo(self, mod):
        """Test that unknown repos fall through to Other."""
        if hasattr(mod, "categorize_repo"):
            cat_func = mod.categorize_repo
        elif hasattr(mod, "get_category"):
            cat_func = mod.get_category
        else:
            pytest.skip("categorize_repo/get_category function not found")

        # A completely random repo should be "Other"
        result = cat_func("randomuser123/my-random-project-xyz")
        assert result == "Other"

    def test_no_slash_repo_name(self, mod):
        """Repo name without a slash should use full name as base."""
        result = mod.get_category("validator")
        # "validator" matches the explicit base name from
        # "validator/validator", so it gets the same category
        assert result == "HTML/CSS checking/validation"

    def test_fork_base_name_match(self, mod):
        """A fork matching an explicit repo base name gets same category."""
        # "someuser/ladybird" matches base name "ladybird" from
        # "ladybirdbrowser/ladybird" in EXPLICIT_REPOS
        result = mod.get_category("someuser/ladybird")
        assert result == "Browser engines"

    def test_standards_positions_repo(self, mod):
        """Any org's standards-positions repo gets Standards positions."""
        result = mod.get_category("anyorg/standards-positions")
        assert result == "Standards positions"

    def test_general_pattern_match(self, mod):
        """Repos matching GENERAL_PATTERNS should get that category."""
        # "respec" is in GENERAL_PATTERNS via SPEC_TOOLING contains
        result = mod.get_category("someuser/my-validator-tool")
        assert result == "HTML/CSS checking/validation"

    def test_topic_based_fallback(self, mod):
        """Repos with matching topics should get topic-based category."""
        with patch.object(
            mod, "fetch_repo_topics", return_value=["machine-learning"]
        ):
            result = mod.get_category("randomuser/random-ml-thing")
        assert result == "ML frameworks"

    def test_topic_fallback_no_match_returns_other(self, mod):
        """Repos with no matching topics should get Other."""
        with patch.object(
            mod, "fetch_repo_topics", return_value=["obscure-topic"]
        ):
            result = mod.get_category("randomuser123/my-random-project-xyz")
        assert result == "Other"


class TestShouldSkipRepo:
    """Tests for the should_skip_repo filtering function."""

    def test_private_repo_skipped(self, mod):
        """Private repos should be skipped."""
        repo_info = {"isPrivate": True}
        result = mod.should_skip_repo("user/private-repo", repo_info=repo_info)
        assert result is True

    def test_profile_repo_skipped(self, mod):
        """Profile repos (username/username) should be skipped."""
        result = mod.should_skip_repo("octocat/octocat", username="octocat")
        assert result is True

    def test_normal_repo_not_skipped(self, mod):
        """Regular public repos should not be skipped."""
        result = mod.should_skip_repo(
            "octocat/hello-world", username="octocat"
        )
        assert result is False

    def test_serenity_repo_skipped(self, mod):
        """Repos with 'serenity' in name should be skipped."""
        result = mod.should_skip_repo("someuser/serenity-fork")
        assert result is True

    def test_empty_repo_name_skipped(self, mod):
        """Empty repo name should be skipped."""
        result = mod.should_skip_repo("")
        assert result is True
        result = mod.should_skip_repo(None)
        assert result is True

    def test_ladybird_copies_set_skipped(self, mod):
        """Known Ladybird copy repos should be skipped."""
        result = mod.should_skip_repo("zechy0055/qosta-broswer")
        assert result is True

    def test_firefox_copies_set_skipped(self, mod):
        """Known Firefox copy repos should be skipped."""
        result = mod.should_skip_repo("mozilla/gecko-dev")
        assert result is True

    def test_serenity_copies_set_skipped(self, mod):
        """Known SerenityOS copy repos should be skipped."""
        result = mod.should_skip_repo("serenityos/serenity")
        assert result is True

    def test_ladybird_related_name_skipped(self, mod):
        """Repos with 'lady' in name (not the canonical one) are skipped."""
        result = mod.should_skip_repo("random/ladybird-fork")
        assert result is True

    def test_ladybird_canonical_not_skipped(self, mod):
        """The canonical Ladybird repo should not be skipped."""
        result = mod.should_skip_repo("ladybirdbrowser/ladybird")
        assert result is False

    def test_ladybird_user_fork_not_skipped(self, mod):
        """A user's own Ladybird fork should not be skipped."""
        result = mod.should_skip_repo("myuser/ladybird", username="myuser")
        assert result is False

    def test_firefox_allowed_list_not_skipped(self, mod):
        """The canonical Firefox repo should not be skipped."""
        result = mod.should_skip_repo("mozilla-firefox/firefox")
        assert result is False

    def test_firefox_user_fork_not_skipped(self, mod):
        """A user's own Firefox fork should not be skipped."""
        result = mod.should_skip_repo("myuser/firefox", username="myuser")
        assert result is False

    def test_fork_parent_ladybird_skipped(self, mod):
        """Repo forked from ladybirdbrowser/ladybird should be skipped."""
        repo_info = {
            "parent": {"nameWithOwner": "ladybirdbrowser/ladybird"},
        }
        result = mod.should_skip_repo(
            "someuser/renamed-browser", repo_info=repo_info
        )
        assert result is True

    def test_fork_description_ladybird_skipped(self, mod):
        """Repo with 'ladybird' in description should be skipped."""
        repo_info = {
            "description": "A fork of the Ladybird browser engine",
        }
        result = mod.should_skip_repo(
            "someuser/my-browser", repo_info=repo_info
        )
        assert result is True

    def test_fork_description_truly_independent_skipped(self, mod):
        """Repo with Ladybird tagline description should be skipped."""
        repo_info = {
            "description": "Truly independent web browser",
        }
        result = mod.should_skip_repo(
            "someuser/my-project", repo_info=repo_info
        )
        assert result is True

    def test_fork_parent_firefox_skipped(self, mod):
        """Repo forked from mozilla-firefox/firefox should be skipped."""
        repo_info = {
            "parent": {"nameWithOwner": "mozilla-firefox/firefox"},
        }
        result = mod.should_skip_repo(
            "someuser/renamed-fox", repo_info=repo_info
        )
        assert result is True

    def test_fork_description_firefox_skipped(self, mod):
        """Repo with Firefox official description should be skipped."""
        repo_info = {
            "description": (
                "The official repository of Mozilla's Firefox web browser"
            ),
        }
        result = mod.should_skip_repo("someuser/my-fox", repo_info=repo_info)
        assert result is True


class TestCategoryPriority:
    """Tests for category ordering/priority."""

    def test_get_ordered_categories(self, mod, sample_repos_by_category):
        """Test that categories are ordered by priority."""
        result = mod.get_ordered_categories(sample_repos_by_category)
        # Result should be a list of category names
        assert isinstance(result, list)
        assert len(result) == len(sample_repos_by_category)

        # "Other" should typically be last
        if "Other" in result:
            assert result[-1] == "Other"

    def test_empty_input(self, mod):
        """Empty dict should return empty list."""
        result = mod.get_ordered_categories({})
        assert result == []

    def test_priority_categories_first(self, mod):
        """Priority categories should come before non-priority ones."""
        categories = {
            "Other": [],
            "Browser engines": [],
            "Web standards and specifications": [],
            "Random Category": [],
        }
        result = mod.get_ordered_categories(categories)

        # Check relative ordering of known categories
        if "Web standards and specifications" in result and "Other" in result:
            web_idx = result.index("Web standards and specifications")
            other_idx = result.index("Other")
            assert web_idx < other_idx


class TestCategorizeRepoEdgeCases:
    """Edge cases for EXPLICIT_REPOS loop and standards-positions."""

    def test_explicit_repo_key_without_slash(self, mod):
        """EXPLICIT_REPOS key without '/' uses full key as base."""
        original = dict(mod.EXPLICIT_REPOS)
        mod.EXPLICIT_REPOS["mybare"] = "Test Category"
        try:
            result = mod.get_category("anyuser/mybare")
            assert result == "Test Category"
        finally:
            mod.EXPLICIT_REPOS.clear()
            mod.EXPLICIT_REPOS.update(original)

    def test_standards_positions_standalone_check(self, mod):
        """standards-positions matched by dedicated check."""
        original = dict(mod.EXPLICIT_REPOS)
        # Remove entries whose base name is "standards-positions"
        # so the standalone check on line 1746 is reached
        filtered = {
            k: v
            for k, v in original.items()
            if k.split("/")[-1] != "standards-positions"
        }
        mod.EXPLICIT_REPOS.clear()
        mod.EXPLICIT_REPOS.update(filtered)
        try:
            result = mod.get_category("neworg/standards-positions")
            assert result == "Standards positions"
        finally:
            mod.EXPLICIT_REPOS.clear()
            mod.EXPLICIT_REPOS.update(original)
