import { describe, expect, it } from "vitest";
import { normalizeLongitude, splitRouteAtAntimeridian } from "./geo";

describe("normalizeLongitude", () => {
  it("keeps longitudes in the standard world range", () => {
    expect(normalizeLongitude(190)).toBe(-170);
    expect(normalizeLongitude(-190)).toBe(170);
    expect(normalizeLongitude(180)).toBe(180);
  });
});

describe("splitRouteAtAntimeridian", () => {
  it("splits eastbound Pacific routes instead of drawing through Europe", () => {
    const segments = splitRouteAtAntimeridian([
      [35.68, 139.76],
      [34.05, -118.24],
    ]);

    expect(segments).toHaveLength(2);
    expect(segments[0][1][1]).toBe(180);
    expect(segments[1][0][1]).toBe(-180);
    expect(segments[1][1]).toEqual([34.05, -118.24]);
  });

  it("splits westbound Pacific routes at the opposite edge", () => {
    const segments = splitRouteAtAntimeridian([
      [34.05, -118.24],
      [35.68, 139.76],
    ]);

    expect(segments).toHaveLength(2);
    expect(segments[0][1][1]).toBe(-180);
    expect(segments[1][0][1]).toBe(180);
  });

  it("does not split ordinary domestic routes", () => {
    expect(splitRouteAtAntimeridian([
      [41.88, -87.63],
      [27.91, -82.79],
    ])).toEqual([[
      [41.88, -87.63],
      [27.91, -82.79],
    ]]);
  });
});
