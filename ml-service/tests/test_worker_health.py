from services.worker import ScraperHealth, HEALTH_MIN_SAMPLES


def test_no_rate_until_min_samples():
    h = ScraperHealth()
    for _ in range(HEALTH_MIN_SAMPLES - 1):
        h.record("usps", success=True)
    assert h.success_rate("usps") is None
    h.record("usps", success=True)
    assert h.success_rate("usps") == 1.0


def test_degraded_flag_and_last_error():
    h = ScraperHealth()
    for _ in range(HEALTH_MIN_SAMPLES):
        h.record("fedex", success=False, error="selector not found")
    stats = h.get_stats()["fedex"]
    assert stats["degraded"] is True
    assert stats["success_rate"] == 0.0
    assert "selector" in stats["last_error"]


def test_recovery_clears_degraded():
    h = ScraperHealth()
    for _ in range(HEALTH_MIN_SAMPLES):
        h.record("ups", success=False, error="boom")
    for _ in range(40):
        h.record("ups", success=True)
    stats = h.get_stats()["ups"]
    assert stats["degraded"] is False
    assert stats["last_success"] is not None
