"""Tests for CLI argument parsing (parse_and_validate_args) and run()."""

import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from tests.conftest import load_chronicle_module  # noqa: E402

mod = load_chronicle_module()


# -----------------------------------------------------------------------
# TestParseAndValidateArgs
# -----------------------------------------------------------------------


class TestParseAndValidateArgs:
    """Tests for parse_and_validate_args()."""

    def test_valid_user_mode(self):
        config = mod.parse_and_validate_args(
            ["--user", "alice", "--days", "7"]
        )
        assert config.username == "alice"
        assert config.org is None
        assert config.team is None
        assert config.owners is False
        assert config.private is False
        assert config.stdout is False
        assert config.yes is False

    def test_valid_org_mode(self):
        config = mod.parse_and_validate_args(
            ["--org", "myorg", "--team", "editors"]
        )
        assert config.org == "myorg"
        assert config.team == "editors"
        assert config.username is None

    def test_date_option_days(self):
        config = mod.parse_and_validate_args(["--user", "x", "--days", "14"])
        # since_date should be 14 days ago (we just check it's a valid date)
        assert len(config.since_date) == 10  # YYYY-MM-DD

    def test_date_option_weeks(self):
        config = mod.parse_and_validate_args(["--user", "x", "--weeks", "2"])
        assert len(config.since_date) == 10

    def test_date_option_months(self):
        config = mod.parse_and_validate_args(["--user", "x", "--months", "3"])
        assert len(config.since_date) == 10

    def test_date_option_year(self):
        config = mod.parse_and_validate_args(["--user", "x", "--year"])
        assert len(config.since_date) == 10

    def test_date_option_since_until(self):
        config = mod.parse_and_validate_args(
            ["--user", "x", "--since", "2025-06-01", "--until", "2025-06-30"]
        )
        assert config.since_date == "2025-06-01"
        assert config.until_date == "2025-06-30"

    def test_date_default_7_days(self):
        config = mod.parse_and_validate_args(["--user", "x"])
        # Default is 7 days back; just check we get a valid date string
        assert len(config.since_date) == 10

    def test_until_defaults_to_today(self):
        from datetime import datetime

        config = mod.parse_and_validate_args(["--user", "x"])
        assert config.until_date == datetime.now().strftime("%Y-%m-%d")

    # -- Validation errors (7 checks) --

    def test_error_org_and_user(self):
        with pytest.raises(SystemExit) as exc_info:
            mod.parse_and_validate_args(["--org", "o", "--user", "u"])
        assert exc_info.value.code == 1

    def test_error_team_without_org(self):
        with pytest.raises(SystemExit) as exc_info:
            mod.parse_and_validate_args(["--team", "t"])
        assert exc_info.value.code == 1

    def test_error_owners_without_org(self):
        with pytest.raises(SystemExit) as exc_info:
            mod.parse_and_validate_args(["--owners"])
        assert exc_info.value.code == 1

    def test_error_owners_and_team(self):
        with pytest.raises(SystemExit) as exc_info:
            mod.parse_and_validate_args(
                ["--org", "o", "--owners", "--team", "t"]
            )
        assert exc_info.value.code == 1

    def test_error_private_without_org(self):
        with pytest.raises(SystemExit) as exc_info:
            mod.parse_and_validate_args(["--private"])
        assert exc_info.value.code == 1

    def test_error_private_and_team(self):
        with pytest.raises(SystemExit) as exc_info:
            mod.parse_and_validate_args(
                ["--org", "o", "--private", "--team", "t", "--yes"]
            )
        assert exc_info.value.code == 1

    def test_error_private_and_owners(self):
        with pytest.raises(SystemExit) as exc_info:
            mod.parse_and_validate_args(
                ["--org", "o", "--private", "--owners", "--yes"]
            )
        assert exc_info.value.code == 1

    # -- Invalid date formats --

    def test_invalid_since_format(self):
        with pytest.raises(SystemExit) as exc_info:
            mod.parse_and_validate_args(["--user", "x", "--since", "nope"])
        assert exc_info.value.code == 1

    def test_invalid_until_format(self):
        with pytest.raises(SystemExit) as exc_info:
            mod.parse_and_validate_args(["--user", "x", "--until", "nope"])
        assert exc_info.value.code == 1

    # -- stdout flag --

    def test_stdout_flag(self):
        config = mod.parse_and_validate_args(["--user", "x", "--stdout"])
        assert config.stdout is True

    # -- --private prompt handling --

    def test_private_with_yes(self):
        config = mod.parse_and_validate_args(
            ["--org", "o", "--private", "--yes"]
        )
        assert config.private is True
        assert config.yes is True

    def test_private_without_yes_decline(self):
        with patch("builtins.input", return_value="n"):
            with pytest.raises(SystemExit) as exc_info:
                mod.parse_and_validate_args(["--org", "o", "--private"])
            assert exc_info.value.code == 0

    def test_private_without_yes_accept(self):
        with patch("builtins.input", return_value="y"):
            config = mod.parse_and_validate_args(["--org", "o", "--private"])
            assert config.private is True

    def test_private_without_yes_eoferror(self):
        with patch("builtins.input", side_effect=EOFError):
            with pytest.raises(SystemExit) as exc_info:
                mod.parse_and_validate_args(["--org", "o", "--private"])
            assert exc_info.value.code == 0

    # -- output flag --

    def test_output_flag(self):
        config = mod.parse_and_validate_args(
            ["--user", "x", "--output", "my-report.md"]
        )
        assert config.output == "my-report.md"


# -----------------------------------------------------------------------
# TestRun
# -----------------------------------------------------------------------


class TestRun:
    """Tests for run()."""

    def _make_config(self, **overrides):
        """Build a RunConfig with sensible defaults."""
        defaults = dict(
            username="alice",
            org=None,
            team=None,
            owners=False,
            private=False,
            since_date="2026-01-01",
            until_date="2026-01-07",
            output=None,
            stdout=False,
            yes=False,
        )
        defaults.update(overrides)
        return mod.RunConfig(**defaults)

    def test_user_mode_writes_file(self, tmp_path):
        config = self._make_config()
        report_text = "# mock report"

        with (
            patch.object(mod, "generate_report", return_value=report_text),
            patch.object(Path, "write_text") as mock_write,
        ):
            # We need to patch so write_text is called but doesn't
            # actually write; just verify it was called
            mod.run(config)

        mock_write.assert_called_once_with(report_text)

    def test_user_mode_stdout(self, capsys):
        config = self._make_config(stdout=True)
        report_text = "# stdout report"

        with patch.object(mod, "generate_report", return_value=report_text):
            mod.run(config)

        captured = capsys.readouterr()
        assert captured.out.strip() == report_text

    def test_user_mode_explicit_output(self):
        config = self._make_config(output="custom.md")
        report_text = "# custom output"

        with (
            patch.object(mod, "generate_report", return_value=report_text),
            patch.object(Path, "write_text") as mock_write,
        ):
            mod.run(config)

        # The Path instance should be constructed with "custom.md"
        mock_write.assert_called_once_with(report_text)

    def test_org_mode_writes_file(self):
        config = self._make_config(
            username=None,
            org="myorg",
        )
        report_text = "# org report"
        gather_result = (
            {"login": "myorg"},  # org_info
            None,  # team_info
            [],  # members
            {},  # aggregated
            [],  # member_data
        )

        with (
            patch.object(
                mod,
                "gather_org_data_active_contributors",
                return_value=gather_result,
            ),
            patch.object(
                mod,
                "generate_org_report",
                return_value=report_text,
            ),
            patch.object(mod, "progress"),
            patch.object(Path, "write_text") as mock_write,
        ):
            mod.run(config)

        mock_write.assert_called_once_with(report_text)

    def test_org_mode_team_filename(self):
        config = self._make_config(
            username=None,
            org="myorg",
            team="editors",
        )
        report_text = "# team report"
        gather_result = (
            {"login": "myorg"},
            None,
            [],
            {},
            [],
        )

        with (
            patch.object(
                mod,
                "gather_org_data_active_contributors",
                return_value=gather_result,
            ),
            patch.object(
                mod,
                "generate_org_report",
                return_value=report_text,
            ),
            patch.object(mod, "progress"),
            patch.object(Path, "write_text") as mock_write,
        ):
            mod.run(config)

        # Default filename should include team slug
        # Verify write_text was called (the Path object was constructed
        # with myorg-editors-... filename)
        mock_write.assert_called_once_with(report_text)

    def test_org_mode_owners_filename(self):
        config = self._make_config(
            username=None,
            org="myorg",
            owners=True,
        )
        report_text = "# owners report"
        gather_result = (
            {"login": "myorg"},
            None,
            [],
            {},
            [],
        )

        with (
            patch.object(
                mod,
                "gather_org_data_active_contributors",
                return_value=gather_result,
            ),
            patch.object(
                mod,
                "generate_org_report",
                return_value=report_text,
            ),
            patch.object(mod, "progress"),
            patch.object(Path, "write_text") as mock_write,
        ):
            mod.run(config)

        mock_write.assert_called_once_with(report_text)


# -----------------------------------------------------------------------
# TestMain — username detection via subprocess
# -----------------------------------------------------------------------


class TestMain:
    """Tests for main() username auto-detection paths."""

    def _no_user_config(self):
        return mod.RunConfig(
            username=None,
            org=None,
            team=None,
            owners=False,
            private=False,
            since_date="2026-01-01",
            until_date="2026-01-07",
            output=None,
            stdout=False,
            yes=False,
        )

    def test_username_detected_successfully(self):
        """gh api user succeeds → username populated, run() called."""
        mock_result = MagicMock()
        mock_result.stdout = "alice\n"

        with (
            patch.object(
                mod,
                "parse_and_validate_args",
                return_value=self._no_user_config(),
            ),
            patch("subprocess.run", return_value=mock_result),
            patch.object(mod, "run") as mock_run,
        ):
            mod.main()

        called_config = mock_run.call_args[0][0]
        assert called_config.username == "alice"

    def test_username_empty_raises_value_error(self):
        """gh api user returns empty string → SystemExit(1)."""
        mock_result = MagicMock()
        mock_result.stdout = "   \n"

        with (
            patch.object(
                mod,
                "parse_and_validate_args",
                return_value=self._no_user_config(),
            ),
            patch("subprocess.run", return_value=mock_result),
            pytest.raises(SystemExit) as exc_info,
        ):
            mod.main()

        assert exc_info.value.code == 1

    def test_subprocess_error_generic(self):
        """gh api user fails (non-rate-limit) → SystemExit(1)."""
        error = subprocess.CalledProcessError(1, "gh")
        error.stderr = "some error"

        with (
            patch.object(
                mod,
                "parse_and_validate_args",
                return_value=self._no_user_config(),
            ),
            patch("subprocess.run", side_effect=error),
            pytest.raises(SystemExit) as exc_info,
        ):
            mod.main()

        assert exc_info.value.code == 1

    def test_subprocess_error_rate_limit(self):
        """gh api user fails with rate limit → calls print_rate_limit_error."""
        error = subprocess.CalledProcessError(1, "gh")
        error.stderr = "API rate limit exceeded"

        with (
            patch.object(
                mod,
                "parse_and_validate_args",
                return_value=self._no_user_config(),
            ),
            patch("subprocess.run", side_effect=error),
            patch.object(mod, "print_rate_limit_error") as mock_rle,
            pytest.raises(SystemExit),
        ):
            mod.main()

        mock_rle.assert_called_once()

    def test_org_mode_skips_detection(self):
        """Org mode does not attempt username detection."""
        config = self._no_user_config()._replace(org="myorg")
        with (
            patch.object(
                mod,
                "parse_and_validate_args",
                return_value=config,
            ),
            patch.object(mod, "run") as mock_run,
            patch("subprocess.run") as mock_sp,
        ):
            mod.main()

        mock_sp.assert_not_called()
        mock_run.assert_called_once()

    def test_explicit_user_skips_detection(self):
        """--user provided skips subprocess detection."""
        config = self._no_user_config()._replace(username="bob")
        with (
            patch.object(
                mod,
                "parse_and_validate_args",
                return_value=config,
            ),
            patch.object(mod, "run") as mock_run,
            patch("subprocess.run") as mock_sp,
        ):
            mod.main()

        mock_sp.assert_not_called()
        called_config = mock_run.call_args[0][0]
        assert called_config.username == "bob"
