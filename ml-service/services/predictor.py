import os
import joblib
import pandas as pd
from datetime import datetime, timedelta
from database.connection import SessionLocal
from database.models import Shipment, Prediction, CarrierRoute, ModelVersion, Carrier
from services.config import settings


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

        ref_date = shipped_at or datetime.utcnow()

        features = self.metadata["features"]
        row = {}
        for f in features:
            if f == "carrier_slug":
                row[f] = self._encode("carrier_slug", carrier_slug)
            elif f == "origin_region":
                row[f] = self._encode("origin_region", origin_region.lower())
            elif f == "dest_region":
                row[f] = self._encode("dest_region", dest_region.lower())
            elif f == "service_type":
                row[f] = self._encode("service_type", service_type)
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

            carrier = db.query(Carrier).filter(Carrier.id == shipment.carrier_id).first()
            if not carrier:
                return None

            origin = (shipment.origin_name or "unknown").split(",")[-1].strip()
            dest = (shipment.dest_name or "unknown").split(",")[-1].strip()

            result = self.predict(
                carrier_slug=carrier.slug,
                origin_region=origin,
                dest_region=dest,
                service_type=shipment.service_type or "standard",
                weight_kg=float(shipment.weight_kg) if shipment.weight_kg else 1.0,
                shipped_at=shipment.shipped_at,
            )

            if result:
                db.add(Prediction(
                    shipment_id=shipment_id,
                    predicted_delivery=result["predicted_delivery"],
                    confidence_low=result["confidence_low"],
                    confidence_high=result["confidence_high"],
                    confidence_pct=result["confidence_pct"],
                    model_version=result["model_version"],
                ))
                db.commit()

            return result
        finally:
            db.close()

    def fallback_estimate(self, carrier_slug: str, origin_region: str, dest_region: str) -> dict | None:
        db = SessionLocal()
        try:
            carrier = db.query(Carrier).filter(Carrier.slug == carrier_slug).first()
            if not carrier:
                return None

            route = (
                db.query(CarrierRoute)
                .filter(
                    CarrierRoute.carrier_id == carrier.id,
                    CarrierRoute.origin_region == origin_region.lower(),
                    CarrierRoute.dest_region == dest_region.lower(),
                )
                .first()
            )

            if not route:
                return None

            ref = datetime.utcnow()
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
