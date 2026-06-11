"use client";

import { useState, useEffect, useRef, useMemo, useCallback } from "react";
import Globe, { GlobeMethods } from "react-globe.gl";
import * as THREE from "three";

export interface GlobeShipment {
  id: string;
  trackingNumber: string;
  status: string;
  carrierName: string;
  originLat: string | null;
  originLng: string | null;
  destLat: string | null;
  destLng: string | null;
  lastLat: string | null;
  lastLng: string | null;
  path: [number, number][];
}

interface ParcelGlobeProps {
  shipments: GlobeShipment[];
  selectedId: string | null;
  onSelect: (id: string | null) => void;
}

const COLORS = {
  traveled: "#00f0ff",
  predicted: "#bf00ff",
  delivered: "#39ff14",
  issue: "#ff003c",
  pending: "#ffdd00",
};

function isIssue(status: string) {
  const s = status.toLowerCase();
  return (
    s.includes("exception") ||
    s.includes("fail") ||
    s.includes("error") ||
    s.includes("required") ||
    s.includes("not_found") ||
    s.includes("blocked")
  );
}

function isDelivered(status: string) {
  return status.toLowerCase().includes("deliver") && !isIssue(status);
}

function statusColor(status: string): string {
  if (isDelivered(status)) return COLORS.delivered;
  if (isIssue(status)) return COLORS.issue;
  return COLORS.traveled;
}

function num(value: string | null): number | null {
  if (value == null) return null;
  const n = parseFloat(value);
  return Number.isFinite(n) ? n : null;
}

function withAlpha(hex: string, alpha: number): string {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return `rgba(${r},${g},${b},${alpha})`;
}

interface Arc {
  shipmentId: string;
  startLat: number;
  startLng: number;
  endLat: number;
  endLng: number;
  kind: "traveled" | "predicted" | "delivered";
}

interface Point {
  shipmentId: string;
  lat: number;
  lng: number;
  kind: "current" | "origin" | "dest";
  color: string;
}

interface Ring {
  shipmentId: string;
  lat: number;
  lng: number;
  color: string;
}

/** Resolve a shipment's known journey into globe coordinates. */
function journeyOf(s: GlobeShipment) {
  const origin =
    num(s.originLat) != null && num(s.originLng) != null
      ? ([num(s.originLat)!, num(s.originLng)!] as [number, number])
      : null;
  const dest =
    num(s.destLat) != null && num(s.destLng) != null
      ? ([num(s.destLat)!, num(s.destLng)!] as [number, number])
      : null;

  // Trail: origin + event path, deduping points that are basically the same place
  const raw: [number, number][] = [];
  if (origin) raw.push(origin);
  for (const p of s.path ?? []) {
    if (Array.isArray(p) && Number.isFinite(p[0]) && Number.isFinite(p[1])) {
      raw.push([p[0], p[1]]);
    }
  }
  const last = num(s.lastLat) != null && num(s.lastLng) != null
    ? ([num(s.lastLat)!, num(s.lastLng)!] as [number, number])
    : null;
  if (last) raw.push(last);

  const trail: [number, number][] = [];
  for (const p of raw) {
    const prev = trail[trail.length - 1];
    if (!prev || Math.abs(prev[0] - p[0]) > 0.05 || Math.abs(prev[1] - p[1]) > 0.05) {
      trail.push(p);
    }
  }

  const current = trail[trail.length - 1] ?? null;
  return { origin, dest, trail, current };
}

export default function ParcelGlobe({ shipments, selectedId, onSelect }: ParcelGlobeProps) {
  const globeRef = useRef<GlobeMethods | undefined>(undefined);
  const containerRef = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ width: 0, height: 0 });
  const [land, setLand] = useState<object[]>([]);

  useEffect(() => {
    fetch("/geo/land-110m.json")
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => d?.features && setLand(d.features))
      .catch(() => {});
  }, []);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const observer = new ResizeObserver((entries) => {
      const { width, height } = entries[0].contentRect;
      setSize({ width, height });
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  const globeMaterial = useMemo(
    () =>
      new THREE.MeshPhongMaterial({
        color: "#0d1424",
        transparent: true,
        opacity: 0.96,
      }),
    []
  );

  const { arcs, points, rings } = useMemo(() => {
    const arcs: Arc[] = [];
    const points: Point[] = [];
    const rings: Ring[] = [];

    for (const s of shipments) {
      const { origin, dest, trail, current } = journeyOf(s);
      const delivered = isDelivered(s.status);
      const color = statusColor(s.status);

      for (let i = 0; i < trail.length - 1; i++) {
        arcs.push({
          shipmentId: s.id,
          startLat: trail[i][0],
          startLng: trail[i][1],
          endLat: trail[i + 1][0],
          endLng: trail[i + 1][1],
          kind: delivered ? "delivered" : "traveled",
        });
      }

      if (current && dest && !delivered) {
        const atDest =
          Math.abs(current[0] - dest[0]) < 0.05 &&
          Math.abs(current[1] - dest[1]) < 0.05;
        if (!atDest) {
          arcs.push({
            shipmentId: s.id,
            startLat: current[0],
            startLng: current[1],
            endLat: dest[0],
            endLng: dest[1],
            kind: "predicted",
          });
        }
      }
      // Delivered with no recorded trail: show the completed journey
      if (delivered && trail.length < 2 && origin && dest) {
        arcs.push({
          shipmentId: s.id,
          startLat: origin[0],
          startLng: origin[1],
          endLat: dest[0],
          endLng: dest[1],
          kind: "delivered",
        });
      }

      if (current) {
        points.push({ shipmentId: s.id, lat: current[0], lng: current[1], kind: "current", color });
        if (!delivered) {
          rings.push({ shipmentId: s.id, lat: current[0], lng: current[1], color });
        }
      }
      if (dest && !delivered) {
        points.push({
          shipmentId: s.id,
          lat: dest[0],
          lng: dest[1],
          kind: "dest",
          color: COLORS.pending,
        });
      }
    }
    return { arcs, points, rings };
  }, [shipments]);

  const arcColor = useCallback(
    (a: object) => {
      const arc = a as Arc;
      const base =
        arc.kind === "predicted"
          ? COLORS.predicted
          : arc.kind === "delivered"
          ? COLORS.delivered
          : COLORS.traveled;
      if (selectedId && arc.shipmentId !== selectedId) return withAlpha(base, 0.12);
      return withAlpha(base, arc.kind === "predicted" ? 0.85 : 0.7);
    },
    [selectedId]
  );

  // Auto-rotate while nothing is selected
  useEffect(() => {
    const globe = globeRef.current;
    if (!globe) return;
    const controls = globe.controls();
    controls.autoRotate = !selectedId;
    controls.autoRotateSpeed = 0.55;
    controls.enablePan = false;
  }, [selectedId, size.width]);

  // Fly to the selected parcel
  useEffect(() => {
    if (!selectedId) return;
    const s = shipments.find((x) => x.id === selectedId);
    if (!s) return;
    const { current, dest, origin } = journeyOf(s);
    const target = current ?? dest ?? origin;
    if (target) {
      globeRef.current?.pointOfView({ lat: target[0], lng: target[1], altitude: 1.7 }, 900);
    }
  }, [selectedId, shipments]);

  return (
    <div ref={containerRef} className="absolute inset-0 overflow-hidden">
      {size.width > 0 && (
        <Globe
          ref={globeRef}
          width={size.width}
          height={size.height}
          backgroundColor="rgba(0,0,0,0)"
          globeMaterial={globeMaterial}
          showAtmosphere
          atmosphereColor="#00f0ff"
          atmosphereAltitude={0.16}
          hexPolygonsData={land}
          hexPolygonResolution={3}
          hexPolygonMargin={0.62}
          hexPolygonUseDots
          hexPolygonColor={() => "rgba(0,240,255,0.28)"}
          arcsData={arcs}
          arcColor={arcColor}
          arcStroke={(a: object) =>
            selectedId && (a as Arc).shipmentId === selectedId ? 0.85 : 0.45
          }
          arcAltitudeAutoScale={0.42}
          arcDashLength={(a: object) => ((a as Arc).kind === "predicted" ? 0.35 : 1)}
          arcDashGap={(a: object) => ((a as Arc).kind === "predicted" ? 0.18 : 0)}
          arcDashAnimateTime={(a: object) =>
            (a as Arc).kind === "predicted" ? 1600 : 0
          }
          arcsTransitionDuration={500}
          onArcClick={(a: object) => onSelect((a as Arc).shipmentId)}
          pointsData={points}
          pointLat={(p: object) => (p as Point).lat}
          pointLng={(p: object) => (p as Point).lng}
          pointColor={(p: object) => {
            const pt = p as Point;
            const alpha =
              selectedId && pt.shipmentId !== selectedId
                ? 0.15
                : pt.kind === "dest"
                ? 0.55
                : 0.95;
            return withAlpha(pt.color, alpha);
          }}
          pointAltitude={0.005}
          pointRadius={(p: object) => ((p as Point).kind === "current" ? 0.45 : 0.28)}
          onPointClick={(p: object) => onSelect((p as Point).shipmentId)}
          ringsData={rings}
          ringLat={(r: object) => (r as Ring).lat}
          ringLng={(r: object) => (r as Ring).lng}
          ringColor={(r: object) => {
            const ring = r as Ring;
            const dim = selectedId && ring.shipmentId !== selectedId;
            return (t: number) => withAlpha(ring.color, (dim ? 0.15 : 0.65) * (1 - t));
          }}
          ringMaxRadius={3.2}
          ringPropagationSpeed={1.6}
          ringRepeatPeriod={1100}
          onGlobeClick={() => onSelect(null)}
          rendererConfig={{ antialias: true, alpha: true }}
        />
      )}
    </div>
  );
}
