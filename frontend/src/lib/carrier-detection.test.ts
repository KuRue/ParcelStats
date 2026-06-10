import { describe, expect, it } from "vitest";
import { detectCarrierSlug, normalizeTrackingNumber } from "./carrier-detection";

describe("normalizeTrackingNumber", () => {
  it("strips whitespace and uppercases", () => {
    expect(normalizeTrackingNumber(" 1z 999aa 10123456784 ")).toBe("1Z999AA10123456784");
  });
});

describe("detectCarrierSlug", () => {
  it("detects UPS", () => {
    expect(detectCarrierSlug("1Z999AA10123456784")).toBe("ups");
  });

  it("detects USPS S10 format", () => {
    expect(detectCarrierSlug("LZ123456789US")).toBe("usps");
  });

  it("detects USPS IMpb format", () => {
    expect(detectCarrierSlug("9400111899223100000000")).toBe("usps");
  });

  it("detects SpeedPAK", () => {
    expect(detectCarrierSlug("EE12345678901234567890")).toBe("speedpak");
  });

  it("detects DHL Express", () => {
    expect(detectCarrierSlug("1234567890")).toBe("dhl-express");
  });

  it("detects FedEx 12-digit", () => {
    expect(detectCarrierSlug("123456789012")).toBe("fedex");
  });

  it("returns null for unknown formats", () => {
    expect(detectCarrierSlug("not-a-tracking-number")).toBeNull();
    expect(detectCarrierSlug("")).toBeNull();
  });
});
