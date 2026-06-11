from services.calibration import blend_with_baseline, BLEND_HALFWEIGHT


BASELINE = {
    "median_days": 15.0,
    "p10_days": 10.0,
    "p90_days": 20.0,
    "confidence_pct": 65.0,
}


def test_no_lane_returns_baseline():
    assert blend_with_baseline(BASELINE, None) == BASELINE


def test_blend_moves_toward_empirical():
    lane = {"median_days": 9.0, "p10_days": 7.0, "p90_days": 12.0, "sample_count": BLEND_HALFWEIGHT}
    blended = blend_with_baseline(BASELINE, lane)
    # Equal weight at the halfweight sample count
    assert blended["median_days"] == 12.0
    assert blended["p10_days"] == 8.5
    assert BASELINE["median_days"] > blended["median_days"] > lane["median_days"]


def test_many_samples_dominate():
    lane = {"median_days": 9.0, "p10_days": 7.0, "p90_days": 12.0, "sample_count": 200}
    blended = blend_with_baseline(BASELINE, lane)
    assert abs(blended["median_days"] - 9.0) < 0.5


def test_confidence_rises_with_evidence_and_caps():
    small = blend_with_baseline(BASELINE, {"median_days": 9, "p10_days": 7, "p90_days": 12, "sample_count": 2})
    large = blend_with_baseline(BASELINE, {"median_days": 9, "p10_days": 7, "p90_days": 12, "sample_count": 500})
    assert small["confidence_pct"] == 70.0
    assert large["confidence_pct"] == 90.0
    assert small["calibration_samples"] == 2
