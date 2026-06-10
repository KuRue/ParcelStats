from datetime import datetime

from services.accuracy import summarize_accuracy


def row(shipment, carrier, model, created, predicted, delivered):
    return (shipment, carrier, model, created, predicted, delivered)


def test_empty_rows():
    result = summarize_accuracy([])
    assert result["overall"] == {"count": 0}


def test_uses_earliest_prediction_per_shipment():
    delivered = datetime(2026, 6, 10)
    rows = [
        # later prediction is perfect, earliest is 2 days off - earliest must win
        row("s1", "usps", "v1", datetime(2026, 6, 5), delivered, delivered),
        row("s1", "usps", "v1", datetime(2026, 6, 1), datetime(2026, 6, 12), delivered),
    ]
    result = summarize_accuracy(rows)
    assert result["overall"]["count"] == 1
    assert result["overall"]["mae_days"] == 2.0
    assert result["overall"]["bias_days"] == 2.0


def test_groups_by_model_and_carrier():
    delivered = datetime(2026, 6, 10)
    rows = [
        row("s1", "usps", "v1", datetime(2026, 6, 1), datetime(2026, 6, 10, 12), delivered),
        row("s2", "ups", "baseline_eta", datetime(2026, 6, 1), datetime(2026, 6, 13), delivered),
    ]
    result = summarize_accuracy(rows)
    assert result["overall"]["count"] == 2
    assert result["by_model"]["v1"]["within_1_day_pct"] == 100.0
    assert result["by_model"]["baseline_eta"]["mae_days"] == 3.0
    assert result["by_carrier"]["ups"]["count"] == 1


def test_skips_rows_without_dates():
    rows = [row("s1", "usps", "v1", datetime(2026, 6, 1), None, datetime(2026, 6, 10))]
    assert summarize_accuracy(rows)["overall"] == {"count": 0}
