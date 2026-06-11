"""Predict future stops for an active shipment by matching its current
event sequence against mined route patterns.

Uses a simple prefix-matching scorer: for each stored pattern, compute
how many of the shipment's current events align with the pattern stops,
then return the best match's remaining stops with timing estimates.
"""
import logging
from datetime import datetime, timedelta

from database.models import Shipment, ShipmentEvent, Carrier, RoutePattern
from services.geocode import resolve as geocode_resolve
from services.knowledge import country_from_region

logger = logging.getLogger("parcelstats.route_predictor")


def predict_route(db, shipment: Shipment) -> dict | None:
    """Predict future stops for a shipment by matching against known patterns."""
    carrier = db.query(Carrier).filter(Carrier.id == shipment.carrier_id).first()
    if not carrier:
        return None

    events = (
        db.query(ShipmentEvent)
        .filter(ShipmentEvent.shipment_id == shipment.id)
        .order_by(ShipmentEvent.event_time.asc())
        .all()
    )
    if not events:
        return None

    origin_country = country_from_region(shipment.origin_name or "")
    dest_country = country_from_region(shipment.dest_name or "")
    if origin_country == "??" or dest_country == "??":
        return None

    patterns = (
        db.query(RoutePattern)
        .filter(
            RoutePattern.carrier_id == carrier.id,
            RoutePattern.origin_country == origin_country,
            RoutePattern.dest_country == dest_country,
        )
        .all()
    )
    if not patterns:
        return None

    current_stops = _build_current_stops(events)
    if not current_stops:
        return None

    best = _find_best_pattern(current_stops, patterns)
    if not best:
        return None

    future = _extract_future_stops(best["pattern"], best["matched_to"], current_stops, events)
    if not future:
        return None

    return {
        "carrier_slug": carrier.slug,
        "origin_country": origin_country,
        "dest_country": dest_country,
        "label": best["pattern"].label,
        "matched_stops": best["matched_to"],
        "total_pattern_stops": len(best["pattern"].stops),
        "total_events": len(events),
        "score": best["score"],
        "sample_count": best["pattern"].sample_count,
        "future_stops": future,
    }


def _build_current_stops(events):
    """Build a list of canonical location names from events, preserving order."""
    stops = []
    seen = set()
    for evt in events:
        loc = _canonical(evt.location_name, evt.location_lat, evt.location_lng)
        if not loc:
            continue
        dedup_key = f"{loc}|{evt.status}"
        if dedup_key in seen:
            continue
        seen.add(dedup_key)
        stops.append({
            "canonical": loc,
            "status": evt.status,
            "event_time": evt.event_time,
        })
    return stops


def _canonical(name, lat, lng) -> str | None:
    if name:
        resolved = geocode_resolve(name)
        if resolved:
            return resolved.city or resolved.country
    if lat and lng:
        resolved = geocode_resolve(f"{lat},{lng}")
        if resolved:
            return resolved.city or resolved.country
    if name:
        return name.split(",")[0].strip().lower() or None
    return None


def _find_best_pattern(current_stops, patterns):
    """Score each pattern by how well current stops match its prefix."""
    best = None
    best_score = -1

    for pattern in patterns:
        stops_raw = pattern.stops
        if not stops_raw:
            continue

        match_count = 0
        matched_to = 0

        for i, ps in enumerate(stops_raw):
            pattern_loc = ps.get("canonical") or ps.get("location_name", "").lower()
            if i < len(current_stops):
                cur_loc = current_stops[i]["canonical"]
                if pattern_loc == cur_loc:
                    match_count += 1
                    matched_to = i + 1
                else:
                    break

        if match_count == 0:
            continue

        # Score: fraction matched, weighted by pattern frequency
        future_stops = len(stops_raw) - matched_to
        if future_stops <= 0:
            continue

        score = (match_count / len(stops_raw)) * (pattern.match_score or 0.5)
        if score > best_score:
            best_score = score
            best = {
                "pattern": pattern,
                "matched_to": matched_to,
                "score": round(score, 3),
            }

    return best


def _extract_future_stops(pattern, matched_to, current_stops, events):
    """Return the remaining stops after the matched prefix, with timing."""
    stops_raw = pattern.stops
    if not stops_raw or matched_to >= len(stops_raw):
        return None

    # Use the last event time as the reference point for timing
    last_event_time = max(e.event_time for e in events) if events else datetime.utcnow()

    future = []
    for i in range(matched_to, len(stops_raw)):
        ps = stops_raw[i]
        median_days = ps.get("median_days_from_start", 0)
        p10_days = ps.get("p10_days", 0)
        p90_days = ps.get("p90_days", 0)

        # Compute time remaining from last event to this stop
        days_remaining = max(0, median_days - (matched_to * 0))  # rough estimate
        eta = last_event_time + timedelta(days=days_remaining)

        future.append({
            "stop_order": i,
            "location_name": ps.get("location_name", "Unknown"),
            "location_lat": ps.get("location_lat"),
            "location_lng": ps.get("location_lng"),
            "status": ps.get("status", "in_transit"),
            "frequency_pct": ps.get("frequency_pct", 100),
            "eta": eta.isoformat(),
            "median_days_from_start": median_days,
            "p10_days": p10_days,
            "p90_days": p90_days,
        })

    return future
