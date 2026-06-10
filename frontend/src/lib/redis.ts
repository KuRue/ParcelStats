import Redis from "ioredis";

const REDIS_URL = process.env.REDIS_URL || "redis://redis:6379";

let _pub: Redis | null = null;
let _sub: Redis | null = null;

export function getRedisPub(): Redis {
  if (!_pub) {
    _pub = new Redis(REDIS_URL, { maxRetriesPerRequest: 3 });
  }
  return _pub;
}

export function getRedisSub(): Redis {
  if (!_sub) {
    _sub = new Redis(REDIS_URL, { maxRetriesPerRequest: null });
  }
  return _sub;
}

export interface LiveEvent {
  type: "shipment_updated" | "prediction_updated" | "scrape_completed" | "stats_updated";
  shipment_id: string;
  tracking_number: string;
  carrier_slug: string;
  status?: string;
  user_id?: string;
  data?: Record<string, unknown>;
  timestamp: string;
}

export function publishEvent(channel: string, event: LiveEvent) {
  const redis = getRedisPub();
  return redis.publish(channel, JSON.stringify(event));
}

export function userChannel(userId: string) {
  return `parcelstats:user:${userId}`;
}

export const globalChannel = "parcelstats:global";
