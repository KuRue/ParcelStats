"use client";

import { useEffect, useRef } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { normalizeLongitude, unwrapRouteLongitudes, type LatLngTuple } from "@/lib/geo";
import {
  formatRegionalDateHour,
  formatStatusLabel,
  isDeliveredStatus,
  isIssueStatus,
  normalizedStatus,
} from "@/lib/utils";

interface MapEvent {
  status: string;
  locationName: string | null;
  locationLat: number | null;
  locationLng: number | null;
  description: string | null;
  eventTime: string;
}

interface FutureStop {
  stopOrder: number;
  locationName: string;
  locationLat: number | null;
  locationLng: number | null;
  status: string;
  frequencyPct: number;
  eta: string;
}

interface FlightPosition {
  icao24: string;
  callsign: string;
  latitude: number;
  longitude: number;
  altitude: number | null;
  velocity: number | null;
  heading: number | null;
  on_ground: boolean;
  origin_country: string;
  distance_to_origin_km?: number;
  distance_to_dest_km?: number;
}

interface ShipmentRouteMapProps {
  events: MapEvent[];
  originLat?: number | null;
  originLng?: number | null;
  originName?: string | null;
  destLat?: number | null;
  destLng?: number | null;
  destName?: string | null;
  status: string;
  futureStops?: FutureStop[];
  flights?: FlightPosition[];
}

function createIcon(color: string, size: number = 12) {
  return L.divIcon({
    className: "custom-marker",
    html: `<div style="
      width:${size}px;
      height:${size}px;
      background:${color};
      border:2px solid ${color};
      border-radius:50%;
      box-shadow:0 0 8px ${color}80, 0 0 20px ${color}40;
    "></div>`,
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2],
  });
}

function createPulseIcon(color: string) {
  return L.divIcon({
    className: "custom-marker",
    html: `<div style="position:relative;width:16px;height:16px;">
      <div style="
        width:16px;height:16px;
        background:${color};
        border:2px solid ${color};
        border-radius:50%;
        box-shadow:0 0 12px ${color}80, 0 0 30px ${color}40;
        animation:pulse 2s ease-in-out infinite;
      "></div>
      <div style="
        position:absolute;top:-4px;left:-4px;
        width:24px;height:24px;
        border:2px solid ${color}40;
        border-radius:50%;
        animation:pulse 2s ease-in-out infinite;
      "></div>
    </div>`,
    iconSize: [16, 16],
    iconAnchor: [8, 8],
  });
}

function createGhostIcon(color: string) {
  return L.divIcon({
    className: "custom-marker",
    html: `<div style="
      width:12px;
      height:12px;
      background:${color}22;
      border:2px dashed ${color};
      border-radius:50%;
      box-shadow:0 0 8px ${color}50;
    "></div>`,
    iconSize: [12, 12],
    iconAnchor: [6, 6],
  });
}

function createEndpointIcon(label: string, color: string) {
  return L.divIcon({
    className: "custom-marker",
    html: `<div style="
      display:flex;flex-direction:column;align-items:center;
      font-family:'JetBrains Mono',monospace;
    ">
      <div style="
        width:20px;height:20px;
        background:${color}20;
        border:2px solid ${color};
        border-radius:50%;
        box-shadow:0 0 12px ${color}60;
        display:flex;align-items:center;justify-content:center;
        font-size:10px;color:${color};font-weight:bold;
      ">${label}</div>
    </div>`,
    iconSize: [20, 20],
    iconAnchor: [10, 10],
  });
}

function createPlaneIcon(heading: number, callsign: string) {
  return L.divIcon({
    className: "custom-marker",
    html: `<div style="
      transform:rotate(${heading}deg);
      width:28px;height:28px;
      display:flex;align-items:center;justify-content:center;
    ">
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" style="filter:drop-shadow(0 0 4px #ffdd0080);">
        <path d="M21 16v-2l-8-5V3.5C13 2.67 12.33 2 11.5 2S10 2.67 10 3.5V9l-8 5v2l8-2.5V19l-2 1.5V22l3.5-1 3.5 1v-1.5L13 19v-5.5l8 2.5z"
          fill="#ffdd00" stroke="#1a1f2e" stroke-width="0.5"/>
      </svg>
    </div>`,
    iconSize: [28, 28],
    iconAnchor: [14, 14],
  });
}

function getStatusColor(status: string): string {
  const s = normalizedStatus(status);
  if (isDeliveredStatus(status)) return "#39ff14";
  if (s.includes("out for delivery")) return "#bf00ff";
  if (s.includes("transit")) return "#00f0ff";
  if (s.includes("custom")) return "#ffdd00";
  if (isIssueStatus(status)) return "#ff003c";
  if (s.includes("arrived") || s.includes("departed")) return "#00f0ff";
  return "#7a8599";
}

function eventTimestamp(event: MapEvent): number {
  const timestamp = new Date(event.eventTime).getTime();
  return Number.isFinite(timestamp) ? timestamp : 0;
}

function dedupeConsecutivePoints(routeCoords: LatLngTuple[]): LatLngTuple[] {
  return routeCoords.filter((point, index) => {
    const previous = routeCoords[index - 1];
    return !previous || Math.abs(previous[0] - point[0]) >= 0.0001 || Math.abs(previous[1] - point[1]) >= 0.0001;
  });
}

function addPolyline(
  map: L.Map,
  routeCoords: LatLngTuple[],
  options: L.PolylineOptions
) {
  const deduped = dedupeConsecutivePoints(routeCoords);
  if (deduped.length > 1) {
    L.polyline(deduped, options).addTo(map);
  }
}

export function ShipmentRouteMap({
  events,
  originLat,
  originLng,
  originName,
  destLat,
  destLng,
  destName,
  status,
  futureStops,
  flights,
}: ShipmentRouteMapProps) {
  const mapRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<L.Map | null>(null);

  useEffect(() => {
    if (!mapRef.current || mapInstanceRef.current) return;

    const map = L.map(mapRef.current, {
      center: [20, 0],
      zoom: 2,
      zoomControl: false,
      attributionControl: false,
      maxBoundsViscosity: 1,
    });

    L.tileLayer(
      "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
      {
        maxZoom: 18,
        subdomains: "abcd",
      }
    ).addTo(map);

    L.control
      .zoom({ position: "bottomright" })
      .addTo(map);

    L.control
      .attribution({ position: "bottomleft", prefix: false })
      .addAttribution("&copy; <a href='https://carto.com/' style='color:#7a8599'>CARTO</a>")
      .addTo(map);

    mapInstanceRef.current = map;

    return () => {
      map.remove();
      mapInstanceRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapInstanceRef.current;
    if (!map) return;

    map.eachLayer((layer) => {
      if (layer instanceof L.TileLayer) return;
      map.removeLayer(layer);
    });

    const points: LatLngTuple[] = [];
    const geoEvents = events.filter(
      (e) => e.locationLat != null && e.locationLng != null
    );
    const routeEvents = [...geoEvents].sort(
      (a, b) => eventTimestamp(a) - eventTimestamp(b)
    );
    const actualRouteRaw: LatLngTuple[] = [];
    const eventDisplayPoints = new Map<MapEvent, LatLngTuple>();

    if (originLat != null && originLng != null) {
      actualRouteRaw.push([originLat, originLng]);
    }

    routeEvents.forEach((event) => {
      actualRouteRaw.push([event.locationLat!, event.locationLng!]);
    });

    const actualRouteDisplay = unwrapRouteLongitudes(actualRouteRaw);
    let actualRouteIndex = 0;
    const originPoint =
      originLat != null && originLng != null
        ? actualRouteDisplay[actualRouteIndex++] ?? [originLat, normalizeLongitude(originLng)]
        : null;

    routeEvents.forEach((event) => {
      eventDisplayPoints.set(
        event,
        actualRouteDisplay[actualRouteIndex++] ?? [
          event.locationLat!,
          normalizeLongitude(event.locationLng!),
        ]
      );
    });

    if (originPoint) {
      const originMarker = L.marker(originPoint, {
        icon: createEndpointIcon("O", "#bf00ff"),
      }).addTo(map);
      originMarker.bindPopup(
        `<div style="font-family:'JetBrains Mono',monospace;font-size:12px;color:#e0e6f0;background:#1a1f2e;padding:8px;border:1px solid #2a3040;border-radius:6px;">
          <div style="color:#bf00ff;font-weight:bold;margin-bottom:4px;">ORIGIN</div>
          <div>${originName || "Unknown"}</div>
        </div>`,
        { className: "cyber-popup" }
      );
      points.push(originPoint);
    }

    if (geoEvents.length > 0) {
      geoEvents.forEach((event, i) => {
        const lat = event.locationLat!;
        const point = eventDisplayPoints.get(event) ?? [
          lat,
          normalizeLongitude(event.locationLng!),
        ];
        points.push(point);

        const isLatest = i === 0;
        const color = getStatusColor(event.status);

        const marker = L.marker(point, {
          icon: isLatest ? createPulseIcon(color) : createIcon(color),
        }).addTo(map);

        const time = formatRegionalDateHour(event.eventTime);

        marker.bindPopup(
          `<div style="font-family:'JetBrains Mono',monospace;font-size:11px;color:#e0e6f0;background:#1a1f2e;padding:10px;border:1px solid #2a3040;border-radius:6px;min-width:180px;">
            <div style="color:${color};font-weight:bold;margin-bottom:4px;font-size:10px;letter-spacing:1px;">${formatStatusLabel(event.status)}</div>
            ${event.locationName ? `<div style="margin-bottom:4px;">${event.locationName}</div>` : ""}
            ${event.description ? `<div style="color:#7a8599;margin-bottom:4px;">${event.description}</div>` : ""}
            ${time ? `<div style="color:#7a8599;font-size:10px;">${time}</div>` : ""}
          </div>`,
          { className: "cyber-popup" }
        );
      });

      if (actualRouteDisplay.length > 1) {
        addPolyline(map, actualRouteDisplay, {
          color: "#00f0ff",
          weight: 2,
          opacity: 0.7,
          smoothFactor: 1.5,
        });

        addPolyline(map, actualRouteDisplay, {
          color: "#00f0ff",
          weight: 6,
          opacity: 0.15,
          smoothFactor: 1.5,
        });
      }

      const lastGeoEvent = geoEvents[0];
      const latestPoint = eventDisplayPoints.get(lastGeoEvent) ?? [
        lastGeoEvent.locationLat!,
        normalizeLongitude(lastGeoEvent.locationLng!),
      ];
      let predictedDestPoint: LatLngTuple | null = null;

      if (destLat != null && destLng != null && status.toLowerCase() !== "delivered") {
        // Route the predicted path through known future stops when available
        const geoFutureStops = (futureStops ?? []).filter(
          (s) => s.locationLat != null && s.locationLng != null
        );

        const predictedLine: LatLngTuple[] = [
          [lastGeoEvent.locationLat!, lastGeoEvent.locationLng!],
        ];
        const predictedStopRefs: FutureStop[] = [];
        for (const stop of geoFutureStops) {
          // Skip stops that coincide with the destination marker
          if (
            Math.abs(stop.locationLat! - destLat) < 0.05 &&
            Math.abs(stop.locationLng! - destLng) < 0.05
          ) {
            continue;
          }
          predictedLine.push([stop.locationLat!, stop.locationLng!]);
          predictedStopRefs.push(stop);
        }
        predictedLine.push([destLat, destLng]);

        const predictedDisplayLine = unwrapRouteLongitudes(predictedLine, latestPoint[1]);
        predictedDestPoint = predictedDisplayLine[predictedDisplayLine.length - 1] ?? null;

        predictedStopRefs.forEach((stop, index) => {
          const point = predictedDisplayLine[index + 1] ?? [
            stop.locationLat!,
            normalizeLongitude(stop.locationLng!),
          ];
          const etaDate = new Date(stop.eta);
          const etaText = formatRegionalDateHour(etaDate);
          const ghost = L.marker(point, {
            icon: createGhostIcon("#bf00ff"),
          }).addTo(map);
          ghost.bindPopup(
            `<div style="font-family:'JetBrains Mono',monospace;font-size:11px;color:#e0e6f0;background:#1a1f2e;padding:10px;border:1px solid #2a3040;border-radius:6px;min-width:180px;">
              <div style="color:#bf00ff;font-weight:bold;margin-bottom:4px;font-size:10px;letter-spacing:1px;">PREDICTED · ${formatStatusLabel(stop.status)}</div>
              <div style="margin-bottom:4px;">${stop.locationName}</div>
              <div style="color:#7a8599;font-size:10px;">ETA ${etaText} · ${Math.round(stop.frequencyPct)}% of shipments</div>
            </div>`,
            { className: "cyber-popup" }
          );
          points.push(point);
        });

        addPolyline(map, predictedDisplayLine, {
          color: "#bf00ff",
          weight: 2,
          opacity: 0.5,
          dashArray: "8, 8",
          smoothFactor: 1.5,
        });

        addPolyline(map, predictedDisplayLine, {
          color: "#bf00ff",
          weight: 6,
          opacity: 0.1,
          dashArray: "8, 8",
          smoothFactor: 1.5,
        });
      }

      if (destLat != null && destLng != null) {
        const destReferenceLng =
          predictedDestPoint?.[1] ??
          latestPoint[1] ??
          actualRouteDisplay[actualRouteDisplay.length - 1]?.[1];
        const destPoint = unwrapRouteLongitudes([[destLat, destLng]], destReferenceLng)[0];
        const destColor =
          isDeliveredStatus(status) ? "#39ff14" : "#00f0ff";
        const destMarker = L.marker(destPoint, {
          icon: createEndpointIcon("D", destColor),
        }).addTo(map);
        destMarker.bindPopup(
          `<div style="font-family:'JetBrains Mono',monospace;font-size:12px;color:#e0e6f0;background:#1a1f2e;padding:8px;border:1px solid #2a3040;border-radius:6px;">
            <div style="color:${destColor};font-weight:bold;margin-bottom:4px;">DESTINATION</div>
            <div>${destName || "Unknown"}</div>
          </div>`,
          { className: "cyber-popup" }
        );
        points.push(destPoint);
      }
    } else if (destLat != null && destLng != null) {
      const destReferenceLng = originPoint?.[1];
      const destPoint =
        destReferenceLng == null
          ? [destLat, normalizeLongitude(destLng)] as LatLngTuple
          : unwrapRouteLongitudes([[destLat, destLng]], destReferenceLng)[0];
      const destColor =
        isDeliveredStatus(status) ? "#39ff14" : "#00f0ff";
      const destMarker = L.marker(destPoint, {
        icon: createEndpointIcon("D", destColor),
      }).addTo(map);
      destMarker.bindPopup(
        `<div style="font-family:'JetBrains Mono',monospace;font-size:12px;color:#e0e6f0;background:#1a1f2e;padding:8px;border:1px solid #2a3040;border-radius:6px;">
          <div style="color:${destColor};font-weight:bold;margin-bottom:4px;">DESTINATION</div>
          <div>${destName || "Unknown"}</div>
        </div>`,
        { className: "cyber-popup" }
      );
      points.push(destPoint);
    }

    if (flights && flights.length > 0 && originLat != null && originLng != null) {
      flights.forEach((flight) => {
        const flightPoint: LatLngTuple = [
          flight.latitude,
          normalizeLongitude(flight.longitude),
        ];
        const altKm = flight.altitude ? (flight.altitude / 1000).toFixed(1) : "?";
        const speedKmh = flight.velocity ? Math.round(flight.velocity * 3.6) : "?";
        const marker = L.marker(flightPoint, {
          icon: createPlaneIcon(flight.heading ?? 0, flight.callsign),
        }).addTo(map);
        marker.bindPopup(
          `<div style="font-family:'JetBrains Mono',monospace;font-size:11px;color:#e0e6f0;background:#1a1f2e;padding:10px;border:1px solid #2a3040;border-radius:6px;min-width:160px;">
            <div style="color:#ffdd00;font-weight:bold;margin-bottom:4px;font-size:12px;">${flight.callsign}</div>
            <div style="color:#7a8599;">${flight.on_ground ? "On ground" : "In flight"}</div>
            ${flight.altitude ? `<div style="color:#7a8599;">Alt: ${altKm} km</div>` : ""}
            ${flight.velocity ? `<div style="color:#7a8599;">Speed: ${speedKmh} km/h</div>` : ""}
            ${flight.origin_country ? `<div style="color:#7a8599;">From: ${flight.origin_country}</div>` : ""}
          </div>`,
          { className: "cyber-popup" }
        );
        points.push(flightPoint);
      });
    }

    if (points.length > 0) {
      const bounds = L.latLngBounds(points);
      map.fitBounds(bounds, { padding: [30, 30], maxZoom: 10 });
      if (points.length > 1) {
        map.setMaxBounds(bounds.pad(0.3));
      }
    }
  }, [events, originLat, originLng, originName, destLat, destLng, destName, status, futureStops, flights]);

  return (
    <div className="relative">
      <div ref={mapRef} className="h-[300px] sm:h-[350px] rounded overflow-hidden" />
      <div className="absolute top-2 left-2 z-[1000] flex flex-col gap-1">
        <div className="flex items-center gap-1 bg-cyber-bg/80 backdrop-blur-sm border border-cyber-border rounded px-2 py-1">
          <div className="w-2 h-2 rounded-full bg-cyber-cyan" />
          <span className="text-[9px] text-cyber-muted font-mono">Route</span>
        </div>
        <div className="flex items-center gap-1 bg-cyber-bg/80 backdrop-blur-sm border border-cyber-border rounded px-2 py-1">
          <div className="w-4 h-0 border-t-2 border-dashed border-cyber-purple" />
          <span className="text-[9px] text-cyber-muted font-mono">Predicted</span>
        </div>
        <div className="flex items-center gap-1 bg-cyber-bg/80 backdrop-blur-sm border border-cyber-border rounded px-2 py-1">
          <div className="w-2 h-2 rounded-full bg-cyber-purple" />
          <span className="text-[9px] text-cyber-muted font-mono">Origin</span>
        </div>
        <div className="flex items-center gap-1 bg-cyber-bg/80 backdrop-blur-sm border border-cyber-border rounded px-2 py-1">
          <div className="w-2 h-2 rounded-full bg-cyber-green" />
          <span className="text-[9px] text-cyber-muted font-mono">Dest</span>
        </div>
        {flights && flights.length > 0 && (
          <div className="flex items-center gap-1 bg-cyber-bg/80 backdrop-blur-sm border border-cyber-border rounded px-2 py-1">
            <svg width="10" height="10" viewBox="0 0 24 24" fill="#ffdd00"><path d="M21 16v-2l-8-5V3.5C13 2.67 12.33 2 11.5 2S10 2.67 10 3.5V9l-8 5v2l8-2.5V19l-2 1.5V22l3.5-1 3.5 1v-1.5L13 19v-5.5l8 2.5z"/></svg>
            <span className="text-[9px] text-cyber-muted font-mono">{flights.length} Cargo Flight{flights.length === 1 ? "" : "s"}</span>
          </div>
        )}
      </div>
    </div>
  );
}
