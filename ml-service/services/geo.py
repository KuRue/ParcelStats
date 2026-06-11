from __future__ import annotations

import re

Coordinate = tuple[float, float]

COUNTRY_ALIASES = {
    "cn": "cn",
    "china": "cn",
    "hongkong": "hk",
    "hongkongchina": "hk",
    "hk": "hk",
    "us": "us",
    "usa": "us",
    "unitedstates": "us",
    "unitedstatesofamerica": "us",
}

COUNTRY_COORDS: dict[str, Coordinate] = {
    "cn": (35.8617, 104.1954),
    "hk": (22.3193, 114.1694),
    "us": (39.8283, -98.5795),
}

CITY_COORDS: dict[tuple[str, str], Coordinate] = {
    ("chicago", "us"): (41.8781, -87.6298),
    ("chicagoil", "us"): (41.8781, -87.6298),
    ("dongguan", "cn"): (23.0207, 113.7518),
    ("largo", "us"): (27.9095, -82.7873),
    ("shenzhen", "cn"): (22.5431, 114.0579),
}


def normalize_place(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"[^a-z0-9]", "", value.lower())


def normalize_country(value: str | None) -> str:
    key = normalize_place(value)
    return COUNTRY_ALIASES.get(key, key)


def same_country(left: str | None, right: str | None) -> bool:
    return normalize_country(left) == normalize_country(right)


def resolve_location(city: str | None, country: str | None) -> Coordinate | None:
    # Gazetteer-backed lookup first (33k+ cities, offline)
    from services.geocode import resolve

    raw = ", ".join(p for p in [city, country] if p)
    hit = resolve(raw, country_hint=country)
    if hit:
        return (hit.lat, hit.lng)

    country_key = normalize_country(country)
    city_key = normalize_place(city)

    if city_key and country_key:
        coords = CITY_COORDS.get((city_key, country_key))
        if coords:
            return coords

    if country_key:
        return COUNTRY_COORDS.get(country_key)

    return None
