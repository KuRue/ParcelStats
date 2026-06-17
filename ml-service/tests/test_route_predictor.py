from datetime import datetime

from services.route_predictor import _find_best_pattern, _extract_future_stops


class FakePattern:
    def __init__(self, stops, match_score=0.8, label="test", sample_count=10):
        self.stops = stops
        self.match_score = match_score
        self.label = label
        self.sample_count = sample_count


def stop(canonical, order, median_days, status="in_transit", lat=None, lng=None):
    return {
        "canonical": canonical,
        "location_name": canonical.title(),
        "location_lat": lat,
        "location_lng": lng,
        "status": status,
        "stop_order": order,
        "median_days_from_start": median_days,
        "p10_days": median_days * 0.7,
        "p90_days": median_days * 1.4,
        "frequency_pct": 90.0,
    }


COORDS = {
    "shenzhen": (22.55, 114.07),
    "hong kong": (22.32, 114.17),
    "chicago": (41.85, -87.65),
    "new york": (40.71, -74.0),
    "atlanta": (33.75, -84.39),
    "largo": (27.9098, -82.7884),
}


PATTERN_CN_US = FakePattern([
    stop("shenzhen", 0, 0.2, lat=22.55, lng=114.07),
    stop("hong kong", 1, 1.5, lat=22.32, lng=114.17),
    stop("chicago", 2, 8.0, status="customs", lat=41.85, lng=-87.65),
    stop("largo", 3, 12.0, status="delivered", lat=27.91, lng=-82.79),
])


def current(canonicals):
    return [
        {
            "canonical": c,
            "status": "in_transit",
            "event_time": datetime(2026, 6, i + 1),
            "location_lat": COORDS.get(c, (None, None))[0],
            "location_lng": COORDS.get(c, (None, None))[1],
        }
        for i, c in enumerate(canonicals)
    ]


def parse_eta(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    return parsed.replace(tzinfo=None)


def test_matches_prefix_and_returns_future():
    best = _find_best_pattern(current(["shenzhen", "hong kong"]), [PATTERN_CN_US])
    assert best is not None
    assert best["matched_to"] == 2

    future = _extract_future_stops(best["pattern"], best["matched_to"], datetime(2026, 6, 1))
    assert [f["location_name"] for f in future] == ["Chicago", "Largo"]
    assert future[0]["location_lat"] == 41.85


def test_no_match_for_unrelated_route():
    assert _find_best_pattern(current(["berlin"]), [PATTERN_CN_US]) is None


def test_matches_canonical_values_case_insensitively():
    upper_case = FakePattern([stop("Shenzhen", 0, 0.2), stop("US", 1, 4.0)])
    best = _find_best_pattern(current(["shenzhen"]), [upper_case])
    assert best is not None
    assert best["matched_to"] == 1


def test_fully_traversed_pattern_is_skipped():
    stops_done = current(["shenzhen", "hong kong", "chicago", "largo"])
    assert _find_best_pattern(stops_done, [PATTERN_CN_US]) is None


def test_prefers_better_matching_pattern():
    other = FakePattern(
        [stop("shenzhen", 0, 0.2), stop("tokyo", 1, 3.0), stop("largo", 2, 10.0)],
        match_score=0.8,
    )
    best = _find_best_pattern(current(["shenzhen", "hong kong"]), [other, PATTERN_CN_US])
    assert best["pattern"] is PATTERN_CN_US


def test_prefers_destination_compatible_pattern():
    northeast = FakePattern(
        [
            stop("shenzhen", 0, 0.2, lat=22.55, lng=114.07),
            stop("chicago", 1, 8.0, lat=41.85, lng=-87.65),
            stop("new york", 2, 10.0, status="delivered", lat=40.71, lng=-74.0),
        ],
        match_score=0.8,
    )
    southeast = FakePattern(
        [
            stop("shenzhen", 0, 0.2, lat=22.55, lng=114.07),
            stop("chicago", 1, 8.0, lat=41.85, lng=-87.65),
            stop("atlanta", 2, 10.0, lat=33.75, lng=-84.39),
            stop("largo", 3, 12.0, status="delivered", lat=27.9098, lng=-82.7884),
        ],
        match_score=0.8,
    )

    best = _find_best_pattern(
        current(["shenzhen", "chicago"]),
        [northeast, southeast],
        dest_lat=27.9098,
        dest_lng=-82.7884,
    )

    assert best["pattern"] is southeast


def test_eta_anchored_to_journey_start_and_clamped():
    # Journey started long ago: ETAs in the past get clamped to "soon"
    best = _find_best_pattern(current(["shenzhen", "hong kong"]), [PATTERN_CN_US])
    future = _extract_future_stops(best["pattern"], best["matched_to"], datetime(2020, 1, 1))
    for f in future:
        eta = parse_eta(f["eta"])
        assert eta > datetime(2026, 1, 1)

    # Fresh journey: ETA = start + median days from start
    future2 = _extract_future_stops(best["pattern"], best["matched_to"], datetime(2099, 1, 1))
    assert future2[0]["eta"].endswith("+00:00")
    eta_chicago = parse_eta(future2[0]["eta"])
    assert (eta_chicago - datetime(2099, 1, 1)).days == 8


def test_geocodes_stops_missing_coordinates():
    llm_pattern = FakePattern([
        stop("shenzhen", 0, 0.2),
        {"canonical": "memphis", "location_name": "Memphis, TN", "status": "in_transit",
         "stop_order": 1, "median_days_from_start": 5.0, "p10_days": 4.0, "p90_days": 7.0,
         "frequency_pct": 80.0},
    ])
    best = _find_best_pattern(current(["shenzhen"]), [llm_pattern])
    future = _extract_future_stops(best["pattern"], best["matched_to"], datetime(2099, 1, 1))
    assert future[0]["location_lat"] is not None
    assert abs(future[0]["location_lat"] - 35.15) < 0.5


def test_future_stops_collapse_repeats_and_end_at_destination():
    noisy_pattern = FakePattern([
        stop("shenzhen", 0, 0.2),
        stop("chicago", 1, 8.0, lat=41.85, lng=-87.65),
        stop("new york", 2, 9.0, lat=40.71, lng=-74.0),
        stop("new york", 3, 10.0, lat=40.71, lng=-74.0),
        stop("new york", 4, 11.0, status="delivered", lat=40.71, lng=-74.0),
    ])
    best = _find_best_pattern(current(["shenzhen", "chicago"]), [noisy_pattern])
    future = _extract_future_stops(
        best["pattern"],
        best["matched_to"],
        datetime(2026, 6, 1),
        current_stops=current(["shenzhen", "chicago"]),
        dest_name="Largo, FL",
        dest_lat=27.9098,
        dest_lng=-82.7884,
    )

    names = [f["location_name"] for f in future]
    assert names[-1] == "Largo, FL"
    assert future[-1]["status"] == "delivered"
    assert future[-1]["location_lat"] == 27.9098

    assert "New York" in names, "Intermediate stops should be preserved"
    ny_count = names.count("New York")
    assert ny_count <= 2, f"Exact duplicates should be collapsed, got {ny_count} New York stops"
