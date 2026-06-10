"""Prediction accuracy: compare past predictions against actual deliveries."""
from collections import defaultdict
from datetime import datetime


def summarize_accuracy(rows: list[tuple]) -> dict:
    """Aggregate (shipment_id, carrier_slug, model_version, created_at,
    predicted_delivery, delivered_at) rows into accuracy stats.

    Only the earliest prediction per shipment is scored - that is the
    forecast made with the least information, so it reflects real-world
    predictive value rather than last-minute corrections.
    """
    earliest: dict[str, tuple] = {}
    for row in rows:
        shipment_id, _, _, created_at, _, _ = row
        current = earliest.get(shipment_id)
        if current is None or (created_at and created_at < current[3]):
            earliest[shipment_id] = row

    by_model: dict[str, list[float]] = defaultdict(list)
    by_carrier: dict[str, list[float]] = defaultdict(list)
    all_errors: list[float] = []

    for shipment_id, carrier_slug, model_version, _, predicted, delivered in earliest.values():
        if not isinstance(predicted, datetime) or not isinstance(delivered, datetime):
            continue
        error_days = (predicted - delivered).total_seconds() / 86400
        all_errors.append(error_days)
        by_model[model_version or "unknown"].append(error_days)
        by_carrier[carrier_slug or "unknown"].append(error_days)

    return {
        "overall": _bucket_stats(all_errors),
        "by_model": {k: _bucket_stats(v) for k, v in by_model.items()},
        "by_carrier": {k: _bucket_stats(v) for k, v in by_carrier.items()},
    }


def _bucket_stats(errors: list[float]) -> dict:
    if not errors:
        return {"count": 0}
    abs_errors = [abs(e) for e in errors]
    return {
        "count": len(errors),
        "mae_days": round(sum(abs_errors) / len(abs_errors), 2),
        "bias_days": round(sum(errors) / len(errors), 2),
        "within_1_day_pct": round(100 * sum(1 for e in abs_errors if e <= 1) / len(abs_errors), 1),
        "within_2_days_pct": round(100 * sum(1 for e in abs_errors if e <= 2) / len(abs_errors), 1),
    }
