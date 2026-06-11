"""Predict future stops for an active shipment by matching its current
event sequence against mined route patterns.

Uses a simple prefix-matching scorer: for each stored pattern, compute
how many of the shipment's current events align with the pattern stops,
then return the best match's remaining stops with timing estimates.
"""
import logging
from datetime import timedelta, timezone

from database.models import Shipment, ShipmentEvent, Carrier, RoutePattern
from services.geocode import resolve as geocode_resolve
from services.knowledge import country_from_region
from services.timeutil import utcnow, to_naive_utc

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

    start_time = to_naive_utc(shipment.shipped_at or events[0].event_time)
    future = _extract_future_stops(best["pattern"], best["matched_to"], start_time)
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
    if not name:
        return None
    resolved = geocode_resolve(name)
    if resolved:
        return _normalize_canonical(resolved.city or resolved.country)
    return _normalize_canonical(name.split(",")[0])


def _normalize_canonical(value: str | None) -> str | None:
    if not value:
        return None
    normalized = value.strip().lower()
    return normalized or None


def _pattern_stop_canonical(ps, cache: dict) -> str | None:
    """Canonical location for a pattern stop.

    Mined patterns store a canonical field; LLM-researched patterns only
    carry a display name ("Shenzhen, China"), so resolve it the same way
    shipment events are resolved.
    """
    if ps.get("canonical"):
        return _normalize_canonical(ps["canonical"])
    name = ps.get("location_name")
    if not name:
        return None
    if name not in cache:
        cache[name] = _canonical(name, None, None)
    return cache[name]


def _find_best_pattern(current_stops, patterns):
    """Score patterns by subsequence-matching the shipment's stops.

    Real scan sequences are messy (repeated locations with different
    statuses, country-only entries), so instead of strict positional
    matching we walk the shipment's stops in order and advance through the
    pattern whenever its next stop appears.
    """
    best = None
    best_score = -1
    canon_cache: dict = {}

    for pattern in patterns:
        stops_raw = pattern.stops
        if not stops_raw:
            continue

        pattern_locs = [_pattern_stop_canonical(ps, canon_cache) for ps in stops_raw]

        match_count = 0
        matched_to = 0  # index into pattern stops: first unvisited stop
        cursor = 0
        for cur in current_stops:
            cur_loc = _normalize_canonical(cur["canonical"])
            for j in range(cursor, len(pattern_locs)):
                if pattern_locs[j] and pattern_locs[j] == cur_loc:
                    match_count += 1
                    cursor = j + 1
                    matched_to = j + 1
                    break

        if match_count == 0:
            continue

        # Score: fraction matched, weighted by pattern trust
        future_stops = len(stops_raw) - matched_to
        if future_stops <= 0:
            continue

        # match_score is a Numeric column - arrives as Decimal from the DB
        score = (match_count / len(stops_raw)) * float(pattern.match_score or 0.5)
        if score > best_score:
            best_score = score
            best = {
                "pattern": pattern,
                "matched_to": matched_to,
                "score": round(score, 3),
            }

    return best


def _extract_future_stops(pattern, matched_to, start_time):
    """Return the remaining stops after the matched prefix, with timing.

    Pattern stop timings are days-from-journey-start (the same anchor the
    miner uses), so each ETA is start_time + median_days. A stop the
    shipment is running late for is clamped to "soon" rather than shown in
    the past.
    """
    stops_raw = pattern.stops
    if not stops_raw or matched_to >= len(stops_raw):
        return None

    now = utcnow()
    min_eta = now + timedelta(hours=2)

    future = []
    for i in range(matched_to, len(stops_raw)):
        ps = stops_raw[i]
        median_days = ps.get("median_days_from_start", 0)
        p10_days = ps.get("p10_days", 0)
        p90_days = ps.get("p90_days", 0)

        eta = start_time + timedelta(days=median_days)
        if eta < min_eta:
            eta = min_eta

        # LLM-researched stops carry names but no coordinates; resolve them
        # so the detail map can draw the predicted path.
        lat, lng = ps.get("location_lat"), ps.get("location_lng")
        if lat is None and ps.get("location_name"):
            hit = geocode_resolve(ps["location_name"])
            if hit:
                lat, lng = hit.lat, hit.lng

        future.append({
            "stop_order": i,
            "location_name": ps.get("location_name", "Unknown"),
            "location_lat": lat,
            "location_lng": lng,
            "status": ps.get("status", "in_transit"),
            "frequency_pct": ps.get("frequency_pct", 100),
            "eta": eta.replace(tzinfo=timezone.utc).isoformat(),
            "median_days_from_start": median_days,
            "p10_days": p10_days,
            "p90_days": p90_days,
        })

    return future
