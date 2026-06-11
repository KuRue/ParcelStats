import os
import joblib
import pandas as pd
import uuid
from datetime import datetime, timedelta
from database.connection import SessionLocal
from database.models import Shipment, Prediction, ModelVersion, Carrier
from services.config import settings
from services.knowledge import (
    country_from_region, haversine_km, estimate_hops,
    get_seasonal_multiplier,
)
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
        try:
            db = SessionLocal()
        except Exception:
            return
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
                shipped_at: datetime | None = None,
                origin_lat: float | None = None, origin_lng: float | None = None,
                dest_lat: float | None = None, dest_lng: float | None = None) -> dict | None:
        ref_date = shipped_at or utcnow()

        origin_country = country_from_region(origin_region)
        dest_country = country_from_region(dest_region)

        distance_km = 0.0
        if origin_lat and origin_lng and dest_lat and dest_lng:
            distance_km = haversine_km(origin_lat, origin_lng, dest_lat, dest_lng)

        hops = estimate_hops(origin_country, dest_country, carrier_slug)
        seasonal = get_seasonal_multiplier(ref_date.month)
        is_domestic = 1 if origin_country == dest_country else 0

        kb_args = (origin_country, dest_country, carrier_slug, service_type, ref_date, seasonal)

        if not self.is_ready:
            return self._knowledge_prediction(*kb_args)

        try:
            features = self.metadata["features"]
            has_old_features = "origin_region" in features

            encoded = {
                "carrier_slug": self._encode("carrier_slug", carrier_slug),
                "service_type": self._encode("service_type", service_type),
            }
            if has_old_features:
                encoded["origin_region"] = self._encode("origin_region", origin_region.lower())
                encoded["dest_region"] = self._encode("dest_region", dest_region.lower())
            else:
                encoded["origin_country"] = self._encode("origin_country", origin_country)
                encoded["dest_country"] = self._encode("dest_country", dest_country)

            if encoded["carrier_slug"] == -1:
                return self._knowledge_prediction(*kb_args)
            origin_ok = encoded.get("origin_region", encoded.get("origin_country", -1))
            dest_ok = encoded.get("dest_region", encoded.get("dest_country", -1))
            if origin_ok == -1 and dest_ok == -1:
                return self._knowledge_prediction(*kb_args)
            unknown_count = sum(1 for v in encoded.values() if v == -1)

            row = {}
            for f in features:
                if f in encoded:
                    row[f] = encoded[f]
                elif f == "weight_kg":
                    row[f] = weight_kg
                elif f == "distance_km":
                    row[f] = distance_km
                elif f == "estimated_hops":
                    row[f] = hops
                elif f == "shipped_month":
                    row[f] = ref_date.month
                elif f == "shipped_dow":
                    row[f] = ref_date.weekday()
                elif f == "seasonal_multiplier":
                    row[f] = seasonal
                elif f == "is_domestic":
                    row[f] = is_domestic
                else:
                    row[f] = 0

            X = pd.DataFrame([row])[features]

            median_days = float(self.model_median.predict(X)[0])
            p10_days = float(self.model_p10.predict(X)[0])
            p90_days = float(self.model_p90.predict(X)[0])

            p10_days = max(0.5, min(p10_days, median_days))
            p90_days = max(median_days, p90_days)

            median_days *= seasonal
            p10_days *= seasonal
            p90_days *= seasonal

            predicted_delivery = ref_date + timedelta(days=median_days)
            confidence_low = ref_date + timedelta(days=p10_days)
            confidence_high = ref_date + timedelta(days=p90_days)
            confidence_pct = self._calculate_confidence(median_days, p10_days, p90_days)
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
                "prediction_source": "ml",
            }
        except Exception:
            return self._knowledge_prediction(*kb_args)

    def _knowledge_prediction(self, origin_country: str, dest_country: str,
                              carrier_slug: str, service_type: str,
                              ref_date: datetime, seasonal: float) -> dict | None:
        from services.knowledge import predict_eta_knowledge
        result = predict_eta_knowledge(origin_country, dest_country, carrier_slug, service_type)
        if not result:
            return None

        # Blend in observed transit times for this lane, if we have any
        calibrated = False
        try:
            from services.calibration import get_lane_stats, blend_with_baseline
            db = SessionLocal()
            try:
                lane = get_lane_stats(db, carrier_slug, origin_country, dest_country, service_type)
            finally:
                db.close()
            if lane:
                result = blend_with_baseline(result, lane)
                calibrated = True
        except Exception:
            pass

        median_days = result["median_days"] * seasonal
        p10_days = result["p10_days"] * seasonal
        p90_days = result["p90_days"] * seasonal
        predicted_delivery = ref_date + timedelta(days=median_days)
        confidence_low = ref_date + timedelta(days=p10_days)
        confidence_high = ref_date + timedelta(days=p90_days)
        return {
            "predicted_delivery": predicted_delivery.isoformat(),
            "confidence_low": confidence_low.isoformat(),
            "confidence_high": confidence_high.isoformat(),
            "confidence_pct": result["confidence_pct"],
            "model_version": "knowledge-v1",
            "median_days": round(median_days, 2),
            "p10_days": round(p10_days, 2),
            "p90_days": round(p90_days, 2),
            "prediction_source": "knowledge+lanes" if calibrated else "knowledge",
            "calibration_samples": result.get("calibration_samples", 0),
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
            if not self._is_predictable_shipment(shipment):
                return None

            carrier = db.query(Carrier).filter(Carrier.id == shipment.carrier_id).first()
            if not carrier:
                return None

            origin = (shipment.origin_name or "unknown").split(",")[-1].strip()
            dest = (shipment.dest_name or "unknown").split(",")[-1].strip()

            # predict() falls back to the knowledge engine when no trained
            # model is loaded, so don't short-circuit here.
            result = self.predict(
                carrier_slug=carrier.slug,
                origin_region=origin,
                dest_region=dest,
                service_type=shipment.service_type or "standard",
                weight_kg=float(shipment.weight_kg) if shipment.weight_kg else 1.0,
                shipped_at=shipment.shipped_at,
                origin_lat=float(shipment.origin_lat) if shipment.origin_lat else None,
                origin_lng=float(shipment.origin_lng) if shipment.origin_lng else None,
                dest_lat=float(shipment.dest_lat) if shipment.dest_lat else None,
                dest_lng=float(shipment.dest_lng) if shipment.dest_lng else None,
            )

            if result:
                db.add(self._prediction_from_result(shipment_id, result))
                db.commit()

            return result
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
            features=result.get("features")
            or {"source": result.get("prediction_source", "unknown")},
        )

    def _is_delivered(self, shipment: Shipment) -> bool:
        status = (shipment.status or "").lower()
        return shipment.delivered_at is not None or (
            "deliver" in status and "fail" not in status and "exception" not in status
        )

    def _is_predictable_shipment(self, shipment: Shipment) -> bool:
        status = (shipment.status or "").lower()
        blocked_terms = [
            "exception",
            "error",
            "fail",
            "not_found",
            "not found",
            "required",
            "auth",
            "blocked",
            "unavailable",
        ]
        if any(term in status for term in blocked_terms):
            return False
        if not shipment.shipped_at:
            return False
        if not shipment.origin_name or not shipment.dest_name:
            return False
        return True

    def _to_datetime(self, value):
        return parse_to_naive_utc(value)

    def _naive_utc(self, value: datetime | None) -> datetime | None:
        return to_naive_utc(value)
