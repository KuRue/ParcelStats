from fastapi import APIRouter, Query
from services.flights import flights_for_route, get_cached_flights, update_flight_cache

router = APIRouter(prefix="/flights", tags=["flights"])


@router.get("/route")
async def flights_on_route(
    origin_lat: float = Query(...),
    origin_lng: float = Query(...),
    dest_lat: float = Query(...),
    dest_lng: float = Query(...),
    corridor_width: float = Query(600),
):
    """Return cargo flights near the great-circle path between two points."""
    flights = flights_for_route(
        origin_lat, origin_lng,
        dest_lat, dest_lng,
        corridor_width_km=corridor_width,
    )
    return {"status": "ok", "count": len(flights), "flights": flights}


@router.get("/cached")
async def cached_flights():
    """Return all cached cargo flights (for debugging/global view)."""
    flights = get_cached_flights()
    return {
        "status": "ok",
        "count": len(flights),
        "flights": [
            {
                "icao24": f.icao24,
                "callsign": f.callsign,
                "latitude": f.latitude,
                "longitude": f.longitude,
                "altitude": f.altitude,
                "velocity": f.velocity,
                "heading": f.heading,
                "on_ground": f.on_ground,
                "origin_country": f.origin_country,
            }
            for f in flights
        ],
    }


@router.post("/refresh")
async def refresh_flights():
    """Force-refresh the flight cache."""
    count = await update_flight_cache()
    return {"status": "ok", "cached": count}
