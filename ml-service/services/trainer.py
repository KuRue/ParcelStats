from services.config import settings
from database.models import Shipment, CarrierRoute, ModelVersion, Carrier
from database.connection import SessionLocal
import numpy as np
import pandas as pd
import joblib
import os
import uuid
from sklearn.model_selection import cross_val_score
from xgboost import XGBRegressor
from services.timeutil import utcnow
from services.knowledge import (
    country_from_region, haversine_km, estimate_hops,
    get_seasonal_multiplier,
)


class ModelTrainer:
    def __init__(self):
        self.model_path = settings.model_path
        os.makedirs(self.model_path, exist_ok=True)

    def train_eta_model(self) -> dict:
        db = SessionLocal()
        try:
            completed = (
                db.query(Shipment)
                .filter(
                    Shipment.shipped_at.isnot(None),
                    Shipment.delivered_at.isnot(None),
                    Shipment.source == "user",
                )
                .all()
            )

            if len(completed) < 10:
                return {"status": "insufficient_data", "count": len(completed), "minimum": 10}

            rows = []
            for s in completed:
                if not _has_real_event_history(s):
                    continue

                duration_days = (s.delivered_at - s.shipped_at).total_seconds() / 86400
                if duration_days <= 0:
                    continue

                carrier = db.query(Carrier).filter(Carrier.id == s.carrier_id).first()
                if not carrier:
                    continue

                origin_region = (s.origin_name or "unknown").split(",")[-1].strip().lower()
                dest_region = (s.dest_name or "unknown").split(",")[-1].strip().lower()
                origin_country = country_from_region(origin_region)
                dest_country = country_from_region(dest_region)

                origin_lat = float(s.origin_lat) if s.origin_lat else None
                origin_lng = float(s.origin_lng) if s.origin_lng else None
                dest_lat = float(s.dest_lat) if s.dest_lat else None
                dest_lng = float(s.dest_lng) if s.dest_lng else None

                distance_km = 0.0
                if origin_lat and origin_lng and dest_lat and dest_lng:
                    distance_km = haversine_km(origin_lat, origin_lng, dest_lat, dest_lng)

                hops = estimate_hops(origin_country, dest_country, carrier.slug)
                seasonal = get_seasonal_multiplier(s.shipped_at.month)

                rows.append({
                    "carrier_slug": carrier.slug,
                    "origin_country": origin_country,
                    "dest_country": dest_country,
                    "service_type": s.service_type or "standard",
                    "weight_kg": float(s.weight_kg) if s.weight_kg else 1.0,
                    "distance_km": distance_km,
                    "estimated_hops": hops,
                    "shipped_month": s.shipped_at.month,
                    "shipped_dow": s.shipped_at.weekday(),
                    "seasonal_multiplier": seasonal,
                    "is_domestic": 1 if origin_country == dest_country else 0,
                    "duration_days": duration_days,
                })

            if len(rows) < 10:
                return {"status": "insufficient_data", "count": len(rows), "minimum": 10}

            df = pd.DataFrame(rows)

            cat_cols = ["carrier_slug", "origin_country", "dest_country", "service_type"]
            for col in cat_cols:
                df[col] = pd.Categorical(df[col]).codes

            features = cat_cols + [
                "weight_kg", "distance_km", "estimated_hops",
                "shipped_month", "shipped_dow", "seasonal_multiplier", "is_domestic",
            ]
            X = df[features]
            y = df["duration_days"]

            model_median = XGBRegressor(
                n_estimators=200,
                max_depth=6,
                learning_rate=0.1,
                objective="reg:squarederror",
                random_state=42,
            )
            model_p10 = XGBRegressor(
                n_estimators=200, max_depth=6, learning_rate=0.1,
                objective="reg:quantileerror", quantile_alpha=0.1, random_state=42,
            )
            model_p90 = XGBRegressor(
                n_estimators=200, max_depth=6, learning_rate=0.1,
                objective="reg:quantileerror", quantile_alpha=0.9, random_state=42,
            )

            model_median.fit(X, y)
            model_p10.fit(X, y)
            model_p90.fit(X, y)

            scores = cross_val_score(model_median, X, y, cv=min(5, len(rows) // 2), scoring="neg_mean_absolute_error")

            version = f"v{utcnow().strftime('%Y%m%d%H%M%S')}"
            artifact_path = os.path.join(self.model_path, version)
            os.makedirs(artifact_path, exist_ok=True)

            joblib.dump(model_median, os.path.join(artifact_path, "eta_median.pkl"))
            joblib.dump(model_p10, os.path.join(artifact_path, "eta_p10.pkl"))
            joblib.dump(model_p90, os.path.join(artifact_path, "eta_p90.pkl"))

            cats = {}
            for col in cat_cols:
                cats[col] = {v: k for k, v in dict(enumerate(pd.Categorical(df[col]).categories)).items()}

            joblib.dump({"features": features, "categories": cats}, os.path.join(artifact_path, "metadata.pkl"))

            metrics = {
                "mae": float(-scores.mean()),
                "samples": len(rows),
                "feature_count": len(features),
            }

            db.query(ModelVersion).filter(ModelVersion.model_name == "eta_predictor").update({"is_active": False})
            db.add(ModelVersion(
                id=str(uuid.uuid4()),
                model_name="eta_predictor",
                version=version,
                metrics=metrics,
                is_active=True,
            ))
            db.commit()

            self._update_carrier_routes(db)

            return {"status": "trained", "version": version, "metrics": metrics}

        finally:
            db.close()

    def _update_carrier_routes(self, db):
        completed = (
            db.query(Shipment)
            .filter(
                Shipment.shipped_at.isnot(None),
                Shipment.delivered_at.isnot(None),
                Shipment.source == "user",
            )
            .all()
        )

        route_data = {}
        for s in completed:
            if not _has_real_event_history(s):
                continue

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


def _has_real_event_history(shipment: Shipment) -> bool:
    events = shipment.events or []
    if len(events) < 2:
        return False
    return any(event.raw_data for event in events)
