from datetime import datetime

from services.predictor import ETAPredictor


class FakeModel:
    def __init__(self, value):
        self.value = value

    def predict(self, X):
        return [self.value]


def make_predictor():
    p = object.__new__(ETAPredictor)
    p.model_median = FakeModel(4.0)
    p.model_p10 = FakeModel(2.0)
    p.model_p90 = FakeModel(6.0)
    p.version = "test"
    p.metadata = {
        "features": [
            "carrier_slug", "origin_region", "dest_region",
            "service_type", "weight_kg", "shipped_month", "shipped_dow",
        ],
        "categories": {
            "carrier_slug": {"0": "usps", "1": "ups"},
            "origin_region": {"0": "ca", "1": "ny"},
            "dest_region": {"0": "ca", "1": "tx"},
            "service_type": {"0": "standard"},
        },
    }
    return p


def test_predicts_for_known_categories():
    result = make_predictor().predict("usps", "CA", "TX", shipped_at=datetime(2026, 6, 1))
    assert result is not None
    assert result["median_days"] == 4.0
    assert result["model_version"] == "test"


def test_returns_none_for_unknown_carrier():
    assert make_predictor().predict("zz-post", "CA", "TX") is None


def test_returns_none_when_both_regions_unknown():
    assert make_predictor().predict("usps", "Nowhere", "Elsewhere") is None


def test_reduced_confidence_for_partially_unknown_input():
    p = make_predictor()
    known = p.predict("usps", "CA", "TX", service_type="standard")
    partial = p.predict("usps", "CA", "TX", service_type="hyperspeed")
    assert partial is not None
    assert partial["confidence_pct"] <= 60.0
    assert partial["confidence_pct"] < known["confidence_pct"]
