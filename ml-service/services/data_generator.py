import random
import uuid
import logging
from datetime import timedelta
from database.connection import SessionLocal
from database.models import Shipment, ShipmentEvent, Carrier, CarrierRoute
import numpy as np
from services.timeutil import utcnow

logger = logging.getLogger("parcelstats.seed")

REGIONS = {
    "US": ["CA", "NY", "TX", "FL", "IL", "PA", "OH", "GA", "NC", "MI", "WA", "AZ", "MA", "VA", "CO"],
    "CN": ["Guangdong", "Shanghai", "Beijing", "Shenzhen", "Zhejiang", "Jiangsu"],
    "DE": ["Berlin", "Munich", "Hamburg", "Frankfurt", "Cologne"],
    "GB": ["London", "Manchester", "Birmingham", "Liverpool", "Edinburgh"],
    "JP": ["Tokyo", "Osaka", "Yokohama", "Nagoya", "Sapporo"],
    "AU": ["Sydney", "Melbourne", "Brisbane", "Perth", "Adelaide"],
    "CA": ["Toronto", "Vancouver", "Montreal", "Calgary", "Ottawa"],
    "FR": ["Paris", "Lyon", "Marseille", "Toulouse", "Nice"],
    "KR": ["Seoul", "Busan", "Incheon", "Daegu"],
    "IN": ["Mumbai", "Delhi", "Bangalore", "Chennai", "Kolkata"],
    "BR": ["Sao Paulo", "Rio de Janeiro", "Brasilia", "Salvador"],
    "MX": ["Mexico City", "Guadalajara", "Monterrey", "Puebla"],
    "IT": ["Rome", "Milan", "Naples", "Turin", "Florence"],
    "ES": ["Madrid", "Barcelona", "Valencia", "Seville"],
    "NL": ["Amsterdam", "Rotterdam", "The Hague", "Utrecht"],
    "SE": ["Stockholm", "Gothenburg", "Malmo"],
    "NZ": ["Auckland", "Wellington", "Christchurch"],
    "SG": ["Singapore"],
    "MY": ["Kuala Lumpur", "Penang", "Johor Bahru"],
    "TH": ["Bangkok", "Chiang Mai", "Pattaya"],
    "CH": ["Zurich", "Geneva", "Basel", "Bern"],
    "IE": ["Dublin", "Cork", "Galway"],
    "PL": ["Warsaw", "Krakow", "Wroclaw"],
    "IL": ["Tel Aviv", "Jerusalem", "Haifa"],
}

CARRIER_TRANSIT = {
    "usps": {
        "domestic": {"std": 2.0, "min": 1, "max": 8, "services": ["Priority Mail", "First Class", "Ground Advantage", "Media Mail"]},
        "international": {"std": 3.0, "min": 5, "max": 30, "services": ["Priority Mail International", "First Class International"]},
    },
    "ups": {
        "domestic": {"std": 1.5, "min": 1, "max": 7, "services": ["Ground", "2nd Day Air", "Next Day Air", "3 Day Select"]},
        "international": {"std": 2.5, "min": 3, "max": 21, "services": ["Worldwide Expedited", "Worldwide Express", "Standard"]},
    },
    "fedex": {
        "domestic": {"std": 1.5, "min": 1, "max": 7, "services": ["Ground", "Express Saver", "2Day", "Priority Overnight"]},
        "international": {"std": 2.0, "min": 2, "max": 14, "services": ["International Economy", "International Priority", "International First"]},
    },
    "dhl-express": {
        "domestic": {"std": 0.5, "min": 1, "max": 3, "services": ["Express", "Express 12:00"]},
        "international": {"std": 1.5, "min": 2, "max": 10, "services": ["Express Worldwide", "Express 12:00", "Economy Select"]},
    },
    "speedpak": {
        "domestic": {"std": 3.0, "min": 3, "max": 15, "services": ["Standard", "Expedited"]},
        "international": {"std": 5.0, "min": 7, "max": 35, "services": ["Standard", "Expedited", "Economy"]},
    },
    "royal-mail": {
        "domestic": {"std": 1.0, "min": 1, "max": 5, "services": ["First Class", "Second Class", "Special Delivery"]},
        "international": {"std": 4.0, "min": 5, "max": 25, "services": ["International Standard", "International Tracked"]},
    },
    "canada-post": {
        "domestic": {"std": 2.0, "min": 1, "max": 8, "services": ["Regular Parcel", "Expedited Parcel", "Priority"]},
        "international": {"std": 3.5, "min": 5, "max": 21, "services": ["International Parcel", "Xpresspost International"]},
    },
    "australia-post": {
        "domestic": {"std": 2.0, "min": 1, "max": 8, "services": ["Standard", "Express", "Priority"]},
        "international": {"std": 4.0, "min": 5, "max": 28, "services": ["Standard", "Express", "Economy"]},
    },
    "japan-post": {
        "domestic": {"std": 1.0, "min": 1, "max": 4, "services": ["Standard", "Express", "Registered"]},
        "international": {"std": 3.0, "min": 5, "max": 21, "services": ["EMS", "Airmail", "SAL", "Surface"]},
    },
    "deutsche-post": {
        "domestic": {"std": 1.5, "min": 1, "max": 5, "services": ["Standard", "Express", "Priority"]},
        "international": {"std": 3.0, "min": 3, "max": 18, "services": ["DHL Paket International", "Premium"]},
    },
    "china-post": {
        "domestic": {"std": 3.0, "min": 2, "max": 10, "services": ["Standard", "EMS", "Express"]},
        "international": {"std": 7.0, "min": 10, "max": 45, "services": ["Registered", "E-Packet", "EMS", "SAL"]},
    },
    "india-post": {
        "domestic": {"std": 3.0, "min": 2, "max": 12, "services": ["Speed Post", "Registered", "Express"]},
        "international": {"std": 5.0, "min": 7, "max": 30, "services": ["Speed Post", "Registered", "Air Parcel"]},
    },
}

CARRIER_COUNTRIES = {
    "usps": "US", "ups": "US", "fedex": "US", "dhl-express": "DE",
    "speedpak": "CN", "royal-mail": "GB", "canada-post": "CA",
    "australia-post": "AU", "japan-post": "JP", "deutsche-post": "DE",
    "china-post": "CN", "india-post": "IN", "correos-spain": "ES",
    "poste-italiane": "IT", "la-poste": "FR", "postnord": "SE",
    "swiss-post": "CH", "an-post": "IE", "nz-post": "NZ",
    "singapore-post": "SG", "pos-malaysia": "MY", "thai-post": "TH",
    "polish-post": "PL", "israel-post": "IL", "brazil-correios": "BR",
}

TRACKING_FORMATS = {
    "usps": lambda: f"9400{random.randint(1000000000, 9999999999)}",
    "ups": lambda: f"1Z{random.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZ')}{random.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZ')}{random.randint(100000000000, 999999999999)}",
    "fedex": lambda: f"{random.randint(100000000000, 999999999999)}",
    "dhl-express": lambda: f"{random.randint(1000000000, 9999999999)}",
    "speedpak": lambda: f"SP{random.randint(1000000000, 9999999999)}CN",
    "royal-mail": lambda: f"{random.choice(['JV', 'JD', 'JG', 'JN'])}{random.randint(100000000, 999999999)}GB",
    "canada-post": lambda: f"{random.randint(100000000000, 999999999999)}",
    "australia-post": lambda: f"{random.choice(['AU', 'SY', 'ME'])}{random.randint(1000000000, 9999999999)}",
    "japan-post": lambda: f"{random.choice(['EJ', 'RR', 'CD'])}{random.randint(100000000, 999999999)}JP",
    "deutsche-post": lambda: f"{random.choice(['JJ', 'JX', 'CK'])}{random.randint(100000000, 999999999)}DE",
    "china-post": lambda: f"{random.choice(['CP', 'EE', 'LX', 'RY'])}{random.randint(100000000, 999999999)}CN",
    "india-post": lambda: f"{random.choice(['EM', 'RP', 'CP'])}{random.randint(100000000, 999999999)}IN",
}

EVENT_TEMPLATES = {
    "label_created": "Shipping label created",
    "pending": ["Package accepted at origin facility", "Package received at {location}", "Picked up from sender"],
    "arrived_at_facility": ["Arrived at {location} sort facility", "Package arrived at {location} distribution center", "Processed at {location}"],
    "departed_facility": ["Departed {location} facility", "Shipped from {location}", "In transit from {location}"],
    "in_transit": ["In transit to next facility", "Package moving through network", "On the way"],
    "customs": ["Cleared customs at {location}", "Customs processing at {location}", "Released from customs"],
    "out_for_delivery": ["Out for delivery in {location}", "With delivery driver - {location}", "Final delivery attempt"],
    "delivered": ["Delivered to recipient", "Delivered - left at front door", "Delivered to {location}", "Signed for by recipient"],
}


def generate_tracking_number(carrier_slug: str) -> str:
    gen = TRACKING_FORMATS.get(carrier_slug)
    if gen:
        return gen()
    prefix = carrier_slug[:2].upper()
    return f"{prefix}{random.randint(1000000000, 9999999999)}"


def generate_synthetic_shipments(count: int = 2000) -> dict:
    db = SessionLocal()
    try:
        carriers = db.query(Carrier).all()
        if not carriers:
            return {"status": "error", "message": "No carriers found"}

        carrier_map = {c.slug: c for c in carriers}
        created = 0
        skipped = 0

        all_country_codes = list(REGIONS.keys())

        for i in range(count):
            slug = random.choice(list(CARRIER_TRANSIT.keys()))
            carrier = carrier_map.get(slug)
            if not carrier:
                skipped += 1
                continue

            carrier_country = CARRIER_COUNTRIES.get(slug, "US")

            is_domestic = random.random() < 0.6
            if is_domestic:
                origin_country = carrier_country
                dest_country = carrier_country
                transit_info = CARRIER_TRANSIT[slug]["domestic"]
            else:
                origin_country = carrier_country
                candidates = [c for c in all_country_codes if c != carrier_country]
                dest_country = random.choice(candidates)
                transit_info = CARRIER_TRANSIT[slug].get("international", CARRIER_TRANSIT[slug]["domestic"])

            origin_city = random.choice(REGIONS.get(origin_country, ["Unknown"]))
            dest_city = random.choice(REGIONS.get(dest_country, ["Unknown"]))

            origin_name = f"{origin_city}, {origin_country}"
            dest_name = f"{dest_city}, {dest_country}"

            service = random.choice(transit_info["services"])
            service_type = "express" if any(k in service.lower() for k in ["express", "priority", "overnight", "ems", "next day"]) else "standard"

            mean_days = transit_info["std"] + (2.0 if service_type == "standard" else 0)
            duration_days = max(transit_info["min"], min(transit_info["max"], np.random.normal(mean_days, transit_info["std"] * 0.5)))
            duration_days = round(duration_days, 1)

            shipped_at = utcnow() - timedelta(days=random.randint(30, 365))
            delivered_at = shipped_at + timedelta(days=duration_days)

            num_events = random.randint(3, 8)
            event_times = sorted([
                shipped_at + timedelta(days=duration_days * (i / num_events) + random.uniform(0, 0.3))
                for i in range(num_events)
            ])

            status_progression = _generate_status_progression(num_events, is_domestic)

            tracking_number = generate_tracking_number(slug)

            shipment_id = str(uuid.uuid4())
            shipment = Shipment(
                id=shipment_id,
                tracking_number=tracking_number,
                carrier_id=carrier.id,
                user_id=None,
                status="delivered",
                service_type=service,
                weight_kg=round(random.uniform(0.1, 25.0), 2),
                origin_name=origin_name,
                dest_name=dest_name,
                shipped_at=shipped_at,
                delivered_at=delivered_at,
                estimated_delivery=delivered_at - timedelta(hours=random.uniform(-12, 12)),
            )
            db.add(shipment)

            for j, (evt_time, evt_status) in enumerate(zip(event_times, status_progression)):
                if is_domestic:
                    location = random.choice([origin_name, dest_name, f"HUB, {origin_country}"])
                else:
                    if j < len(event_times) // 2:
                        location = origin_name
                    elif j == len(event_times) // 2:
                        location = "Customs, Transit"
                    else:
                        location = dest_name

                template = random.choice(EVENT_TEMPLATES.get(evt_status, [evt_status]))
                description = template.format(location=location)

                db.add(ShipmentEvent(
                    id=str(uuid.uuid4()),
                    shipment_id=shipment_id,
                    status=evt_status,
                    location_name=location,
                    description=description,
                    event_time=evt_time,
                ))

            created += 1
            if created % 100 == 0:
                db.commit()
                logger.info(f"Seeded {created}/{count} shipments")

        db.commit()

        _update_carrier_routes(db)

        return {
            "status": "success",
            "created": created,
            "skipped": skipped,
            "total_requested": count,
        }
    except Exception as e:
        db.rollback()
        logger.error(f"Seed failed: {e}")
        return {"status": "error", "message": str(e)}
    finally:
        db.close()


def _generate_status_progression(num_events: int, is_domestic: bool) -> list[str]:
    if is_domestic:
        pipeline = ["label_created", "pending", "arrived_at_facility", "departed_facility", "in_transit", "arrived_at_facility", "out_for_delivery", "delivered"]
    else:
        pipeline = ["label_created", "pending", "departed_facility", "arrived_at_facility", "in_transit", "customs", "departed_facility", "arrived_at_facility", "out_for_delivery", "delivered"]

    if num_events <= len(pipeline):
        indices = sorted(random.sample(range(len(pipeline)), num_events))
        return [pipeline[i] for i in indices]

    result = list(pipeline)
    while len(result) < num_events:
        insert_idx = random.randint(1, len(result) - 2)
        if result[insert_idx] in ("in_transit", "departed_facility", "arrived_at_facility"):
            result.insert(insert_idx, result[insert_idx])
        else:
            result.insert(insert_idx, "in_transit")
    return result[:num_events]


def _update_carrier_routes(db):
    completed = (
        db.query(Shipment)
        .filter(Shipment.shipped_at.isnot(None), Shipment.delivered_at.isnot(None))
        .all()
    )

    route_data = {}
    for s in completed:
        carrier = db.query(Carrier).filter(Carrier.id == s.carrier_id).first()
        if not carrier:
            continue

        origin = (s.origin_name or "unknown").split(",")[-1].strip().lower()
        dest = (s.dest_name or "unknown").split(",")[-1].strip().lower()
        key = (carrier.id, origin, dest, s.service_type or "standard")

        duration = (s.delivered_at - s.shipped_at).total_seconds() / 86400
        if duration <= 0:
            continue

        if key not in route_data:
            route_data[key] = []
        route_data[key].append(duration)

    for (carrier_id, origin, dest, service), durations in route_data.items():
        arr = np.array(durations)
        existing = (
            db.query(CarrierRoute)
            .filter(
                CarrierRoute.carrier_id == carrier_id,
                CarrierRoute.origin_region == origin,
                CarrierRoute.dest_region == dest,
                CarrierRoute.service_type == service,
            )
            .first()
        )

        if existing:
            existing.avg_days = float(np.mean(arr))
            existing.median_days = float(np.median(arr))
            existing.p10_days = float(np.percentile(arr, 10))
            existing.p90_days = float(np.percentile(arr, 90))
            existing.sample_count = len(arr)
            existing.updated_at = utcnow()
        else:
            db.add(CarrierRoute(
                id=str(uuid.uuid4()),
                carrier_id=carrier_id,
                origin_region=origin,
                dest_region=dest,
                service_type=service,
                avg_days=float(np.mean(arr)),
                median_days=float(np.median(arr)),
                p10_days=float(np.percentile(arr, 10)),
                p90_days=float(np.percentile(arr, 90)),
                sample_count=len(arr),
            ))

    db.commit()
    logger.info(f"Updated {len(route_data)} carrier routes")
