import json
import time
from datetime import datetime, timedelta
from typing import Optional
import redis
from services.config import settings


class JobQueue:
    QUEUE_KEY = "parcelstats:scrape:queue"
    PROCESSING_KEY = "parcelstats:scrape:processing"
    RATE_LIMIT_PREFIX = "parcelstats:ratelimit:"
    MAX_RETRIES = 3
    RETRY_DELAYS = [60, 300, 900]
    CARRIER_RATE_LIMITS = {
        "usps": 30,
        "ups": 30,
        "fedex": 30,
        "dhl-express": 30,
        "default": 60,
    }

    def __init__(self):
        self.redis = redis.from_url(settings.redis_url, decode_responses=True)

    def enqueue(
        self,
        tracking_number: str,
        carrier_slug: str,
        shipment_id: str,
        priority: int = 0,
    ) -> str:
        job = {
            "tracking_number": tracking_number,
            "carrier_slug": carrier_slug,
            "shipment_id": shipment_id,
            "attempts": 0,
            "enqueued_at": datetime.utcnow().isoformat(),
            "priority": priority,
        }
        job_data = json.dumps(job)
        self.redis.zadd(self.QUEUE_KEY, {job_data: -priority})
        return f"{carrier_slug}:{tracking_number}"

    def dequeue(self, timeout: int = 5) -> Optional[dict]:
        carriers = self.CARRIER_RATE_LIMITS.keys()
        now = time.time()

        all_jobs = self.redis.zrange(self.QUEUE_KEY, 0, -1, withscores=True)
        if not all_jobs:
            return None

        for job_data, score in all_jobs:
            job = json.loads(job_data)
            carrier = job.get("carrier_slug", "default")

            rate_limit_key = f"{self.RATE_LIMIT_PREFIX}{carrier}"
            last_request = self.redis.get(rate_limit_key)
            if last_request:
                limit = self.CARRIER_RATE_LIMITS.get(
                    carrier, self.CARRIER_RATE_LIMITS["default"]
                )
                if now - float(last_request) < limit:
                    continue

            self.redis.zrem(self.QUEUE_KEY, job_data)
            self.redis.set(rate_limit_key, str(now), ex=3600)
            job["attempts"] = job.get("attempts", 0) + 1
            return job

        return None

    def requeue_failed(self, job: dict, error: str):
        attempts = job.get("attempts", 1)
        if attempts > self.MAX_RETRIES:
            return False

        delay = self.RETRY_DELAYS[min(attempts - 1, len(self.RETRY_DELAYS) - 1)]
        retry_at = datetime.utcnow() + timedelta(seconds=delay)

        job["last_error"] = error
        job["retry_at"] = retry_at.isoformat()
        job_data = json.dumps(job)

        self.redis.zadd(self.QUEUE_KEY, {job_data: -(100 - attempts)})
        return True

    def get_queue_size(self) -> int:
        return self.redis.zcard(self.QUEUE_KEY)

    def get_pending_count(self) -> int:
        return self.redis.zcard(self.QUEUE_KEY)

    def clear_stale_processing(self, max_age_seconds: int = 3600):
        self.redis.zremrangebyscore(
            self.PROCESSING_KEY, "-inf", time.time() - max_age_seconds
        )

    def get_stats(self) -> dict:
        return {
            "queue_size": self.redis.zcard(self.QUEUE_KEY),
            "processing": self.redis.zcard(self.PROCESSING_KEY),
        }
