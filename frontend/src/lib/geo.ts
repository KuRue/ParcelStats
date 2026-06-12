export type LatLngTuple = [number, number];

function roundCoordinate(value: number): number {
  return Math.round(value * 1_000_000_000_000) / 1_000_000_000_000;
}

export function normalizeLongitude(lng: number): number {
  if (!Number.isFinite(lng)) return lng;
  const normalized = ((((lng + 180) % 360) + 360) % 360) - 180;
  return normalized === -180 && lng > 0 ? 180 : roundCoordinate(normalized);
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
