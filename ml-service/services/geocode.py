"""Offline geocoder backed by the bundled GeoNames gazetteer.

Resolves carrier scan-location strings ("JACKSONVILLE, FL 32099",
"SHENZHEN, China", "Chicago IL, US") to coordinates without any network
calls, so every tracked parcel can appear on the dashboard globe.
"""
from __future__ import annotations

import csv
import os
import re
import threading
from dataclasses import dataclass

from services.knowledge import COUNTRY_CODE_MAP, HUBS

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")

US_STATES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI", "ID",
    "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS",
    "MO", "MT", "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "OH", "OK",
    "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV",
    "WI", "WY", "DC", "PR", "GU", "VI", "AS", "MP",
}

CA_PROVINCES = {"AB", "BC", "MB", "NB", "NL", "NS", "NT", "NU", "ON", "PE", "QC", "SK", "YT"}


@dataclass
class GeocodeResult:
    lat: float
    lng: float
    city: str | None
    country: str
    source: str  # "city" | "hub" | "country"


class _Gazetteer:
    def __init__(self):
        # (name, country) -> (lat, lng, admin1, population); best-by-population
        self.by_city_country: dict[tuple[str, str], tuple[float, float, str, int]] = {}
        # (name, country, admin1) -> (lat, lng)
        self.by_city_admin: dict[tuple[str, str, str], tuple[float, float]] = {}
        # name -> (lat, lng, country, population); best-by-population worldwide
        self.by_city: dict[str, tuple[float, float, str, int]] = {}
        # country code -> (lat, lng)
        self.country_centroids: dict[str, tuple[float, float]] = {}
        # lowercase country name -> code
        self.country_names: dict[str, str] = {}
        self._load()

    def _load(self):
        cities_path = os.path.join(DATA_DIR, "cities.tsv")
        countries_path = os.path.join(DATA_DIR, "countries.tsv")
        if not os.path.exists(cities_path):
            return

        with open(cities_path, encoding="utf-8") as f:
            for row in csv.reader(f, delimiter="\t"):
                if len(row) < 6:
                    continue
                name, country, admin1 = row[0], row[1], row[2]
                lat, lng, pop = float(row[3]), float(row[4]), int(row[5])

                key = (name, country)
                if key not in self.by_city_country or pop > self.by_city_country[key][3]:
                    self.by_city_country[key] = (lat, lng, admin1, pop)
                if admin1:
                    self.by_city_admin.setdefault((name, country, admin1), (lat, lng))
                if name not in self.by_city or pop > self.by_city[name][3]:
                    self.by_city[name] = (lat, lng, country, pop)

        if os.path.exists(countries_path):
            with open(countries_path, encoding="utf-8") as f:
                for row in csv.reader(f, delimiter="\t"):
                    if len(row) < 4:
                        continue
                    code, name = row[0], row[1]
                    self.country_centroids[code] = (float(row[2]), float(row[3]))
                    self.country_names[name.lower()] = code


_gazetteer: _Gazetteer | None = None
_lock = threading.Lock()


def _gaz() -> _Gazetteer:
    global _gazetteer
    if _gazetteer is None:
        with _lock:
            if _gazetteer is None:
                _gazetteer = _Gazetteer()
    return _gazetteer


def _clean(value: str) -> str:
    value = re.sub(r"\([^)]*\)", " ", value)  # drop "(USPS)" style suffixes
    value = re.sub(r"\b\d{4,}(?:-\d{4})?\b", " ", value)  # drop ZIP/postal codes
    return re.sub(r"\s+", " ", value).strip()


def _country_code(token: str) -> str | None:
    g = _gaz()
    key = token.strip().lower()
    if not key:
        return None
    if key in COUNTRY_CODE_MAP:
        return COUNTRY_CODE_MAP[key]
    if key in g.country_names:
        return g.country_names[key]
    upper = token.strip().upper()
    if len(upper) == 2 and upper in g.country_centroids:
        return upper
    return None


def parse_location(raw: str) -> tuple[str | None, str | None, str | None]:
    """Split a location string into (city, admin1, country_code)."""
    cleaned = _clean(raw)
    if not cleaned:
        return None, None, None

    parts = [p.strip() for p in cleaned.split(",") if p.strip()]
    if not parts:
        return None, None, None

    country: str | None = None
    admin1: str | None = None

    # "Germany", "China" - a bare country name with no city
    if len(parts) == 1 and " " not in parts[0]:
        bare = _country_code(parts[0])
        if bare:
            return None, None, bare

    if len(parts) > 1:
        last_upper = parts[-1].upper()
        # Two-letter tokens that are US states (MO, CA, DE, IN...) collide
        # with ISO country codes; parcel data is state-heavy, so prefer the
        # state reading here and let resolve() retry as a country on miss.
        if not (last_upper in US_STATES and last_upper != "US"):
            country = _country_code(parts[-1])
            if country:
                parts = parts[:-1]

    # State / province tokens, either their own part or appended to the city
    remaining = []
    for part in parts:
        upper = part.upper()
        if upper in US_STATES:
            admin1, country = upper, country or "US"
            continue
        if upper in CA_PROVINCES:
            admin1, country = upper, country or "CA"
            continue
        remaining.append(part)
    parts = remaining

    city = parts[0] if parts else None
    if city:
        words = city.split()
        if len(words) > 1:
            tail = words[-1].upper()
            if tail in US_STATES:
                admin1, country, city = tail, country or "US", " ".join(words[:-1])
            elif tail in CA_PROVINCES:
                admin1, country, city = tail, country or "CA", " ".join(words[:-1])

    return (city.lower() if city else None), admin1, country


def resolve(raw: str | None, country_hint: str | None = None) -> GeocodeResult | None:
    """Resolve a free-text location to coordinates, or None."""
    if not raw:
        return None
    g = _gaz()
    if not g.by_city:  # gazetteer data missing
        return None

    city, admin1, country = parse_location(raw)
    if country is None and country_hint:
        country = _country_code(country_hint)

    result = _match_city(g, city, admin1, country)

    # Ambiguous state token (e.g. "Toronto, CA"): retry it as a country code
    if result is None and admin1 and admin1 in g.country_centroids:
        result = _match_city(g, city, None, admin1)
        if result:
            return result

    if result:
        return result

    if country:
        centroid = g.country_centroids.get(country)
        if centroid:
            return GeocodeResult(centroid[0], centroid[1], None, country, "country")

    return None


CITY_ALIASES = {
    "new york": "new york city",
    "nyc": "new york city",
    "st louis": "saint louis",
    "st. louis": "saint louis",
    "st paul": "saint paul",
    "st petersburg": "saint petersburg",
}


def _match_city(
    g: _Gazetteer, city: str | None, admin1: str | None, country: str | None
) -> GeocodeResult | None:
    if not city:
        return None

    # Facility prefixes ("ISC NEW YORK" -> "NEW YORK"): retry the lookup
    # dropping leading words until something matches.
    words = city.split()
    candidates: list[str] = []
    for i in range(len(words)):
        cand = " ".join(words[i:])
        candidates.append(CITY_ALIASES.get(cand, cand))

    for candidate in candidates:
        if country and admin1:
            hit = g.by_city_admin.get((candidate, country, admin1))
            if hit:
                return GeocodeResult(hit[0], hit[1], candidate, country, "city")
        if country:
            hit2 = g.by_city_country.get((candidate, country))
            if hit2:
                return GeocodeResult(hit2[0], hit2[1], candidate, country, "city")

        for hub in HUBS:
            if hub.name.lower() == candidate and (not country or hub.country == country):
                return GeocodeResult(hub.lat, hub.lng, candidate, hub.country, "hub")

        if not country:
            hit3 = g.by_city.get(candidate)
            if hit3:
                return GeocodeResult(hit3[0], hit3[1], candidate, hit3[2], "city")

    return None
