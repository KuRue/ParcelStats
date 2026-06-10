import os
import joblib
import pandas as pd
import uuid
from datetime import datetime, timedelta
from database.connection import SessionLocal
from database.models import Shipment, Prediction, CarrierRoute, ModelVersion, Carrier
from services.config import settings
from services.timeutil import utcnow, to_naive_utc, parse_to_naive_utc


class ETAPredictor:
    def __init__(self):
        self.model_path = settings.model_path
        self.model_median = None
        self.model_p10 = None
        self.model_p90 = None
        self.metadata = None
        self.version = None
        self._load_model()

    def _load_model(self):
        db = SessionLocal()
        try:
            active = (
                db.query(ModelVersion)
                .filter(ModelVersion.model_name == "eta_predictor", ModelVersion.is_active)
                .first()
            )
            if not active:
                return

            artifact_path = os.path.join(self.model_path, active.version)
            if not os.path.exists(artifact_path):
                return

            self.model_median = joblib.load(os.path.join(artifact_path, "eta_median.pkl"))
            self.model_p10 = joblib.load(os.path.join(artifact_path, "eta_p10.pkl"))
            self.model_p90 = joblib.load(os.path.join(artifact_path, "eta_p90.pkl"))
            self.metadata = joblib.load(os.path.join(artifact_path, "metadata.pkl"))
            self.version = active.version
        finally:
            db.close()

    @property
    def is_ready(self) -> bool:
        return self.model_median is not None

    def predict(self, carrier_slug: str, origin_region: str, dest_region: str,
                service_type: str = "standard", weight_kg: float = 1.0,
                shipped_at: datetime | None = None) -> dict | None:
        if not self.is_ready:
            return None

        ref_date = shipped_at or utcnow()

        encoded = {
            "carrier_slug": self._encode("carrier_slug", carrier_slug),
            "origin_region": self._encode("origin_region", origin_region.lower()),
            "dest_region": self._encode("dest_region", dest_region.lower()),
            "service_type": self._encode("service_type", service_type),
        }
        # The model has never seen this carrier or lane, so its output would be
        # meaningless - bail out and let the fallback chain handle it.
        if encoded["carrier_slug"] == -1:
            return None
        if encoded["origin_region"] == -1 and encoded["dest_region"] == -1:
            return None
        unknown_count = sum(1 for v in encoded.values() if v == -1)

        features = self.metadata["features"]
        row = {}
        for f in features:
            if f in encoded:
                row[f] = encoded[f]
            elif f == "weight_kg":
                row[f] = weight_kg
            elif f == "shipped_month":
                row[f] = ref_date.month
            elif f == "shipped_dow":
                row[f] = ref_date.weekday()

        X = pd.DataFrame([row])[features]

        median_days = float(self.model_median.predict(X)[0])
        p10_days = float(self.model_p10.predict(X)[0])
        p90_days = float(self.model_p90.predict(X)[0])

        p10_days = max(0.5, min(p10_days, median_days))
        p90_days = max(median_days, p90_days)

        predicted_delivery = ref_date + timedelta(days=median_days)
        confidence_low = ref_date + timedelta(days=p10_days)
        confidence_high = ref_date + timedelta(days=p90_days)
        confidence_pct = self._calculate_confidence(median_days, p10_days, p90_days)
        # Partially-unseen inputs (e.g. unknown service type or one region)
        # still predict, but with reduced confidence.
        if unknown_count:
            confidence_pct = min(confidence_pct, 60.0 - 10.0 * (unknown_count - 1))

        return {
            "predicted_delivery": predicted_delivery.isoformat(),
            "confidence_low": confidence_low.isoformat(),
            "confidence_high": confidence_high.isoformat(),
            "confidence_pct": round(confidence_pct, 2),
            "model_version": self.version,
            "median_days": round(median_days, 2),
            "p10_days": round(p10_days, 2),
            "p90_days": round(p90_days, 2),
        }

    def _encode(self, feature: str, value: str) -> int:
        cats = self.metadata.get("categories", {}).get(feature, {})
        for k, v in cats.items():
            if v == value:
                return int(k)
        return -1

    def _calculate_confidence(self, median: float, p10: float, p90: float) -> float:
        if median <= 0:
            return 50.0
        spread = (p90 - p10) / median
        confidence = max(10, min(99, 95 - spread * 20))
        return confidence

    def predict_for_shipment(self, shipment_id: str) -> dict | None:
        db = SessionLocal()
        try:
            shipment = db.query(Shipment).filter(Shipment.id == shipment_id).first()
            if not shipment:
                return None
            if self._is_delivered(shipment):
                return None

            carrier = db.query(Carrier).filter(Carrier.id == shipment.carrier_id).first()
            if not carrier:
                return None

            origin = (shipment.origin_name or "unknown").split(",")[-1].strip()
            dest = (shipment.dest_name or "unknown").split(",")[-1].strip()

            result = None
            if self.is_ready:
                result = self.predict(
                    carrier_slug=carrier.slug,
                    origin_region=origin,
                    dest_region=dest,
                    service_type=shipment.service_type or "standard",
                    weight_kg=float(shipment.weight_kg) if shipment.weight_kg else 1.0,
                    shipped_at=shipment.shipped_at,
                )

            if not result:
                result = self.fallback_estimate(
                    carrier_slug=carrier.slug,
                    origin_region=origin,
                    dest_region=dest,
                    service_type=shipment.service_type or "standard",
                    ref_date=shipment.shipped_at,
                )

            if not result:
                result = self._carrier_estimate(shipment)

            if not result:
                result = self._baseline_estimate(shipment, carrier.slug)

            if result:
                db.add(self._prediction_from_result(shipment_id, result))
                db.commit()

            return result
        finally:
            db.close()

    def fallback_estimate(
        self,
        carrier_slug: str,
        origin_region: str,
        dest_region: str,
        service_type: str | None = None,
        ref_date: datetime | None = None,
    ) -> dict | None:
        db = SessionLocal()
        try:
            carrier = db.query(Carrier).filter(Carrier.slug == carrier_slug).first()
            if not carrier:
                return None

            query = (
                db.query(CarrierRoute)
                .filter(
                    CarrierRoute.carrier_id == carrier.id,
                    CarrierRoute.origin_region == origin_region.lower(),
                    CarrierRoute.dest_region == dest_region.lower(),
                )
            )
            route = query.filter(CarrierRoute.service_type == service_type).first()
            if not route:
                route = query.order_by(CarrierRoute.sample_count.desc()).first()

            if not route:
                return None

            ref = self._naive_utc(ref_date) or utcnow()
            return {
                "predicted_delivery": (ref + timedelta(days=float(route.median_days))).isoformat(),
                "confidence_low": (ref + timedelta(days=float(route.p10_days))).isoformat(),
                "confidence_high": (ref + timedelta(days=float(route.p90_days))).isoformat(),
                "confidence_pct": max(10, min(70, 70 - (float(route.p90_days) - float(route.p10_days)) * 5)),
                "model_version": "fallback_route_stats",
                "median_days": float(route.median_days),
                "sample_count": route.sample_count,
            }
        finally:
            db.close()

    def _prediction_from_result(self, shipment_id: str, result: dict) -> Prediction:
        return Prediction(
            id=str(uuid.uuid4()),
            shipment_id=shipment_id,
            predicted_delivery=self._to_datetime(result["predicted_delivery"]),
            confidence_low=self._to_datetime(result.get("confidence_low")),
            confidence_high=self._to_datetime(result.get("confidence_high")),
            confidence_pct=result.get("confidence_pct"),
            model_version=result["model_version"],
            features=result.get("features"),
        )

    def _carrier_estimate(self, shipment: Shipment) -> dict | None:
        if not shipment.estimated_delivery:
            return None

        predicted = shipment.estimated_delivery
        predicted = self._naive_utc(predicted) or predicted
        return {
            "predicted_delivery": predicted.isoformat(),
            "confidence_low": (predicted - timedelta(days=1)).isoformat(),
            "confidence_high": (predicted + timedelta(days=1)).isoformat(),
            "confidence_pct": 70,
            "model_version": "carrier_estimate",
            "features": {"source": "carrier_estimated_delivery"},
        }

    def _baseline_estimate(self, shipment: Shipment, carrier_slug: str) -> dict:
        ref = self._naive_utc(shipment.shipped_at) or utcnow()
        median_days = self._baseline_days(carrier_slug, shipment.origin_name, shipment.dest_name)
        predicted = ref + timedelta(days=median_days)
        minimum_prediction = utcnow() + timedelta(days=1)
        if predicted < minimum_prediction:
            predicted = minimum_prediction

        return {
            "predicted_delivery": predicted.isoformat(),
            "confidence_low": (predicted - timedelta(days=2)).isoformat(),
            "confidence_high": (predicted + timedelta(days=4)).isoformat(),
            "confidence_pct": 45,
            "model_version": "baseline_eta",
            "median_days": median_days,
            "features": {
                "carrier_slug": carrier_slug,
                "source": "baseline",
            },
        }

    def _baseline_days(self, carrier_slug: str, origin_name: str | None, dest_name: str | None) -> int:
        defaults = {
            "usps": 4,
            "ups": 4,
            "fedex": 4,
            "dhl-express": 5,
            "speedpak": 10,
        }
        days = defaults.get(carrier_slug, 7)

        origin_country = self._country_token(origin_name)
        dest_country = self._country_token(dest_name)
        if origin_country and dest_country and origin_country != dest_country:
            days += 3

        return days

    def _country_token(self, location_name: str | None) -> str | None:
        if not location_name or "," not in location_name:
            return None
        return location_name.split(",")[-1].strip().lower()

    def _is_delivered(self, shipment: Shipment) -> bool:
        status = (shipment.status or "").lower()
        return shipment.delivered_at is not None or (
            "deliver" in status and "fail" not in status and "exception" not in status
        )

    def _to_datetime(self, value):
        return parse_to_naive_utc(value)

    def _naive_utc(self, value: datetime | None) -> datetime | None:
        return to_naive_utc(value)
