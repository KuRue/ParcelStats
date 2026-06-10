import { beforeEach, describe, expect, it, vi } from "vitest";

const incr = vi.fn();
const expire = vi.fn();

vi.mock("@/lib/redis", () => ({
  getRedisPub: () => ({ incr, expire }),
}));

import { rateLimit, clientIp } from "./rate-limit";

describe("rateLimit", () => {
  beforeEach(() => {
    incr.mockReset();
    expire.mockReset();
  });

  it("allows requests under the limit", async () => {
    incr.mockResolvedValue(1);
    const result = await rateLimit({ action: "t", key: "u1", limit: 5, windowSeconds: 60 });
    expect(result).toBeNull();
    expect(expire).toHaveBeenCalled();
  });

  it("blocks requests over the limit with 429", async () => {
    incr.mockResolvedValue(6);
    const result = await rateLimit({ action: "t", key: "u1", limit: 5, windowSeconds: 60 });
    expect(result).not.toBeNull();
    expect(result!.status).toBe(429);
    expect(result!.headers.get("Retry-After")).toBe("60");
  });

  it("fails open when redis errors", async () => {
    incr.mockRejectedValue(new Error("redis down"));
    const result = await rateLimit({ action: "t", key: "u1", limit: 5, windowSeconds: 60 });
    expect(result).toBeNull();
  });
});

describe("clientIp", () => {
  it("uses the first x-forwarded-for entry", () => {
    const req = new Request("http://x", {
      headers: { "x-forwarded-for": "1.2.3.4, 5.6.7.8" },
    });
    expect(clientIp(req)).toBe("1.2.3.4");
  });

  it("falls back to x-real-ip then unknown", () => {
    expect(clientIp(new Request("http://x", { headers: { "x-real-ip": "9.9.9.9" } }))).toBe("9.9.9.9");
    expect(clientIp(new Request("http://x"))).toBe("unknown");
  });
});
