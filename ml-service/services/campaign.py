import random
import uuid
import logging
import re
from database.connection import SessionLocal
from database.models import Shipment, ShipmentEvent, Carrier, ScrapeJob
from services.queue import JobQueue

logger = logging.getLogger("parcelstats.campaign")


def generate_usps():
    prefix = random.choice(["9400", "9405", "9414", "9444", "9205", "9270"])
    return f"{prefix}{random.randint(1000000000, 9999999999)}"


def generate_ups():
    service_code = random.choice(["AA", "1A", "YW", "FV", "96"])
    region = random.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
    num = f"{random.randint(100000000000, 999999999999)}"
    check = _ups_check_digit(f"1Z{service_code}{region}{num}")
    return f"1Z{service_code}{region}{num[:11]}{check}"


def generate_fedex():
    fmt = random.choice(["express", "ground", "smartpost"])
    if fmt == "express":
        return f"{random.randint(100000000000, 999999999999)}"
    elif fmt == "ground":
        return f"{''.join(random.choices('0123456789', k=15))}"
    else:
        return f"92{''.join(random.choices('0123456789', k=20))}"


def generate_dhl():
    return f"{random.randint(1000000000, 9999999999)}"


def generate_speedpak():
    return f"SP{random.randint(1000000000, 9999999999)}CN"


def generate_royal_mail():
    prefix = random.choice(["JV", "JD", "JG", "JN", "RR", "RN"])
    return f"{prefix}{random.randint(100000000, 999999999)}GB"


def generate_canada_post():
    return f"{random.randint(100000000000, 999999999999)}"


def generate_australia_post():
    prefix = random.choice(["AU", "SY", "ME", "CR"])
    return f"{prefix}{random.randint(1000000000, 9999999999)}"


def generate_japan_post():
    prefix = random.choice(["EJ", "RR", "CD", "EM"])
    return f"{prefix}{random.randint(100000000, 999999999)}JP"


def generate_deutsche_post():
    prefix = random.choice(["JJ", "JX", "CK", "RG", "RR"])
    return f"{prefix}{random.randint(100000000, 999999999)}DE"


def generate_china_post():
    prefix = random.choice(["CP", "EE", "LX", "RY", "LP"])
    return f"{prefix}{random.randint(100000000, 999999999)}CN"


def generate_india_post():
    prefix = random.choice(["EM", "RP", "CP", "EE"])
    return f"{prefix}{random.randint(100000000, 999999999)}IN"


def generate_korea_post():
    prefix = random.choice(["EM", "RR", "CP"])
    return f"{prefix}{random.randint(100000000, 999999999)}KR"


def generate_brazil():
    return f"{random.choice(['OA', 'OH', 'ON'])}{random.randint(100000000, 999999999)}BR"


def generate_generic(slug):
    prefix = slug[:2].upper()
    return f"{prefix}{random.randint(1000000000, 9999999999)}"


GENERATORS = {
    "usps": generate_usps,
    "ups": generate_ups,
    "fedex": generate_fedex,
    "dhl-express": generate_dhl,
    "speedpak": generate_speedpak,
    "royal-mail": generate_royal_mail,
    "canada-post": generate_canada_post,
    "australia-post": generate_australia_post,
    "japan-post": generate_japan_post,
    "deutsche-post": generate_deutsche_post,
    "china-post": generate_china_post,
    "india-post": generate_india_post,
    "correos-spain": lambda: f"{random.choice(['RR', 'CP', 'PQ'])}{random.randint(100000000, 999999999)}ES",
    "poste-italiane": lambda: f"{random.choice(['RR', 'CP', 'RA'])}{random.randint(100000000, 999999999)}IT",
    "la-poste": lambda: f"{random.choice(['RR', 'CP', 'EE'])}{random.randint(100000000, 999999999)}FR",
    "postnord": lambda: f"{random.choice(['RR', 'CP', 'EE'])}{random.randint(100000000, 999999999)}SE",
    "swiss-post": lambda: f"{random.choice(['RR', 'CP', 'EE'])}{random.randint(100000000, 999999999)}CH",
    "an-post": lambda: f"{random.choice(['RR', 'CP'])}{random.randint(100000000, 999999999)}IE",
    "nz-post": lambda: f"{random.choice(['RR', 'CP'])}{random.randint(100000000, 999999999)}NZ",
    "singapore-post": lambda: f"{random.choice(['RR', 'CP'])}{random.randint(100000000, 999999999)}SG",
    "pos-malaysia": lambda: f"{random.choice(['RR', 'CP'])}{random.randint(100000000, 999999999)}MY",
    "thai-post": lambda: f"{random.choice(['RR', 'CP', 'EA'])}{random.randint(100000000, 999999999)}TH",
    "polish-post": lambda: f"{random.choice(['RR', 'CP'])}{random.randint(100000000, 999999999)}PL",
    "israel-post": lambda: f"{random.choice(['RR', 'CP'])}{random.randint(100000000, 999999999)}IL",
    "brazil-correios": generate_brazil,
    "korea-post": generate_korea_post,
    "yanwen": lambda: f"YW{random.randint(1000000000, 9999999999)}",
    "dhl-parcel-de": lambda: f"{random.randint(10000000000000, 99999999999999)}",
    "gls": lambda: f"{random.randint(10000000000, 99999999999)}",
    "hermes": lambda: f"H{random.randint(1000000000000, 9999999999999)}",
}


def _ups_check_digit(tracking: str) -> int:
    digits = [int(c) for c in tracking if c.isdigit()]
    total = sum(d * 3 if i % 2 == 0 else d for i, d in enumerate(digits))
    return (10 - (total % 10)) % 10


def run_campaign(
    carriers: list[str] | None = None,
    per_carrier: int = 50,
    batch_size: int = 500,
) -> dict:
    db = SessionLocal()
    try:
        all_carriers = db.query(Carrier).all()
        carrier_map = {c.slug: c for c in all_carriers}

        if carriers:
            target_slugs = [s for s in carriers if s in carrier_map]
        else:
            target_slugs = list(carrier_map.keys())

        queue = JobQueue()
        total_queued = 0
        total_skipped = 0
        results = {}

        for slug in target_slugs:
            carrier = carrier_map[slug]
            gen_func = GENERATORS.get(slug)
            queued = 0
            seen = set()

            for _ in range(per_carrier):
                tn = gen_func() if gen_func else generate_generic(slug)
                while tn in seen:
                    tn = gen(slug)
                seen.add(tn)

                existing = db.query(Shipment).filter(
                    Shipment.tracking_number == tn,
                    Shipment.carrier_id == carrier.id,
                ).first()
                if existing:
                    total_skipped += 1
                    continue

                shipment_id = str(uuid.uuid4())
                shipment = Shipment(
                    id=shipment_id,
                    tracking_number=tn,
                    carrier_id=carrier.id,
                    user_id=None,
                    status="pending",
                    source="campaign",
                )
                db.add(shipment)

                queue.enqueue(
                    tracking_number=tn,
                    carrier_slug=slug,
                    shipment_id=shipment_id,
                )
                queued += 1

            if queued > 0 and total_queued > 0 and total_queued % 100 == 0:
                db.commit()

            results[slug] = queued
            total_queued += queued

        db.commit()

        logger.info(f"Campaign queued {total_queued} shipments across {len(target_slugs)} carriers")

        return {
            "status": "campaign_started",
            "total_queued": total_queued,
            "per_carrier": per_carrier,
            "carriers": results,
        }
    except Exception as e:
        db.rollback()
        logger.error(f"Campaign failed: {e}")
        return {"status": "error", "message": str(e)}
    finally:
        db.close()
