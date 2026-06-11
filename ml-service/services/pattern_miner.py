"""Mine route patterns from historical shipment event sequences.

The agent:
1. Queries all delivered shipments with their events
2. For each (carrier, origin_country, dest_country, service_type) group,
   builds a location sequence for each shipment
3. Clusters sequences by common prefixes (like a trie) to find
   the most common routes
4. Computes timing statistics per stop and stores the patterns
"""
import logging
import uuid
from collections import defaultdict

import numpy as np

from database.connection import SessionLocal
from database.models import Shipment, ShipmentEvent, Carrier, RoutePattern
from services.geocode import resolve as geocode_resolve
from services.knowledge import country_from_region
from services.timeutil import utcnow

logger = logging.getLogger("parcelstats.pattern_miner")

MIN_CLUSTER_SIZE = 3
MAX_PATTERN_LENGTH = 15


def mine_patterns() -> dict:
    """Run the full mining pipeline. Returns stats about what was mined."""
    db = SessionLocal()
    try:
        return _run(db)
    finally:
        db.close()


def _run(db) -> dict:
    stats = {"lanes": 0, "patterns_created": 0, "patterns_updated": 0, "skipped_small": 0}

    lane_groups = _collect_lane_groups(db)
    stats["lanes"] = len(lane_groups)

    for key, shipments in lane_groups.items():
        carrier_id, origin_country, dest_country, service_type = key
        sequences = []
        for shipment in shipments:
            seq = _build_sequence(db, shipment)
            if seq:
                sequences.append((shipment, seq))

        clusters = _cluster_sequences(sequences)
        for cluster in clusters:
            if len(cluster) < MIN_CLUSTER_SIZE:
                stats["skipped_small"] += 1
                continue

            pattern = _compute_pattern(cluster, carrier_id, origin_country, dest_country, service_type)
            if _upsert_pattern(db, pattern):
                stats["patterns_created"] += 1
            else:
                stats["patterns_updated"] += 1

    logger.info(
        f"Mined {stats['lanes']} lanes, "
        f"{stats['patterns_created']} new patterns, "
        f"{stats['patterns_updated']} updated, "
        f"{stats['skipped_small']} clusters too small"
    )
    return stats


def _collect_lane_groups(db):
    """Group delivered user shipments by (carrier, origin, dest, service)."""
    shipments = (
        db.query(Shipment)
        .filter(
            Shipment.source == "user",
            Shipment.delivered_at.isnot(None),
            Shipment.status.ilike("%deliver%"),
        )
        .all()
    )

    groups = defaultdict(list)
    for s in shipments:
        carrier = db.query(Carrier).filter(Carrier.id == s.carrier_id).first()
        if not carrier:
            continue
        oc = country_from_region(s.origin_name or "")
        dc = country_from_region(s.dest_name or "")
        if oc == "??" or dc == "??":
            continue
        key = (carrier.id, oc, dc, s.service_type or "standard")
        groups[key].append(s)

    return dict(groups)


def _build_sequence(db, shipment: Shipment):
    """Build a normalized stop sequence from a shipment's events."""
    events = (
        db.query(ShipmentEvent)
        .filter(ShipmentEvent.shipment_id == shipment.id)
        .order_by(ShipmentEvent.event_time.asc())
        .all()
    )
    if not events:
        return None

    start_time = shipment.shipped_at or events[0].event_time
    if not start_time:
        return None

    sequence = []
    seen = set()
    for evt in events:
        loc = _canonical_location(evt.location_name, evt.location_lat, evt.location_lng)
        if not loc:
            loc = "unknown"
        dedup_key = f"{loc}|{evt.status}"
        if dedup_key in seen:
            continue
        seen.add(dedup_key)

        days = (evt.event_time - start_time).total_seconds() / 86400
        sequence.append({
            "location_name": evt.location_name or loc,
            "location_lat": float(evt.location_lat) if evt.location_lat else None,
            "location_lng": float(evt.location_lng) if evt.location_lng else None,
            "status": evt.status,
            "canonical": loc,
            "days_from_start": round(max(0.0, days), 2),
        })

    if len(sequence) < 2:
        return None
    return sequence


def _canonical_location(name: str | None, lat, lng) -> str | None:
    """Resolve a location string to a canonical city or country name."""
    if name:
        resolved = geocode_resolve(name)
        if resolved:
            return resolved.city or resolved.country
    if lat and lng:
        resolved = geocode_resolve(f"{lat},{lng}")
        if resolved:
            return resolved.city or resolved.country
    if name:
        # Last resort: use the raw location name, stripped to first part
        return name.split(",")[0].strip().lower() or None
    return None


def _cluster_sequences(sequences):
    """Cluster sequences by common prefix using a trie approach.

    Returns a list of clusters, where each cluster is a list of
    (shipment, sequence) tuples sharing the same stop prefix.
    """
    trie = _build_trie(sequences)
    clusters = []
    _extract_clusters(trie, clusters, 0)
    return clusters


def _build_trie(sequences):
    """Build a prefix trie from sequences.

    Each node: {children: {canonical_location: {count, child_node}}, sequences: [...]}
    """
    root = {"children": {}, "sequences": []}
    for shipment, seq in sequences:
        node = root
        for stop in seq:
            key = stop["canonical"]
            if key not in node["children"]:
                node["children"][key] = {"children": {}, "sequences": []}
            node = node["children"][key]
            node["sequences"].append((shipment, seq))
    return root


def _extract_clusters(node, clusters, depth):
    """Walk the trie and extract clusters with sufficient size.

    Any node with >= MIN_CLUSTER_SIZE sequences forms a cluster.
    We take the node (which represents the common prefix up to this point)
    and all sequences that share this prefix.
    """
    if len(node["sequences"]) >= MIN_CLUSTER_SIZE:
        # Trim sequences to the common prefix depth + remaining future stops
        cluster_seqs = []
        for shipment, full_seq in node["sequences"]:
            if len(full_seq) <= depth:
                cluster_seqs.append((shipment, full_seq))
            else:
                cluster_seqs.append((shipment, full_seq))
        clusters.append(cluster_seqs)

        # Don't recurse into children of a cluster node — we want
        # the longest common prefix that still has enough samples
        return

    for child in node["children"].values():
        _extract_clusters(child, clusters, depth + 1)


def _compute_pattern(cluster, carrier_id, origin_country, dest_country, service_type):
    """Compute a single pattern from a cluster of sequences.

    The pattern is the most common path through the cluster stops.
    """
    if not cluster:
        return None

    # Build a consensus path: for each position, the most frequent canonical location
    max_len = max(len(s[1]) for s in cluster)
    path = []
    for i in range(min(max_len, MAX_PATTERN_LENGTH)):
        pos_counts = defaultdict(list)
        for shipment, seq in cluster:
            if i < len(seq):
                stop = seq[i]
                pos_counts[stop["canonical"]].append(stop)

        # Skip positions with no majority
        if not pos_counts:
            break

        best_loc = max(pos_counts, key=lambda k: len(pos_counts[k]))
        best_stops = pos_counts[best_loc]

        total = len(cluster)
        freq = round(len(best_stops) / total * 100, 1)

        days_arr = np.array([s["days_from_start"] for s in best_stops])
        lat_lngs = [(s["location_lat"], s["location_lng"]) for s in best_stops if s["location_lat"]]

        path.append({
            "stop_order": i,
            "location_name": best_stops[0]["location_name"],
            "canonical": best_loc,
            "location_lat": _median_lat_lng(lat_lngs)[0] if lat_lngs else None,
            "location_lng": _median_lat_lng(lat_lngs)[1] if lat_lngs else None,
            "status": best_stops[0]["status"],
            "frequency_pct": freq,
            "median_days_from_start": round(float(np.median(days_arr)), 2) if len(days_arr) > 0 else 0.0,
            "p10_days": round(float(np.percentile(days_arr, 10)), 2) if len(days_arr) > 0 else 0.0,
            "p90_days": round(float(np.percentile(days_arr, 90)), 2) if len(days_arr) > 0 else 0.0,
        })

    label = f'{path[0]["canonical"].title() if path[0].get("canonical") else path[0]["location_name"]} → '
    label += f'{path[-1]["canonical"].title() if path[-1].get("canonical") else path[-1]["location_name"]}'
    if len(path) > 2:
        via = path[1].get("canonical", path[1]["location_name"])
        label += f" via {via.title()}"

    score = round(len(cluster) / (len(cluster) + 10), 2)

    return {
        "carrier_id": carrier_id,
        "origin_country": origin_country,
        "dest_country": dest_country,
        "service_type": service_type,
        "label": label,
        "stops": path,
        "sample_count": len(cluster),
        "match_score": score,
    }


def _median_lat_lng(coords):
    """Return median lat and lng from a list of (lat, lng) tuples."""
    lats = [c[0] for c in coords if c[0] is not None]
    lngs = [c[1] for c in coords if c[1] is not None]
    if not lats or not lngs:
        return (None, None)
    return (float(np.median(lats)), float(np.median(lngs)))


def _upsert_pattern(db, pattern_data):
    """Insert or update a route pattern."""
    if not pattern_data:
        return False

    existing = (
        db.query(RoutePattern)
        .filter(
            RoutePattern.carrier_id == pattern_data["carrier_id"],
            RoutePattern.origin_country == pattern_data["origin_country"],
            RoutePattern.dest_country == pattern_data["dest_country"],
            RoutePattern.service_type == pattern_data["service_type"],
            RoutePattern.label == pattern_data["label"],
        )
        .first()
    )

    if existing:
        existing.stops = pattern_data["stops"]
        existing.sample_count = pattern_data["sample_count"]
        existing.match_score = pattern_data["match_score"]
        existing.updated_at = utcnow()
        db.commit()
        return False

    pattern = RoutePattern(
        id=str(uuid.uuid4()),
        carrier_id=pattern_data["carrier_id"],
        origin_country=pattern_data["origin_country"],
        dest_country=pattern_data["dest_country"],
        service_type=pattern_data["service_type"],
        label=pattern_data["label"],
        stops=pattern_data["stops"],
        sample_count=pattern_data["sample_count"],
        match_score=pattern_data["match_score"],
    )
    db.add(pattern)
    db.commit()
    return True
