import { describe, expect, it } from "vitest";
import {
  longitudeNear,
  normalizeLongitude,
  splitRouteAtAntimeridian,
  unwrapRouteLongitudes,
} from "./geo";

describe("normalizeLongitude", () => {
  it("keeps longitudes in the standard world range", () => {
    expect(normalizeLongitude(190)).toBe(-170);
    expect(normalizeLongitude(-190)).toBe(170);
    expect(normalizeLongitude(180)).toBe(180);
  });
});

describe("longitudeNear", () => {
  it("moves a longitude into the nearest wrapped world", () => {
    expect(longitudeNear(-118.24, 139.76)).toBe(241.76);
    expect(longitudeNear(139.76, -118.24)).toBe(-220.24);
  });
});

describe("unwrapRouteLongitudes", () => {
  it("keeps Pacific routes continuous in the eastbound direction", () => {
    expect(unwrapRouteLongitudes([
      [35.68, 139.76],
      [34.05, -118.24],
    ])).toEqual([
      [35.68, 139.76],
      [34.05, 241.76],
    ]);
  });

  it("keeps Pacific routes continuous in the westbound direction", () => {
    expect(unwrapRouteLongitudes([
      [34.05, -118.24],
      [35.68, 139.76],
    ])).toEqual([
      [34.05, -118.24],
      [35.68, -220.24],
    ]);
  });

  it("can anchor a follow-on segment to an already unwrapped point", () => {
    expect(unwrapRouteLongitudes([
      [34.05, -118.24],
      [27.91, -82.79],
    ], 241.76)).toEqual([
      [34.05, 241.76],
      [27.91, 277.21],
    ]);
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
