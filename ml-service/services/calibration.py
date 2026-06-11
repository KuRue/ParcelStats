"""Calibrate predictions against actual delivery outcomes.

The trainer writes empirical per-lane stats to carrier_routes after each
training run, and the worker updates them on every delivery (below). This
module reads them back and blends them into knowledge-baseline predictions,
weighted by sample count - so forecasts converge on observed reality as
deliveries accumulate.
"""
import logging
import uuid

import numpy as np

from database.models import Shipment, CarrierRoute, Carrier
from services.knowledge import country_from_region
from services.timeutil import utcnow

logger = logging.getLogger("parcelstats.calibration")

# Sample count at which empirical data and the baseline are weighted equally
BLEND_HALFWEIGHT = 8
MIN_SAMPLES = 2


def get_lane_stats(db, carrier_slug: str, origin_country: str,
                   dest_country: str, service_type: str | None = None) -> dict | None:
    """Aggregate observed transit stats for a carrier lane (country level)."""
    carrier = db.query(Carrier).filter(Carrier.slug == carrier_slug).first()
    if not carrier:
        return None

    routes = (
        db.query(CarrierRoute)
        .filter(CarrierRoute.carrier_id == carrier.id, CarrierRoute.sample_count > 0)
        .all()
    )
    matches = [
        r for r in routes
        if country_from_region(r.origin_region) == origin_country
        and country_from_region(r.dest_region) == dest_country
    ]
    if service_type:
        service_matches = [r for r in matches if r.service_type == service_type]
        if service_matches:
            matches = service_matches
    if not matches:
        return None

    total = sum(r.sample_count for r in matches)
    if total < MIN_SAMPLES:
        return None

    def weighted(attr: str) -> float:
        return sum(float(getattr(r, attr)) * r.sample_count for r in matches) / total

    return {
        "median_days": weighted("median_days"),
        "p10_days": weighted("p10_days"),
        "p90_days": weighted("p90_days"),
        "sample_count": total,
    }


def blend_with_baseline(baseline: dict, lane: dict | None) -> dict:
    """Blend a knowledge baseline with empirical lane stats.

    Weight grows with sample count: n / (n + BLEND_HALFWEIGHT). Confidence
    rises with evidence, capped at 90%.
    """
    if not lane:
        return baseline

    n = lane["sample_count"]
    w = n / (n + BLEND_HALFWEIGHT)

    blended = dict(baseline)
    for key in ("median_days", "p10_days", "p90_days"):
        blended[key] = round((1 - w) * baseline[key] + w * lane[key], 2)
    blended["confidence_pct"] = round(
        min(90.0, baseline.get("confidence_pct", 50.0) + min(25.0, n * 2.5)), 1
    )
    blended["calibration_samples"] = n
    return blended


def lane_key_regions(shipment: Shipment) -> tuple[str, str]:
    origin = (shipment.origin_name or "unknown").split(",")[-1].strip().lower()
    dest = (shipment.dest_name or "unknown").split(",")[-1].strip().lower()
    return origin, dest


def update_lane_stats_for_shipment(db, shipment: Shipment) -> bool:
    """Refresh the carrier_routes row for a just-delivered shipment's lane."""
    if not shipment.shipped_at or not shipment.delivered_at:
        return False

    origin, dest = lane_key_regions(shipment)
    service = shipment.service_type or "standard"

    # All delivered user shipments on the same lane
    siblings = (
        db.query(Shipment)
        .filter(
            Shipment.carrier_id == shipment.carrier_id,
            Shipment.shipped_at.isnot(None),
            Shipment.delivered_at.isnot(None),
            Shipment.source == "user",
        )
        .all()
    )
    durations = []
    for s in siblings:
        s_origin, s_dest = lane_key_regions(s)
        if s_origin != origin or s_dest != dest:
            continue
        if (s.service_type or "standard") != service:
            continue
        days = (s.delivered_at - s.shipped_at).total_seconds() / 86400
        if days > 0:
            durations.append(days)

    if not durations:
        return False

    arr = np.array(durations)
    existing = (
        db.query(CarrierRoute)
        .filter(
            CarrierRoute.carrier_id == shipment.carrier_id,
            CarrierRoute.origin_region == origin,
            CarrierRoute.dest_region == dest,
            CarrierRoute.service_type == service,
        )
        .first()
    )
    if existing:
        existing.avg_days = float(np.mean(arr))
        existing.median_days = float(np.median(arr))
        existing.p10_days = float(np.percentile(arr, 10))
        existing.p90_days = float(np.percentile(arr, 90))
        existing.sample_count = len(arr)
        existing.updated_at = utcnow()
    else:
        db.add(CarrierRoute(
            id=str(uuid.uuid4()),
            carrier_id=shipment.carrier_id,
            origin_region=origin,
            dest_region=dest,
            service_type=service,
            avg_days=float(np.mean(arr)),
            median_days=float(np.median(arr)),
            p10_days=float(np.percentile(arr, 10)),
            p90_days=float(np.percentile(arr, 90)),
            sample_count=len(arr),
        ))

    db.commit()
    logger.info(
        f"Lane calibration updated: {origin} -> {dest} ({service}), "
        f"{len(arr)} samples, median {float(np.median(arr)):.1f}d"
    )
    return True
