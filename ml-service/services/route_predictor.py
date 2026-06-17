"""Predict future stops for an active shipment by matching its current
event sequence against mined route patterns.

Uses a simple prefix-matching scorer: for each stored pattern, compute
how many of the shipment's current events align with the pattern stops,
then return the best match's remaining stops with timing estimates.
"""
import logging
from datetime import timedelta, timezone
from decimal import Decimal

from database.models import Shipment, ShipmentEvent, Carrier, RoutePattern
from services.geocode import resolve as geocode_resolve
from services.knowledge import country_from_region, haversine_km
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

    best = _find_best_pattern(
        current_stops,
        patterns,
        dest_lat=_to_float(shipment.dest_lat),
        dest_lng=_to_float(shipment.dest_lng),
    )

    start_time = to_naive_utc(shipment.shipped_at or events[0].event_time)

    if best:
        future = _extract_future_stops(
            best["pattern"],
            best["matched_to"],
            start_time,
            current_stops=current_stops,
            dest_name=shipment.dest_name,
            dest_lat=_to_float(shipment.dest_lat),
            dest_lng=_to_float(shipment.dest_lng),
        )
        if future:
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

    return _synthetic_route(
        db,
        shipment,
        events,
        carrier,
        origin_country,
        dest_country,
    )


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
            "location_lat": _to_float(evt.location_lat),
            "location_lng": _to_float(evt.location_lng),
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


def _to_float(value) -> float | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


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


def _find_best_pattern(current_stops, patterns, dest_lat=None, dest_lng=None):
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

        # Score: fraction matched, weighted by pattern trust and destination fit.
        future_stops = len(stops_raw) - matched_to
        if future_stops <= 0:
            continue

        # match_score is a Numeric column - arrives as Decimal from the DB
        base_score = (match_count / len(stops_raw)) * float(pattern.match_score or 0.5)
        score = base_score * _destination_fit_score(
            stops_raw,
            matched_to,
            dest_lat,
            dest_lng,
        )
        if score > best_score:
            best_score = score
            best = {
                "pattern": pattern,
                "matched_to": matched_to,
                "score": round(score, 3),
            }

    return best


def _destination_fit_score(stops_raw, matched_to, dest_lat=None, dest_lng=None) -> float:
    """Prefer stored routes whose remaining stops get close to this destination."""
    if dest_lat is None or dest_lng is None:
        return 1.0

    distances = []
    for ps in stops_raw[matched_to:]:
        lat = _to_float(ps.get("location_lat"))
        lng = _to_float(ps.get("location_lng"))
        if lat is not None and lng is not None:
            distances.append(haversine_km(lat, lng, dest_lat, dest_lng))

    if not distances:
        return 1.0

    best_distance = min(distances)
    final_distance = distances[-1]

    best_proximity = 1 / (1 + best_distance / 750)
    final_proximity = 1 / (1 + final_distance / 750)
    return 0.4 + (0.35 * best_proximity) + (0.25 * final_proximity)


def _extract_future_stops(
    pattern,
    matched_to,
    start_time,
    current_stops=None,
    dest_name=None,
    dest_lat=None,
    dest_lng=None,
):
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

    return _refine_future_stops(
        future,
        current_stops=current_stops,
        dest_name=dest_name,
        dest_lat=dest_lat,
        dest_lng=dest_lng,
    )


def _refine_future_stops(
    future,
    current_stops=None,
    dest_name=None,
    dest_lat=None,
    dest_lng=None,
):
    """Remove noisy repeated predictions and anchor the route to the destination."""
    if not future:
        return future

    latest_current = None
    if current_stops:
        latest_current = _normalize_canonical(current_stops[-1].get("canonical"))

    dest_canon = _canonical(dest_name, dest_lat, dest_lng) if dest_name else None
    if dest_name and (dest_lat is None or dest_lng is None):
        dest_hit = geocode_resolve(dest_name)
        if dest_hit:
            dest_lat = dest_hit.lat
            dest_lng = dest_hit.lng

    refined = []
    seen = set()
    for stop in future:
        canon = _canonical(stop.get("location_name"), stop.get("location_lat"), stop.get("location_lng"))
        status = stop.get("status", "")
        dedup_key = f"{canon}|{status}"
        if canon and canon == latest_current and canon != dest_canon:
            continue
        if dedup_key in seen and canon != dest_canon:
            continue
        if canon:
            seen.add(dedup_key)
        if dest_canon and canon != dest_canon and status == "delivered":
            stop = {**stop, "status": "arrived_at_facility"}
        refined.append(stop)

    if dest_name and dest_canon:
        last_canon = (
            _canonical(
                refined[-1].get("location_name"),
                refined[-1].get("location_lat"),
                refined[-1].get("location_lng"),
            )
            if refined
            else None
        )
        if last_canon != dest_canon:
            source = future[-1]
            refined.append({
                **source,
                "stop_order": source.get("stop_order", len(future)),
                "location_name": dest_name,
                "location_lat": dest_lat,
                "location_lng": dest_lng,
                "status": "delivered",
                "frequency_pct": 100,
            })
        elif refined[-1].get("status") != "delivered":
            refined[-1] = {
                **refined[-1],
                "location_name": dest_name,
                "location_lat": dest_lat,
                "location_lng": dest_lng,
                "status": "delivered",
                "frequency_pct": 100,
            }

    return refined


def _latest_current_distance_to_destination(current_stops, dest_lat, dest_lng) -> float | None:
    if not current_stops or dest_lat is None or dest_lng is None:
        return None

    latest = current_stops[-1]
    lat = _to_float(latest.get("location_lat"))
    lng = _to_float(latest.get("location_lng"))
    if lat is None or lng is None:
        return None
    return haversine_km(lat, lng, dest_lat, dest_lng)


def _is_low_progress_intermediate(stop, dest_canon, latest_distance, dest_lat, dest_lng) -> bool:
    """Deprecated: previously hid domestic stops close to destination.

    Now always returns False — we want to show ALL predicted stops so the
    user sees the full chain (depart → hub → out for delivery → delivered).
    """
    return False


def _synthetic_route(
    db, shipment: Shipment, events, carrier: Carrier,
    origin_country: str, dest_country: str,
) -> dict | None:
    """Generate a predicted stop chain when no mined pattern matches.

    Uses the latest event location and destination to build:
    depart current → arrive regional hub → out for delivery → delivered
    """
    from services.knowledge import HUBS, haversine_km

    dest_lat = _to_float(shipment.dest_lat)
    dest_lng = _to_float(shipment.dest_lng)
    dest_name = shipment.dest_name or "Destination"

    if dest_lat is None or dest_lng is None:
        hit = geocode_resolve(dest_name)
        if hit:
            dest_lat, dest_lng = hit.lat, hit.lng
    if dest_lat is None:
        return None

    latest_event = events[-1] if events else None
    cur_lat = _to_float(latest_event.location_lat if latest_event else None)
    cur_lng = _to_float(latest_event.location_lng if latest_event else None)
    cur_name = latest_event.location_name if latest_event else shipment.origin_name

    remaining_km = 0.0
    if cur_lat and cur_lng:
        remaining_km = haversine_km(cur_lat, cur_lng, dest_lat, dest_lng)

    now = utcnow()

    regional_hub_name = None
    regional_hub_lat = dest_lat
    regional_hub_lng = dest_lng
    nearest_dist = float("inf")
    for hub in HUBS:
        if hub.country != dest_country:
            continue
        d = haversine_km(hub.lat, hub.lng, dest_lat, dest_lng)
        if d < nearest_dist and d < 500:
            nearest_dist = d
            regional_hub_name = hub.name
            regional_hub_lat = hub.lat
            regional_hub_lng = hub.lng

    if regional_hub_name is None:
        regional_hub_name = dest_name.split(",")[0].strip() if dest_name else "Regional Hub"

    base_hours = max(6, remaining_km / 80.0)

    future_stops = []

    if latest_event and cur_lat and cur_lng:
        future_stops.append({
            "stop_order": 0,
            "location_name": cur_name or "Current Location",
            "location_lat": cur_lat,
            "location_lng": cur_lng,
            "status": "departed_facility",
            "frequency_pct": 90,
            "eta": (now + timedelta(hours=2)).replace(tzinfo=timezone.utc).isoformat(),
            "median_days_from_start": 0,
            "p10_days": 0,
            "p90_days": 1,
        })

    future_stops.append({
        "stop_order": 1,
        "location_name": regional_hub_name,
        "location_lat": regional_hub_lat,
        "location_lng": regional_hub_lng,
        "status": "arrived_at_facility",
        "frequency_pct": 85,
        "eta": (now + timedelta(hours=base_hours)).replace(tzinfo=timezone.utc).isoformat(),
        "median_days_from_start": round(base_hours / 24, 1),
        "p10_days": round(base_hours / 24 * 0.7, 1),
        "p90_days": round(base_hours / 24 * 1.5, 1),
    })

    future_stops.append({
        "stop_order": 2,
        "location_name": dest_name,
        "location_lat": dest_lat,
        "location_lng": dest_lng,
        "status": "out_for_delivery",
        "frequency_pct": 90,
        "eta": (now + timedelta(hours=base_hours + 12)).replace(tzinfo=timezone.utc).isoformat(),
        "median_days_from_start": round((base_hours + 12) / 24, 1),
        "p10_days": round((base_hours + 6) / 24, 1),
        "p90_days": round((base_hours + 24) / 24, 1),
    })

    future_stops.append({
        "stop_order": 3,
        "location_name": dest_name,
        "location_lat": dest_lat,
        "location_lng": dest_lng,
        "status": "delivered",
        "frequency_pct": 100,
        "eta": (now + timedelta(hours=base_hours + 18)).replace(tzinfo=timezone.utc).isoformat(),
        "median_days_from_start": round((base_hours + 18) / 24, 1),
        "p10_days": round((base_hours + 12) / 24, 1),
        "p90_days": round((base_hours + 48) / 24, 1),
    })

    return {
        "carrier_slug": carrier.slug,
        "origin_country": origin_country,
        "dest_country": dest_country,
        "label": "Synthetic forecast",
        "matched_stops": len(events),
        "total_pattern_stops": len(future_stops),
        "total_events": len(events),
        "score": 0.3,
        "sample_count": 0,
        "future_stops": future_stops,
    }
