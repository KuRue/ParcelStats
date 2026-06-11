"""Route research agent that queries an LLM (OpenAI-compatible) for
carrier routing knowledge and stores the results as route patterns.

Can be used to:
1. Research a specific carrier + lane and store as a knowledge-based pattern
2. Enrich existing mined patterns with LLM-generated labels and context
3. Fill gaps for lanes with no historical data
"""
import json
import logging
import uuid
from typing import Optional
from openai import OpenAI

from database.connection import SessionLocal
from database.models import Carrier, RoutePattern
from services.config import settings
from services.agent.prompts import ROUTE_RESEARCH_SYSTEM, LANE_RESEARCH_USER
from services.timeutil import utcnow

logger = logging.getLogger("parcelstats.agent.research")


class RouteResearchAgent:
    def __init__(self):
        self.base_url = settings.openai_base_url
        self.api_key = settings.openai_api_key
        self.model = settings.openai_model
        self._client: Optional[OpenAI] = None

    @property
    def available(self) -> bool:
        return bool(self.base_url and self.api_key)

    def _get_client(self):
        if self._client is None:
            self._client = OpenAI(
                base_url=self.base_url,
                api_key=self.api_key,
            )
        return self._client

    def research_lane(self, carrier_slug: str, origin_country: str,
                      dest_country: str) -> dict | None:
        """Research a carrier lane and return a structured route pattern."""
        if not self.available:
            logger.warning("OpenAI not configured — skipping research")
            return None

        client = self._get_client()
        user_msg = LANE_RESEARCH_USER.format(
            carrier_slug=carrier_slug,
            origin_country=origin_country,
            dest_country=dest_country,
        )

        try:
            resp = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": ROUTE_RESEARCH_SYSTEM},
                    {"role": "user", "content": user_msg},
                ],
                response_format={"type": "json_object"},
                temperature=0.3,
                max_tokens=2000,
            )
            content = resp.choices[0].message.content
            if not content:
                logger.warning(f"Empty response from LLM for {carrier_slug} {origin_country}→{dest_country}")
                return None
            return json.loads(content)
        except Exception as e:
            logger.error(f"LLM research failed for {carrier_slug} {origin_country}→{dest_country}: {e}")
            return None

    def research_and_store(self, carrier_slug: str, origin_country: str,
                           dest_country: str) -> dict:
        """Research a lane and store the result as a route_pattern if new."""
        result = {"carrier": carrier_slug, "origin": origin_country,
                  "dest": dest_country, "created": False, "error": None}

        data = self.research_lane(carrier_slug, origin_country, dest_country)
        if not data:
            result["error"] = "No data returned from LLM"
            return result

        db = SessionLocal()
        try:
            carrier = db.query(Carrier).filter(Carrier.slug == carrier_slug).first()
            if not carrier:
                result["error"] = f"Carrier {carrier_slug} not found"
                return result

            stops = data.get("stops", [])
            if not stops:
                result["error"] = "No stops in LLM response"
                return result

            label = data.get("label", f"{origin_country}→{dest_country} via LLM")

            existing = (
                db.query(RoutePattern)
                .filter(
                    RoutePattern.carrier_id == carrier.id,
                    RoutePattern.origin_country == origin_country,
                    RoutePattern.dest_country == dest_country,
                    RoutePattern.label == label,
                )
                .first()
            )
            if existing:
                result["created"] = False
                result["message"] = "Pattern already exists"
                return result

            pattern = RoutePattern(
                id=str(uuid.uuid4()),
                carrier_id=carrier.id,
                origin_country=origin_country,
                dest_country=dest_country,
                service_type="standard",
                label=label,
                stops=stops,
                sample_count=1,
                match_score=0.3,
            )
            db.add(pattern)
            db.commit()
            result["created"] = True
            result["pattern_id"] = pattern.id
            result["stops_count"] = len(stops)
            logger.info(
                f"Stored LLM-researched pattern: {carrier_slug} "
                f"{origin_country}→{dest_country} ({len(stops)} stops)"
            )
        except Exception as e:
            db.rollback()
            result["error"] = str(e)
            logger.error(f"Failed to store research for {carrier_slug}: {e}")
        finally:
            db.close()

        return result

    def enrich_all_patterns(self):
        """Enrich existing mined patterns with LLM labels and context."""
        if not self.available:
            logger.warning("OpenAI not configured — skipping enrichment")
            return {"enriched": 0, "skipped": 0}

        db = SessionLocal()
        try:
            patterns = (
                db.query(RoutePattern)
                .filter(RoutePattern.label.like("%→% via %"))
                .all()
            )
        finally:
            db.close()

        enriched = 0
        for p in patterns:
            carrier = db.query(Carrier).filter(Carrier.id == p.carrier_id).first()
            if not carrier:
                continue
            data = self.research_lane(carrier.slug, p.origin_country, p.dest_country)
            if data and data.get("label"):
                db = SessionLocal()
                try:
                    pat = db.query(RoutePattern).filter(RoutePattern.id == p.id).first()
                    if pat:
                        pat.label = data["label"]
                        pat.updated_at = utcnow()
                        db.commit()
                        enriched += 1
                finally:
                    db.close()

        return {"enriched": enriched, "skipped": len(patterns) - enriched}

    def fill_missing_lanes(self, db_session=None):
        """Research lanes that have no route patterns yet.

        Finds carriers with active shipments that lack patterns, and
        researches the most common missing lanes.
        """
        if not self.available:
            return {"researched": 0}

        close_session = db_session is None
        db = db_session or SessionLocal()
        try:
            from sqlalchemy import text
            rows = db.execute(
                text("""
                    SELECT DISTINCT c.slug, c.id as carrier_id,
                           country_from_region(s.origin_name) as oc,
                           country_from_region(s.dest_name) as dc
                    FROM shipments s
                    JOIN carriers c ON c.id = s.carrier_id
                    WHERE s.delivered_at IS NULL
                      AND NOT EXISTS (
                          SELECT 1 FROM route_patterns rp
                          WHERE rp.carrier_id = c.id
                            AND rp.origin_country = country_from_region(s.origin_name)
                            AND rp.dest_country = country_from_region(s.dest_name)
                      )
                    LIMIT 20
                """)
            ).fetchall()
        finally:
            if close_session:
                db.close()

        researched = 0
        for row in rows:
            result = self.research_and_store(row.slug, row.oc, row.dc)
            if result.get("created"):
                researched += 1

        logger.info(f"Researched {researched} missing lanes")
        return {"researched": researched}
