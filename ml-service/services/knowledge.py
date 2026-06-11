import math
from dataclasses import dataclass


@dataclass
class Hub:
    code: str
    name: str
    lat: float
    lng: float
    country: str


@dataclass
class LaneBaseline:
    origin_country: str
    dest_country: str
    carrier_slugs: list[str]
    standard_days: float
    express_days: float
    economy_days: float


HUBS: list[Hub] = [
    Hub("CNSHA", "Shanghai", 31.23, 121.47, "CN"),
    Hub("CNGZG", "Guangzhou", 23.13, 113.26, "CN"),
    Hub("CNSZX", "Shenzhen", 22.54, 114.06, "CN"),
    Hub("CNPEK", "Beijing", 39.90, 116.40, "CN"),
    Hub("CNYNH", "Yiwu", 29.31, 120.07, "CN"),
    Hub("HKHKG", "Hong Kong", 22.32, 114.17, "HK"),
    Hub("USLAX", "Los Angeles", 33.94, -118.41, "US"),
    Hub("USORD", "Chicago O'Hare", 41.97, -87.91, "US"),
    Hub("USJFK", "New York JFK", 40.64, -73.78, "US"),
    Hub("USSFO", "San Francisco", 37.62, -122.38, "US"),
    Hub("USDFW", "Dallas", 32.90, -97.04, "US"),
    Hub("USMIA", "Miami", 25.80, -80.29, "US"),
    Hub("GBLHR", "London Heathrow", 51.47, -0.46, "GB"),
    Hub("GBEMA", "East Midlands", 52.83, -1.33, "GB"),
    Hub("DECGN", "Cologne", 50.87, 7.13, "DE"),
    Hub("DEFRA", "Frankfurt", 50.03, 8.57, "DE"),
    Hub("FRCDG", "Paris CDG", 49.01, 2.55, "FR"),
    Hub("NLAMS", "Amsterdam", 52.31, 4.77, "NL"),
    Hub("JPTYO", "Tokyo", 35.76, 140.39, "JP"),
    Hub("JPKIX", "Osaka", 34.43, 135.24, "JP"),
    Hub("KRICN", "Incheon", 37.46, 126.44, "KR"),
    Hub("AUSYD", "Sydney", -33.95, 151.18, "AU"),
    Hub("AUMEL", "Melbourne", -37.67, 144.84, "AU"),
    Hub("CAYUL", "Montreal", 45.47, -73.74, "CA"),
    Hub("CAYVR", "Vancouver", 49.19, -123.18, "CA"),
    Hub("SGSIN", "Singapore", 1.36, 103.99, "SG"),
    Hub("INDEL", "Delhi", 28.57, 77.10, "IN"),
    Hub("INBOM", "Mumbai", 19.09, 72.87, "IN"),
    Hub("THBKK", "Bangkok", 13.69, 100.75, "TH"),
    Hub("MYKUL", "Kuala Lumpur", 2.75, 101.71, "MY"),
    Hub("ESMAD", "Madrid", 40.49, -3.57, "ES"),
    Hub("ITMXP", "Milan", 45.63, 8.73, "IT"),
    Hub("SEARN", "Stockholm", 59.65, 17.93, "SE"),
    Hub("CHZRH", "Zurich", 47.46, 8.55, "CH"),
    Hub("IEABB", "Dublin", 53.43, -6.27, "IE"),
    Hub("NZAKL", "Auckland", -37.01, 174.79, "NZ"),
    Hub("BRGRU", "Sao Paulo", -23.43, -46.47, "BR"),
    Hub("PLWAW", "Warsaw", 52.17, 20.97, "PL"),
    Hub("ILTLV", "Tel Aviv", 32.01, 34.89, "IL"),
]


LANE_BASELINES: list[LaneBaseline] = [
    LaneBaseline("CN", "US", ["speedpak", "china-post", "yanwen"], 15.0, 7.0, 25.0),
    LaneBaseline("CN", "GB", ["speedpak", "china-post", "yanwen"], 12.0, 6.0, 22.0),
    LaneBaseline("CN", "DE", ["speedpak", "china-post", "yanwen"], 13.0, 6.0, 23.0),
    LaneBaseline("CN", "FR", ["speedpak", "china-post", "yanwen"], 13.0, 6.0, 23.0),
    LaneBaseline("CN", "AU", ["speedpak", "china-post", "yanwen"], 10.0, 5.0, 18.0),
    LaneBaseline("CN", "CA", ["speedpak", "china-post", "yanwen"], 14.0, 7.0, 24.0),
    LaneBaseline("CN", "JP", ["speedpak", "china-post", "yanwen"], 5.0, 3.0, 10.0),
    LaneBaseline("CN", "KR", ["speedpak", "china-post", "yanwen"], 5.0, 3.0, 10.0),
    LaneBaseline("CN", "SG", ["speedpak", "china-post", "yanwen"], 6.0, 3.0, 12.0),
    LaneBaseline("CN", "IN", ["speedpak", "china-post", "yanwen"], 8.0, 5.0, 16.0),
    LaneBaseline("CN", "TH", ["speedpak", "china-post", "yanwen"], 7.0, 4.0, 14.0),
    LaneBaseline("CN", "MY", ["speedpak", "china-post", "yanwen"], 7.0, 4.0, 14.0),
    LaneBaseline("CN", "NZ", ["speedpak", "china-post", "yanwen"], 12.0, 6.0, 20.0),
    LaneBaseline("CN", "BR", ["speedpak", "china-post", "yanwen"], 20.0, 10.0, 35.0),
    LaneBaseline("CN", "ES", ["speedpak", "china-post", "yanwen"], 14.0, 7.0, 24.0),
    LaneBaseline("CN", "IT", ["speedpak", "china-post", "yanwen"], 14.0, 7.0, 24.0),
    LaneBaseline("CN", "SE", ["speedpak", "china-post", "yanwen"], 14.0, 7.0, 24.0),
    LaneBaseline("CN", "CH", ["speedpak", "china-post", "yanwen"], 13.0, 6.0, 22.0),
    LaneBaseline("CN", "IE", ["speedpak", "china-post", "yanwen"], 13.0, 6.0, 22.0),
    LaneBaseline("CN", "PL", ["speedpak", "china-post", "yanwen"], 14.0, 7.0, 24.0),
    LaneBaseline("CN", "IL", ["speedpak", "china-post", "yanwen"], 10.0, 5.0, 18.0),
    LaneBaseline("CN", "HK", ["speedpak", "china-post", "yanwen"], 3.0, 1.5, 6.0),
    LaneBaseline("HK", "US", ["speedpak", "china-post", "yanwen"], 14.0, 6.0, 24.0),
    LaneBaseline("HK", "GB", ["speedpak", "china-post", "yanwen"], 11.0, 5.0, 20.0),
    LaneBaseline("HK", "DE", ["speedpak", "china-post", "yanwen"], 12.0, 6.0, 22.0),
    LaneBaseline("HK", "AU", ["speedpak", "china-post", "yanwen"], 9.0, 4.0, 16.0),
    LaneBaseline("TW", "US", ["speedpak", "china-post", "yanwen"], 13.0, 6.0, 22.0),
    LaneBaseline("TW", "GB", ["speedpak", "china-post", "yanwen"], 11.0, 5.0, 20.0),
    LaneBaseline("US", "US", ["usps", "ups", "fedex"], 4.0, 2.0, 7.0),
    LaneBaseline("GB", "GB", ["royal-mail"], 2.0, 1.0, 4.0),
    LaneBaseline("DE", "DE", ["deutsche-post", "dhl-parcel-de", "hermes", "gls"], 2.0, 1.0, 4.0),
    LaneBaseline("FR", "FR", ["la-poste"], 2.0, 1.0, 4.0),
    LaneBaseline("JP", "JP", ["japan-post"], 2.0, 1.0, 3.0),
    LaneBaseline("AU", "AU", ["australia-post"], 3.0, 1.5, 6.0),
    LaneBaseline("CA", "CA", ["canada-post"], 3.0, 1.5, 6.0),
    LaneBaseline("US", "GB", ["usps", "ups", "fedex"], 6.0, 3.0, 10.0),
    LaneBaseline("US", "DE", ["usps", "ups", "fedex"], 7.0, 3.0, 11.0),
    LaneBaseline("US", "JP", ["usps", "ups", "fedex"], 5.0, 2.0, 8.0),
    LaneBaseline("US", "AU", ["usps", "ups", "fedex"], 7.0, 3.0, 12.0),
    LaneBaseline("US", "CA", ["usps", "ups", "fedex"], 4.0, 2.0, 7.0),
    LaneBaseline("GB", "DE", ["royal-mail"], 4.0, 2.0, 7.0),
    LaneBaseline("GB", "FR", ["royal-mail"], 3.0, 2.0, 6.0),
    LaneBaseline("GB", "US", ["royal-mail"], 7.0, 3.0, 12.0),
    LaneBaseline("GB", "AU", ["royal-mail"], 9.0, 5.0, 15.0),
    LaneBaseline("DE", "US", ["deutsche-post", "dhl-parcel-de"], 8.0, 4.0, 13.0),
    LaneBaseline("AU", "US", ["australia-post"], 8.0, 4.0, 13.0),
    LaneBaseline("CA", "US", ["canada-post"], 5.0, 2.0, 8.0),
    LaneBaseline("IN", "US", ["india-post"], 12.0, 6.0, 20.0),
    LaneBaseline("IN", "GB", ["india-post"], 8.0, 4.0, 14.0),
    LaneBaseline("KR", "US", ["korea-post"], 8.0, 4.0, 14.0),
    LaneBaseline("JP", "US", ["japan-post"], 7.0, 3.0, 12.0),
    LaneBaseline("NZ", "US", ["nz-post"], 9.0, 5.0, 15.0),
    LaneBaseline("SG", "US", ["singapore-post"], 10.0, 5.0, 18.0),
    LaneBaseline("TH", "US", ["thai-post"], 12.0, 6.0, 20.0),
    LaneBaseline("MY", "US", ["pos-malaysia"], 11.0, 5.0, 18.0),
    LaneBaseline("ES", "US", ["correos"], 9.0, 4.0, 15.0),
    LaneBaseline("IT", "US", ["poste-italiane"], 9.0, 4.0, 15.0),
    LaneBaseline("SE", "US", ["postnord"], 8.0, 4.0, 13.0),
    LaneBaseline("CH", "US", ["swiss-post"], 7.0, 3.0, 12.0),
    LaneBaseline("IE", "US", ["an-post"], 8.0, 4.0, 13.0),
    LaneBaseline("PL", "US", ["polish-post"], 10.0, 5.0, 16.0),
    LaneBaseline("IL", "US", ["israel-post"], 10.0, 5.0, 16.0),
    LaneBaseline("BR", "US", ["brazil-correios"], 15.0, 7.0, 25.0),
]


SEASONAL_MULTIPLIERS: dict[int, float] = {
    1: 1.05,
    2: 0.95,
    3: 0.95,
    4: 0.95,
    5: 0.95,
    6: 0.95,
    7: 1.00,
    8: 1.00,
    9: 1.00,
    10: 1.05,
    11: 1.25,
    12: 1.30,
}


COUNTRY_CODE_MAP: dict[str, str] = {
    "united states": "US", "usa": "US", "us": "US",
    "china": "CN", "cn": "CN",
    "hong kong": "HK", "hk": "HK",
    "taiwan": "TW", "tw": "TW",
    "united kingdom": "GB", "uk": "GB", "gb": "GB", "england": "GB", "scotland": "GB", "wales": "GB",
    "germany": "DE", "de": "DE", "deutschland": "DE",
    "france": "FR", "fr": "FR",
    "japan": "JP", "jp": "JP",
    "south korea": "KR", "korea": "KR", "kr": "KR",
    "australia": "AU", "au": "AU",
    "canada": "CA", "ca": "CA",
    "singapore": "SG", "sg": "SG",
    "india": "IN", "in": "IN",
    "thailand": "TH", "th": "TH",
    "malaysia": "MY", "my": "MY",
    "new zealand": "NZ", "nz": "NZ",
    "spain": "ES", "es": "ES",
    "italy": "IT", "it": "IT",
    "sweden": "SE", "se": "SE",
    "switzerland": "CH", "ch": "CH",
    "ireland": "IE", "ie": "IE",
    "poland": "PL", "pl": "PL",
    "israel": "IL", "il": "IL",
    "brazil": "BR", "br": "BR",
    "netherlands": "NL", "nl": "NL",
    "belgium": "BE", "be": "BE",
    "austria": "AT", "at": "AT",
    "portugal": "PT", "pt": "PT",
    "denmark": "DK", "dk": "DK",
    "norway": "NO", "no": "NO",
    "finland": "FI", "fi": "FI",
    "mexico": "MX", "mx": "MX",
    "russia": "RU", "ru": "RU",
    "turkey": "TR", "tr": "TR",
    "south africa": "ZA", "za": "ZA",
    "uae": "AE", "united arab emirates": "AE",
    "saudi arabia": "SA", "sa": "SA",
    "argentina": "AR", "ar": "AR",
    "chile": "CL", "cl": "CL",
    "colombia": "CO", "co": "CO",
    "peru": "PE", "pe": "PE",
    "philippines": "PH", "ph": "PH",
    "vietnam": "VN", "vn": "VN",
    "indonesia": "ID", "id": "ID",
    "pakistan": "PK", "pk": "PK",
    "bangladesh": "BD", "bd": "BD",
    "nigeria": "NG", "ng": "NG",
    "egypt": "EG", "eg": "EG",
    "czech republic": "CZ", "czechia": "CZ", "cz": "CZ",
    "romania": "RO", "ro": "RO",
    "greece": "GR", "gr": "GR",
    "hungary": "HU", "hu": "HU",
    "croatia": "HR", "hr": "HR",
}


def country_from_region(region: str) -> str:
    if not region:
        return "??"
    key = region.strip().lower()
    if key in COUNTRY_CODE_MAP:
        return COUNTRY_CODE_MAP[key]
    code = key.upper()
    if len(code) == 2:
        return code
    for part in reversed(key.split(",")):
        part = part.strip()
        if part in COUNTRY_CODE_MAP:
            return COUNTRY_CODE_MAP[part]
        if len(part) == 2:
            return part.upper()
    return "??"


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
         * math.sin(dlng / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def get_nearest_hub(lat: float | None, lng: float | None, country: str | None = None) -> Hub | None:
    if lat is not None and lng is not None:
        candidates = HUBS
        if country:
            candidates = [h for h in HUBS if h.country == country] or HUBS
        best = min(candidates, key=lambda h: haversine_km(lat, lng, h.lat, h.lng))
        if haversine_km(lat, lng, best.lat, best.lng) < 500:
            return best
    if country:
        matches = [h for h in HUBS if h.country == country]
        if matches:
            return matches[0]
    return None


def estimate_hops(origin_country: str, dest_country: str, carrier_slug: str) -> int:
    if origin_country == dest_country:
        domestic_hops = {
            "usps": 2, "ups": 1, "fedex": 1,
            "royal-mail": 1, "canada-post": 2, "australia-post": 2,
            "deutsche-post": 1, "japan-post": 1, "china-post": 2,
            "hermes": 1, "gls": 1, "dhl-parcel-de": 1,
        }
        return domestic_hops.get(carrier_slug, 2)
    intl_hops = {
        "speedpak": 3, "yanwen": 3, "china-post": 4,
        "dhl-express": 2, "ups": 2, "fedex": 2,
    }
    base = intl_hops.get(carrier_slug, 3)
    if origin_country in ("CN", "HK", "TW") and dest_country in ("US", "CA", "GB", "DE", "FR", "AU"):
        return base
    return base + 1


def get_lane_baseline(
    origin_country: str, dest_country: str, carrier_slug: str, service_type: str = "standard"
) -> dict | None:
    matches = []
    for lane in LANE_BASELINES:
        if lane.origin_country == origin_country and lane.dest_country == dest_country:
            if carrier_slug in lane.carrier_slugs:
                matches.append(lane)
    if not matches:
        for lane in LANE_BASELINES:
            if lane.origin_country == origin_country and lane.dest_country == dest_country:
                matches.append(lane)
    if not matches:
        return None

    lane = matches[0]
    service_key = (service_type or "standard").lower()
    if "express" in service_key or "priority" in service_key or "expedited" in service_key:
        days = lane.express_days
    elif "economy" in service_key or "standard" in service_key:
        days = lane.economy_days
    elif "ground" in service_key:
        days = lane.standard_days
    else:
        days = lane.standard_days

    spread = days * 0.3
    return {
        "median_days": days,
        "p10_days": max(1.0, days - spread),
        "p90_days": days + spread,
        "lane_found": True,
    }


def get_seasonal_multiplier(month: int) -> float:
    return SEASONAL_MULTIPLIERS.get(month, 1.0)


def predict_eta_knowledge(origin_country: str, dest_country: str,
                          carrier_slug: str, service_type: str) -> dict | None:
    lane_result = get_lane_baseline(origin_country, dest_country, carrier_slug, service_type)
    if lane_result:
        return {
            "median_days": lane_result["median_days"],
            "p10_days": lane_result["p10_days"],
            "p90_days": lane_result["p90_days"],
            "confidence_pct": 65.0,
        }

    hops = estimate_hops(origin_country, dest_country, carrier_slug)
    base_days = max(3.0, hops * 2.5)
    spread = base_days * 0.4
    return {
        "median_days": base_days,
        "p10_days": max(1.0, base_days - spread),
        "p90_days": base_days + spread,
        "confidence_pct": 40.0,
    }
