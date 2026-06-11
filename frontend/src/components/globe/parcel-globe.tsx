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
  originName: string | null;
  destName: string | null;
  lastLocation: string | null;
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

interface PlaceLabel {
  shipmentId: string;
  lat: number;
  lng: number;
  text: string;
  kind: "current" | "origin" | "dest";
  color: string;
}

/** "Chicago IL, US" -> "Chicago IL"; "SHENZHEN, China" -> "SHENZHEN" */
function placeName(location: string | null): string | null {
  if (!location) return null;
  const name = location.split(",")[0].trim();
  return name.length > 1 ? name : null;
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

  const { arcs, points, rings, labels } = useMemo(() => {
    const arcs: Arc[] = [];
    const points: Point[] = [];
    const rings: Ring[] = [];
    const labels: PlaceLabel[] = [];
    const labelSpots = new Set<string>();

    const addLabel = (label: PlaceLabel) => {
      // One label per ~half-degree cell to keep shared hubs readable
      const key = `${Math.round(label.lat * 2)}:${Math.round(label.lng * 2)}`;
      if (labelSpots.has(key)) return;
      labelSpots.add(key);
      labels.push(label);
    };

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
        const currentName = placeName(s.lastLocation) ?? (delivered ? placeName(s.destName) : null);
        if (currentName) {
          addLabel({
            shipmentId: s.id,
            lat: current[0],
            lng: current[1],
            text: currentName,
            kind: "current",
            color,
          });
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
        const destLabel = placeName(s.destName);
        if (destLabel) {
          addLabel({
            shipmentId: s.id,
            lat: dest[0],
            lng: dest[1],
            text: destLabel,
            kind: "dest",
            color: COLORS.pending,
          });
        }
      }
      if (origin) {
        const originLabel = placeName(s.originName);
        if (originLabel) {
          addLabel({
            shipmentId: s.id,
            lat: origin[0],
            lng: origin[1],
            text: originLabel,
            kind: "origin",
            color: "#7a8599",
          });
        }
      }
    }
    return { arcs, points, rings, labels };
  }, [shipments]);

  const visibleLabels = useMemo(() => {
    if (selectedId) {
      return labels.filter((l) => l.shipmentId === selectedId);
    }
    // Unselected view: show where parcels are now, plus destinations when
    // there are few enough parcels for it to stay readable.
    return labels.filter(
      (l) => l.kind === "current" || (l.kind === "dest" && shipments.length <= 8)
    );
  }, [labels, selectedId, shipments.length]);

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
          polygonsData={land}
          polygonCapColor={() => "rgba(0,180,200,0.13)"}
          polygonSideColor={() => "rgba(0,0,0,0)"}
          polygonStrokeColor={() => "rgba(0,240,255,0.30)"}
          polygonAltitude={0.004}
          polygonsTransitionDuration={0}
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
          labelsData={visibleLabels}
          labelLat={(l: object) => (l as PlaceLabel).lat}
          labelLng={(l: object) => (l as PlaceLabel).lng}
          labelText={(l: object) => (l as PlaceLabel).text}
          labelSize={(l: object) => {
            const label = l as PlaceLabel;
            if (selectedId && label.shipmentId === selectedId) return 1.05;
            return label.kind === "current" ? 0.85 : 0.7;
          }}
          labelColor={(l: object) => {
            const label = l as PlaceLabel;
            const alpha = label.kind === "current" ? 0.9 : 0.65;
            return withAlpha(label.color, alpha);
          }}
          labelDotRadius={0.18}
          labelAltitude={0.012}
          labelResolution={2}
          labelsTransitionDuration={400}
          onLabelClick={(l: object) => onSelect((l as PlaceLabel).shipmentId)}
          onGlobeClick={() => onSelect(null)}
          rendererConfig={{ antialias: true, alpha: true }}
        />
      )}
    </div>
  );
}
