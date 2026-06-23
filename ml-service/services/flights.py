"""Cargo flight tracker using the free OpenSky Network API.

Polls live aircraft positions and filters for cargo carriers (FedEx, UPS,
DHL, Cargolux, Atlas Air, Kalitta, etc.). Results are cached in Redis so
multiple shipments on the same route share one API call.

OpenSky anonymous access: ~400 requests/day, 100s rate-limit (more than
enough for a 60s polling cycle).
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, asdict
from typing import Optional

import httpx
import redis as redis_lib

from services.config import settings

logger = logging.getLogger("parcelstats.flights")

OPENSKY_URL = "https://opensky-network.org/api/states/all"
CACHE_KEY = "flights:cargo:latest"
CACHE_TTL = 120  # 2 minutes

CARGO_PREFIXES = (
    "FDX",   # FedEx
    "UPS",   # UPS
    "GTI",   # Atlas Air
    "GEC",   # Atlas Air (alt)
    "CKS",   # Kalitta Air
    "CLX",   # Cargolux
    "PAC",   # Polar Air Cargo
    "NCA",   # Nippon Cargo Airlines
    "KZE",   # Kam Air Cargo
    "ABW",   # AirBridgeCargo
    "CLX",   # Cargolux
    "BCS",   # European Air Transport (DHL)
    "SBI",   # S7 Cargo
    "FOO",   # Cargojet
    "WFK",   # Western Global
    "JOS",   # Joint-Stock
    "GTI",   # Atlas
    "DHX",   # DHL
    "TAY",   # Swift Air (cargo)
    "POE",   # Polar Air
    "GTO",   # Cargo
    "AJT",   # ATRAN Cargo
    "MUP",   # MyCargo
    "RUS",   # Russian cargo
    "CHIEF", # Chief Air
    "CAM",   # Atlas Air Cargo (CAM)
)


@dataclass
class FlightPosition:
    icao24: str
    callsign: str
    latitude: float
    longitude: float
    altitude: Optional[float]
    velocity: Optional[float]
    heading: Optional[float]
    vertical_rate: Optional[float]
    on_ground: bool
    origin_country: str
    last_contact: int


def _redis() -> redis_lib.Redis | None:
    try:
        return redis_lib.from_url(settings.redis_url, decode_responses=True)
    except Exception:
        return None


async def fetch_cargo_flights() -> list[FlightPosition]:
    """Fetch live cargo flight positions from OpenSky Network."""
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(OPENSKY_URL)
            if resp.status_code != 200:
                logger.warning("OpenSky returned HTTP %d", resp.status_code)
                return []

            data = resp.json()
            states = data.get("states") or []
            if not states:
                return []

            cargo_flights: list[FlightPosition] = []
            for s in states:
                if len(s) < 11:
                    continue
                callsign = (s[1] or "").strip()
                if not callsign:
                    continue
                prefix = callsign[:3].upper()
                prefix4 = callsign[:5].upper()
                if prefix not in CARGO_PREFIXES and prefix4 not in CARGO_PREFIXES:
                    continue
                lat, lng = s[6], s[5]
                if lat is None or lng is None:
                    continue

                cargo_flights.append(FlightPosition(
                    icao24=s[0],
                    callsign=callsign,
                    latitude=float(lat),
                    longitude=float(lng),
                    altitude=s[7] if s[7] is not None else (s[13] if len(s) > 13 and s[13] is not None else None),
                    velocity=s[9],
                    heading=s[10],
                    vertical_rate=s[11] if len(s) > 11 else None,
                    on_ground=bool(s[8]) if s[8] is not None else False,
                    origin_country=s[2] or "",
                    last_contact=int(s[4]) if s[4] else int(time.time()),
                ))

            return cargo_flights

    except Exception as e:
        logger.warning("OpenSky fetch failed: %s", e)
        return []


async def update_flight_cache():
    """Fetch and cache cargo flights in Redis. Called by the scheduler."""
    flights = await fetch_cargo_flights()
    if not flights:
        return 0

    r = _redis()
    if not r:
        return len(flights)

    try:
        payload = json.dumps([asdict(f) for f in flights])
        r.setex(CACHE_KEY, CACHE_TTL, payload)
        logger.info("Cached %d cargo flights", len(flights))
        return len(flights)
    except Exception as e:
        logger.warning("Failed to cache flights: %s", e)
        return len(flights)


def get_cached_flights() -> list[FlightPosition]:
    """Return cached cargo flights, or empty list if cache miss."""
    r = _redis()
    if not r:
        return []
    try:
        raw = r.get(CACHE_KEY)
        if not raw:
            return []
        data = json.loads(raw)
        return [FlightPosition(**f) for f in data]
    except Exception:
        return []


def flights_for_route(
    origin_lat: float,
    origin_lng: float,
    dest_lat: float,
    dest_lng: float,
    corridor_width_km: float = 600,
) -> list[dict]:
    """Return cargo flights near the great-circle path between two points.

    Uses a simple perpendicular-distance check to filter flights within
    a corridor along the route.
    """
    from services.knowledge import haversine_km

    flights = get_cached_flights()
    if not flights:
        return []

    route_length = haversine_km(origin_lat, origin_lng, dest_lat, dest_lng)
    if route_length < 50:
        return []

    results = []
    for f in flights:
        d_origin = haversine_km(f.latitude, f.longitude, origin_lat, origin_lng)
        d_dest = haversine_km(f.latitude, f.longitude, dest_lat, dest_lng)

        cross_track = perpendicular_distance_km(
            f.latitude, f.longitude,
            origin_lat, origin_lng,
            dest_lat, dest_lng,
        )

        along_track = (d_origin + d_dest) / 2
        max_along = route_length + corridor_width_km

        if cross_track <= corridor_width_km and along_track <= max_along:
            results.append({
                "icao24": f.icao24,
                "callsign": f.callsign,
                "latitude": f.latitude,
                "longitude": f.longitude,
                "altitude": f.altitude,
                "velocity": f.velocity,
                "heading": f.heading,
                "on_ground": f.on_ground,
                "origin_country": f.origin_country,
                "distance_to_origin_km": round(d_origin),
                "distance_to_dest_km": round(d_dest),
            })

    return results


def perpendicular_distance_km(
    point_lat: float, point_lng: float,
    line_lat1: float, line_lng1: float,
    line_lat2: float, line_lng2: float,
) -> float:
    """Approximate perpendicular distance from a point to a great-circle path.

    Uses the cross-track distance formula.
    """
    from services.knowledge import haversine_km
    import math

    R = 6371.0

    d13 = haversine_km(line_lat1, line_lng1, point_lat, point_lng) / R
    if d13 == 0:
        return 0.0

    bearing_start = math.radians(bearing(
        line_lat1, line_lng1, line_lat2, line_lng2
    ))

    bearing_point = math.radians(bearing(
        line_lat1, line_lng1, point_lat, point_lng
    ))

    cross_track = math.asin(
        math.sin(d13) * math.sin(bearing_point - bearing_start)
    ) * R

    return abs(cross_track)


def bearing(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Initial bearing in degrees between two points."""
    import math
    lat1, lat2 = math.radians(lat1), math.radians(lat2)
    dlng = math.radians(lng2 - lng1)
    y = math.sin(dlng) * math.cos(lat2)
    x = (math.cos(lat1) * math.sin(lat2)
         - math.sin(lat1) * math.cos(lat2) * math.cos(dlng))
    return (math.degrees(math.atan2(y, x)) + 360) % 360
