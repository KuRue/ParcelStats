export type LatLngTuple = [number, number];

function roundCoordinate(value: number): number {
  return Math.round(value * 1_000_000_000_000) / 1_000_000_000_000;
}

export function normalizeLongitude(lng: number): number {
  if (!Number.isFinite(lng)) return lng;
  const normalized = ((((lng + 180) % 360) + 360) % 360) - 180;
  return normalized === -180 && lng > 0 ? 180 : roundCoordinate(normalized);
}

export function longitudeNear(lng: number, referenceLng: number): number {
  if (!Number.isFinite(lng) || !Number.isFinite(referenceLng)) return lng;
  const normalized = normalizeLongitude(lng);
  const worldOffset = Math.round((referenceLng - normalized) / 360) * 360;
  return roundCoordinate(normalized + worldOffset);
}

export function unwrapRouteLongitudes(points: LatLngTuple[], anchorLng?: number): LatLngTuple[] {
  if (points.length === 0) return [];

  const firstLng =
    anchorLng == null
      ? normalizeLongitude(points[0][1])
      : longitudeNear(points[0][1], anchorLng);
  const unwrapped: LatLngTuple[] = [[points[0][0], firstLng]];

  for (let i = 1; i < points.length; i += 1) {
    const previousLng = unwrapped[i - 1][1];
    unwrapped.push([points[i][0], longitudeNear(points[i][1], previousLng)]);
  }

  return unwrapped;
}

export function splitRouteAtAntimeridian(points: LatLngTuple[]): LatLngTuple[][] {
  if (points.length <= 1) return points.length ? [[points[0]]] : [];

  const normalized = points.map(([lat, lng]) => [lat, normalizeLongitude(lng)] as LatLngTuple);
  const segments: LatLngTuple[][] = [[normalized[0]]];

  for (let i = 1; i < normalized.length; i += 1) {
    const previous = normalized[i - 1];
    const next = normalized[i];
    const diff = next[1] - previous[1];
    const current = segments[segments.length - 1];

    if (Math.abs(diff) <= 180) {
      current.push(next);
      continue;
    }

    const crossingLng = diff < -180 ? 180 : -180;
    const unwrappedNextLng = diff < -180 ? next[1] + 360 : next[1] - 360;
    const ratio = (crossingLng - previous[1]) / (unwrappedNextLng - previous[1]);
    const crossingLat = roundCoordinate(previous[0] + (next[0] - previous[0]) * ratio);

    current.push([crossingLat, crossingLng]);
    segments.push([[crossingLat, -crossingLng], next]);
  }

  return segments.filter((segment) => segment.length > 0);
}
