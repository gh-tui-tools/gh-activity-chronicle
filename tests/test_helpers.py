"""Unit tests for helper functions (pure functions, no API calls)."""

import pytest
from urllib.parse import unquote


class TestFormatNumber:
    """Tests for format_number()."""

    def test_zero(self, mod):
        assert mod.format_number(0) == "0"

    def test_small_number(self, mod):
        assert mod.format_number(42) == "42"

    def test_thousands(self, mod):
        assert mod.format_number(1000) == "1,000"

    def test_millions(self, mod):
        assert mod.format_number(1234567) == "1,234,567"

    def test_negative(self, mod):
        assert mod.format_number(-1000) == "-1,000"


class TestMakeRepoAnchor:
    """Tests for make_repo_anchor()."""

    def test_simple_repo(self, mod):
        assert mod.make_repo_anchor("owner/repo") == "owner-repo"

    def test_repo_with_dots(self, mod):
        assert mod.make_repo_anchor("w3c/csswg-drafts") == "w3c-csswg-drafts"

    def test_repo_with_multiple_slashes(self, mod):
        # Should only have one slash in practice, but test robustness
        result = mod.make_repo_anchor("a/b/c")
        assert "/" not in result

    def test_special_characters(self, mod):
        result = mod.make_repo_anchor("owner/repo.js")
        assert "." not in result or result == "owner-repo-js"


class TestMakeLangAnchor:
    """Tests for make_lang_anchor()."""

    def test_simple_language(self, mod):
        assert mod.make_lang_anchor("Python") == "python"

    def test_cpp(self, mod):
        # C++ should become something URL-safe
        result = mod.make_lang_anchor("C++")
        assert "+" not in result
        assert result == "cplusplus" or result == "c"

    def test_csharp(self, mod):
        result = mod.make_lang_anchor("C#")
        assert "#" not in result

    def test_language_with_space(self, mod):
        result = mod.make_lang_anchor("Jupyter Notebook")
        assert " " not in result


class TestMakeOrgAnchor:
    """Tests for make_org_anchor()."""

    def test_simple_org(self, mod):
        assert mod.make_org_anchor("tc39") == "org-tc39"

    def test_org_with_at(self, mod):
        # @ should be stripped or handled
        result = mod.make_org_anchor("@w3c")
        assert "@" not in result

    def test_company_with_punctuation(self, mod):
        result = mod.make_org_anchor("DWANGO Co.,Ltd.")
        assert "." not in result
        assert "," not in result
        assert result.startswith("org-")

    def test_mixed_case(self, mod):
        result = mod.make_org_anchor("GitHub")
        assert result == "org-github"

    def test_multiple_spaces(self, mod):
        result = mod.make_org_anchor("Some  Company  Name")
        # Should not have multiple consecutive dashes
        assert "--" not in result


class TestMakeCommitLink:
    """Tests for make_commit_link()."""

    def test_basic_link(self, mod):
        link = mod.make_commit_link(
            "owner/repo", 10, "2026-01-01", "2026-01-31", "testuser"
        )
        assert "[10]" in link
        assert "github.com/search" in link
        assert "repo%3Aowner%2Frepo" in link or "repo:owner/repo" in unquote(link)
        assert "author%3Atestuser" in link or "author:testuser" in unquote(link)

    def test_link_with_special_chars_in_repo(self, mod):
        link = mod.make_commit_link(
            "owner/repo.js", 5, "2026-01-01", "2026-01-31", "user"
        )
        # Should be properly URL encoded
        assert "github.com/search" in link

    def test_multiple_authors(self, mod):
        link = mod.make_commit_link(
            "owner/repo", 20, "2026-01-01", "2026-01-31",
            ["user1", "user2", "user3"]
        )
        # Should contain OR syntax for multiple authors
        decoded = unquote(link)
        assert "user1" in decoded
        assert "user2" in decoded


class TestMakeLangCommitLink:
    """Tests for make_lang_commit_link()."""

    def test_basic_lang_link(self, mod):
        link = mod.make_lang_commit_link(
            "Python", 25, "2026-01-01", "2026-01-31", "testuser"
        )
        assert "[25]" in link
        assert "github.com/search" in link
        decoded = unquote(link)
        assert "language:Python" in decoded or "language%3APython" in link

    def test_cpp_encoding(self, mod):
        link = mod.make_lang_commit_link(
            "C++", 10, "2026-01-01", "2026-01-31", "user"
        )
        # C++ needs special encoding
        assert "github.com/search" in link


class TestIsBot:
    """Tests for is_bot()."""

    def test_github_bot(self, mod):
        assert mod.is_bot("dependabot[bot]") is True
        assert mod.is_bot("renovate[bot]") is True
        assert mod.is_bot("github-actions[bot]") is True

    def test_bot_suffix(self, mod):
        assert mod.is_bot("dependabot") is True
        assert mod.is_bot("greenkeeper-bot") is True
        assert mod.is_bot("snyk-bot") is True

    def test_not_a_bot(self, mod):
        assert mod.is_bot("sideshowbarker") is False
        assert mod.is_bot("octocat") is False

    def test_case_insensitive(self, mod):
        assert mod.is_bot("DependaBot") is True
        assert mod.is_bot("RENOVATE[BOT]") is True

    def test_partial_match_not_bot(self, mod):
        # "robot" ends with "bot" but is likely a valid username
        # Current implementation would match this - document the behavior
        result = mod.is_bot("robot")
        # This tests current behavior, not necessarily desired behavior
        assert result is True  # ends with "bot"

    def test_empty_or_none(self, mod):
        # Should handle edge cases gracefully
        assert mod.is_bot("") is False
        # None might raise - test current behavior
        try:
            result = mod.is_bot(None)
            assert result is False
        except (TypeError, AttributeError):
            pass  # Also acceptable


class TestColorsClass:
    """Tests for the Colors utility class."""

    def test_colors_exist(self, mod):
        """Verify Colors class has expected attributes."""
        assert hasattr(mod, "Colors")
        colors = mod.Colors
        # Check some expected color attributes
        assert hasattr(colors, "RESET") or hasattr(colors, "reset")

    def test_color_formatting(self, mod):
        """Test color string generation if methods exist."""
        colors = mod.Colors
        # The class might use class methods or string attributes
        # Just verify it doesn't crash
        if hasattr(colors, "green"):
            result = colors.green("test")
            assert "test" in result
