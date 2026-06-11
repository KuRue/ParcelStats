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
            "carrier_slug", "origin_country", "dest_country",
            "service_type", "weight_kg", "distance_km", "estimated_hops",
            "shipped_month", "shipped_dow", "seasonal_multiplier", "is_domestic",
        ],
        "categories": {
            "carrier_slug": {"0": "usps", "1": "ups"},
            "origin_country": {"0": "US"},
            "dest_country": {"0": "US"},
            "service_type": {"0": "standard"},
        },
    }
    return p


def test_knowledge_fallback_without_loaded_model():
    p = object.__new__(ETAPredictor)
    p.model_median = None
    p.metadata = None

    result = p.predict("usps", "US", "US")
    assert result is not None
    assert result["model_version"] == "knowledge-v1"
    assert result["prediction_source"] == "knowledge"


def test_predicts_for_known_categories():
    result = make_predictor().predict("usps", "US", "US", shipped_at=datetime(2026, 7, 1))
    assert result is not None
    assert result["median_days"] == 4.0
    assert result["model_version"] == "test"


def test_knowledge_fallback_for_unknown_carrier():
    result = make_predictor().predict("zz-post", "US", "US")
    assert result is not None
    assert result["model_version"] == "knowledge-v1"


def test_knowledge_fallback_when_both_regions_unknown():
    result = make_predictor().predict("usps", "Nowhere", "Elsewhere")
    assert result is not None
    assert result["model_version"] == "knowledge-v1"
    # Unknown lanes should carry lower confidence than known ones
    known = make_predictor().predict("usps", "US", "US")
    assert result["confidence_pct"] < known["confidence_pct"]


def test_reduced_confidence_for_partially_unknown_input():
    p = make_predictor()
    known = p.predict("usps", "US", "US", service_type="standard")
    partial = p.predict("usps", "US", "US", service_type="hyperspeed")
    assert partial is not None
    assert partial["confidence_pct"] <= 60.0
    assert partial["confidence_pct"] < known["confidence_pct"]
