import { NextResponse } from "next/server";
import { getRedisPub } from "@/lib/redis";

interface RateLimitOptions {
  /** Unique name of the action being limited, e.g. "register" */
  action: string;
  /** Who is performing it: user id or client IP */
  key: string;
  /** Max requests allowed per window */
  limit: number;
  /** Window length in seconds */
  windowSeconds: number;
}

/**
 * Fixed-window rate limiter backed by Redis. Returns null when allowed,
 * or a ready-to-return 429 response when the limit is exceeded.
 * Fails open if Redis is unavailable.
 */
export async function rateLimit(
  opts: RateLimitOptions
): Promise<NextResponse | null> {
  try {
    const redis = getRedisPub();
    const windowId = Math.floor(Date.now() / 1000 / opts.windowSeconds);
    const redisKey = `ratelimit:${opts.action}:${opts.key}:${windowId}`;

    const count = await redis.incr(redisKey);
    if (count === 1) {
      await redis.expire(redisKey, opts.windowSeconds);
    }

    if (count > opts.limit) {
      return NextResponse.json(
        { error: "Too many requests, please slow down" },
        {
          status: 429,
          headers: { "Retry-After": String(opts.windowSeconds) },
        }
      );
    }
    return null;
  } catch (error) {
    console.error("Rate limit check failed (allowing request):", error);
    return null;
  }
}

export function clientIp(request: Request): string {
  const forwarded = request.headers.get("x-forwarded-for");
  if (forwarded) return forwarded.split(",")[0].trim();
  return request.headers.get("x-real-ip") || "unknown";
}
