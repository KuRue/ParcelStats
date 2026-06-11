from services.geocode import parse_location, resolve


def test_parse_us_city_state_zip():
    assert parse_location("JACKSONVILLE, FL 32099") == ("jacksonville", "FL", "US")


def test_parse_city_state_suffix():
    assert parse_location("Chicago IL, US") == ("chicago", "IL", "US")


def test_parse_country_only():
    assert parse_location("Germany") == (None, None, "DE")


def test_parse_strips_facility_suffix():
    city, admin1, country = parse_location("ISC NEW YORK NY(USPS)")
    assert admin1 == "NY"
    assert country == "US"


def test_resolve_major_cities():
    cases = {
        "SHENZHEN, China": ("CN", 22.5),
        "JACKSONVILLE, FL 32099": ("US", 30.3),
        "Tokyo, Japan": ("JP", 35.7),
        "Mississauga, ON": ("CA", 43.6),
    }
    for raw, (country, lat) in cases.items():
        hit = resolve(raw)
        assert hit is not None, raw
        assert hit.country == country
        assert abs(hit.lat - lat) < 0.5


def test_resolve_ambiguous_state_vs_country():
    # MO is Missouri here, not Macau
    hit = resolve("O'Fallon, MO")
    assert hit is not None
    assert hit.country == "US"

    # CA with a Canadian city resolves to Canada
    toronto = resolve("Toronto, CA")
    assert toronto is not None
    assert toronto.country == "CA"

    # CA with a Californian city stays in the US
    la = resolve("Los Angeles, CA")
    assert la is not None
    assert la.country == "US"


def test_resolve_facility_prefix():
    hit = resolve("ISC NEW YORK NY(USPS)")
    assert hit is not None
    assert abs(hit.lat - 40.7) < 0.3


def test_resolve_country_centroid_fallback():
    hit = resolve("Germany")
    assert hit is not None
    assert hit.source == "country"
    assert hit.country == "DE"


def test_resolve_unknown_returns_none():
    assert resolve("totally unknown place xyz") is None
    assert resolve("") is None
    assert resolve(None) is None
