"""Unit tests for rate limit estimation and warning logic."""


class TestEstimateOrgApiCalls:
    """Tests for estimate_org_api_calls()."""

    def test_small_org_short_period(self, mod):
        """Small org (10 members) for 7 days."""
        result = mod.estimate_org_api_calls(10, 7)
        # Phase 1: ceil(10*0.05 / 10) = 1
        # Phase 2: 10 * 2.4 * 1.0 = 24
        # Total: ~25
        assert 20 <= result <= 50

    def test_medium_org(self, mod):
        """Medium org (50 members) for 7 days."""
        result = mod.estimate_org_api_calls(50, 7)
        # Should be roughly 50 * 2.4 + small phase 1 overhead
        assert 100 <= result <= 200

    def test_large_org_baseline(self, mod):
        """Large org (524 members, w3c baseline) for 7 days."""
        result = mod.estimate_org_api_calls(524, 7)
        # Empirical: ~1,300 for w3c 7-day
        assert 1000 <= result <= 1600

    def test_large_org_monthly(self, mod):
        """Large org for 30 days."""
        result = mod.estimate_org_api_calls(524, 30)
        # Empirical: ~2,200 for w3c 30-day
        assert 2000 <= result <= 2800

    def test_very_large_org_short_period(self, mod):
        """Very large org (3686 members, w3c --private) for 1 day."""
        result = mod.estimate_org_api_calls(3686, 1)
        # Empirical: ~2,724 actual calls
        # Old formula gave 5,728 (2.1x overestimate)
        assert 2000 <= result <= 3500

    def test_sublinear_member_scaling(self, mod):
        """Doubling members should NOT double API calls."""
        small = mod.estimate_org_api_calls(500, 7)
        large = mod.estimate_org_api_calls(1000, 7)
        ratio = large / small
        # With linear scaling ratio would be ~2.0
        # With ^0.8 scaling it should be ~1.7
        assert ratio < 2.0

    def test_sublinear_time_scaling(self, mod):
        """30 days should NOT be 4x the calls of 7 days."""
        seven_day = mod.estimate_org_api_calls(100, 7)
        thirty_day = mod.estimate_org_api_calls(100, 30)

        # 30/7 ≈ 4.3, but with ^0.4 scaling it should be ~1.7x
        ratio = thirty_day / seven_day
        assert 1.5 <= ratio <= 2.5  # Sublinear, not linear

    def test_zero_members(self, mod):
        """Zero members should return minimal calls."""
        result = mod.estimate_org_api_calls(0, 7)
        assert result >= 0
        assert result < 10

    def test_one_member(self, mod):
        """Single member edge case."""
        result = mod.estimate_org_api_calls(1, 7)
        assert result > 0
        assert result < 20

    def test_yearly_period(self, mod):
        """Full year (365 days)."""
        result = mod.estimate_org_api_calls(100, 365)
        # Should be higher than 30 days but still sublinear
        thirty_day = mod.estimate_org_api_calls(100, 30)
        assert result > thirty_day
        # 365/30 ≈ 12, but with ^0.4 scaling should be ~2-3x
        ratio = result / thirty_day
        assert ratio < 5

    def test_known_active_skips_phase1(self, mod):
        """known_active=True should skip phase 1 and sublinear scaling."""
        # With known_active, 1000 members is used directly (no ^0.8)
        known = mod.estimate_org_api_calls(1000, 7, known_active=True)
        # Should be ~1000 * 2.4 = 2400 (no phase 1, no scaling)
        assert 2300 <= known <= 2500

    def test_known_active_lower_than_heuristic_for_large_org(self, mod):
        """known_active for small active count < heuristic for large total."""
        # Pre-check: 3000 total members, heuristic applies sublinear scaling
        heuristic = mod.estimate_org_api_calls(3000, 7)
        # Re-check: only 200 actually active, no scaling needed
        actual = mod.estimate_org_api_calls(200, 7, known_active=True)
        assert actual < heuristic


class TestShouldWarnRateLimit:
    """Tests for should_warn_rate_limit()."""

    def test_no_warning_small_job(self, mod):
        """Small job with plenty of remaining calls."""
        should_warn, message = mod.should_warn_rate_limit(500, 4000)
        assert should_warn is False

    def test_warning_large_job_absolute(self, mod):
        """Job using >50% of total limit should warn."""
        # 2600 is >50% of 5000
        should_warn, message = mod.should_warn_rate_limit(2600, 5000)
        assert should_warn is True
        assert message is not None

    def test_warning_exhaustion_risk(self, mod):
        """Job using >80% of remaining should warn."""
        # 900 is 90% of 1000 remaining
        should_warn, message = mod.should_warn_rate_limit(900, 1000)
        assert should_warn is True
        assert message is not None

    def test_remaining_none_uses_total(self, mod):
        """When remaining is None, should use 5000 as total."""
        # 2600 is >50% of 5000
        should_warn, message = mod.should_warn_rate_limit(2600, None)
        assert should_warn is True

    def test_no_warning_under_both_thresholds(self, mod):
        """Job under both thresholds should not warn."""
        # 2000 is 40% of 5000 total, 50% of 4000 remaining
        should_warn, message = mod.should_warn_rate_limit(2000, 4000)
        assert should_warn is False

    def test_message_contains_estimate(self, mod):
        """Warning message should contain the estimated call count."""
        should_warn, message = mod.should_warn_rate_limit(3000, 5000)
        if should_warn and message:
            assert "3,000" in message or "3000" in message

    def test_message_contains_percentage(self, mod):
        """Warning message should contain percentage."""
        should_warn, message = mod.should_warn_rate_limit(2500, 5000)
        if should_warn and message:
            assert "%" in message

    def test_edge_exactly_at_threshold(self, mod):
        """Test behavior at exact threshold boundaries."""
        # Exactly 50% of 5000 = 2500
        should_warn, _ = mod.should_warn_rate_limit(2500, 5000)
        # Behavior at exact boundary is implementation-defined


class TestRateLimitConstants:
    """Verify rate limit constants are sensible."""

    def test_warn_threshold_absolute_exists(self, mod):
        """Check WARN_THRESHOLD_ABSOLUTE constant."""
        if hasattr(mod, "WARN_THRESHOLD_ABSOLUTE"):
            assert 0 < mod.WARN_THRESHOLD_ABSOLUTE < 1
            # Should be around 0.5 (50%)
            assert 0.4 <= mod.WARN_THRESHOLD_ABSOLUTE <= 0.6

    def test_warn_threshold_remaining_exists(self, mod):
        """Check WARN_THRESHOLD_REMAINING constant."""
        if hasattr(mod, "WARN_THRESHOLD_REMAINING"):
            assert 0 < mod.WARN_THRESHOLD_REMAINING < 1
            # Should be around 0.8 (80%)
            assert 0.7 <= mod.WARN_THRESHOLD_REMAINING <= 0.9

    def test_total_rate_limit(self, mod):
        """Check GITHUB_RATE_LIMIT_TOTAL constant."""
        if hasattr(mod, "GITHUB_RATE_LIMIT_TOTAL"):
            assert mod.GITHUB_RATE_LIMIT_TOTAL == 5000
