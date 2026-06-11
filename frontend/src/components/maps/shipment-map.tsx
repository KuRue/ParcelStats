"use client";

import { useEffect, useRef } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { formatStatusLabel } from "@/lib/utils";

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

function getStatusColor(status: string): string {
  const s = status.toLowerCase();
  if (s.includes("deliver") && !s.includes("fail") && !s.includes("exception"))
    return "#39ff14";
  if (s.includes("out for delivery")) return "#bf00ff";
  if (s.includes("transit")) return "#00f0ff";
  if (s.includes("custom")) return "#ffdd00";
  if (s.includes("exception") || s.includes("fail")) return "#ff003c";
  if (s.includes("arrived") || s.includes("departed")) return "#00f0ff";
  return "#7a8599";
}

function eventTimestamp(event: MapEvent): number {
  const timestamp = new Date(event.eventTime).getTime();
  return Number.isFinite(timestamp) ? timestamp : 0;
}

function addRoutePoint(
  routeCoords: L.LatLngExpression[],
  lat: number,
  lng: number
) {
  const last = routeCoords[routeCoords.length - 1] as [number, number] | undefined;
  if (last && Math.abs(last[0] - lat) < 0.0001 && Math.abs(last[1] - lng) < 0.0001) {
    return;
  }
  routeCoords.push([lat, lng]);
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

    const points: L.LatLngExpression[] = [];
    const markers: L.Marker[] = [];

    if (originLat != null && originLng != null) {
      const originMarker = L.marker([originLat, originLng], {
        icon: createEndpointIcon("O", "#bf00ff"),
      }).addTo(map);
      originMarker.bindPopup(
        `<div style="font-family:'JetBrains Mono',monospace;font-size:12px;color:#e0e6f0;background:#1a1f2e;padding:8px;border:1px solid #2a3040;border-radius:6px;">
          <div style="color:#bf00ff;font-weight:bold;margin-bottom:4px;">ORIGIN</div>
          <div>${originName || "Unknown"}</div>
        </div>`,
        { className: "cyber-popup" }
      );
      markers.push(originMarker);
      points.push([originLat, originLng]);
    }

    const geoEvents = events.filter(
      (e) => e.locationLat != null && e.locationLng != null
    );

    if (geoEvents.length > 0) {
      const routeCoords: L.LatLngExpression[] = [];
      const routeEvents = [...geoEvents].sort(
        (a, b) => eventTimestamp(a) - eventTimestamp(b)
      );

      if (originLat != null && originLng != null) {
        addRoutePoint(routeCoords, originLat, originLng);
      }

      geoEvents.forEach((event, i) => {
        const lat = event.locationLat!;
        const lng = event.locationLng!;
        points.push([lat, lng]);

        const isLatest = i === 0;
        const color = getStatusColor(event.status);

        const marker = L.marker([lat, lng], {
          icon: isLatest ? createPulseIcon(color) : createIcon(color),
        }).addTo(map);

        const time = event.eventTime
          ? new Date(event.eventTime).toLocaleString()
          : "";

        marker.bindPopup(
          `<div style="font-family:'JetBrains Mono',monospace;font-size:11px;color:#e0e6f0;background:#1a1f2e;padding:10px;border:1px solid #2a3040;border-radius:6px;min-width:180px;">
            <div style="color:${color};font-weight:bold;margin-bottom:4px;font-size:10px;letter-spacing:1px;">${formatStatusLabel(event.status)}</div>
            ${event.locationName ? `<div style="margin-bottom:4px;">${event.locationName}</div>` : ""}
            ${event.description ? `<div style="color:#7a8599;margin-bottom:4px;">${event.description}</div>` : ""}
            ${time ? `<div style="color:#7a8599;font-size:10px;">${time}</div>` : ""}
          </div>`,
          { className: "cyber-popup" }
        );
        markers.push(marker);
      });

      routeEvents.forEach((event) => {
        addRoutePoint(routeCoords, event.locationLat!, event.locationLng!);
      });

      if (routeCoords.length > 1) {
        L.polyline(routeCoords, {
          color: "#00f0ff",
          weight: 2,
          opacity: 0.7,
          smoothFactor: 1.5,
        }).addTo(map);

        L.polyline(routeCoords, {
          color: "#00f0ff",
          weight: 6,
          opacity: 0.15,
          smoothFactor: 1.5,
        }).addTo(map);
      }

      const lastGeoEvent = geoEvents[0];
      if (destLat != null && destLng != null && status.toLowerCase() !== "delivered") {
        // Route the predicted path through known future stops when available
        const geoFutureStops = (futureStops ?? []).filter(
          (s) => s.locationLat != null && s.locationLng != null
        );

        const predictedLine: L.LatLngExpression[] = [
          [lastGeoEvent.locationLat!, lastGeoEvent.locationLng!],
        ];
        for (const stop of geoFutureStops) {
          // Skip stops that coincide with the destination marker
          if (
            Math.abs(stop.locationLat! - destLat) < 0.05 &&
            Math.abs(stop.locationLng! - destLng) < 0.05
          ) {
            continue;
          }
          predictedLine.push([stop.locationLat!, stop.locationLng!]);

          const etaDate = new Date(stop.eta);
          const etaText = Number.isFinite(etaDate.getTime())
            ? etaDate.toLocaleDateString(undefined, {
                month: "short",
                day: "numeric",
              })
            : "";
          const ghost = L.marker([stop.locationLat!, stop.locationLng!], {
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
          markers.push(ghost);
          points.push([stop.locationLat!, stop.locationLng!]);
        }
        predictedLine.push([destLat, destLng]);

        L.polyline(predictedLine, {
          color: "#bf00ff",
          weight: 2,
          opacity: 0.5,
          dashArray: "8, 8",
          smoothFactor: 1.5,
        }).addTo(map);

        L.polyline(predictedLine, {
          color: "#bf00ff",
          weight: 6,
          opacity: 0.1,
          dashArray: "8, 8",
          smoothFactor: 1.5,
        }).addTo(map);

        points.push([destLat, destLng]);
      }
    }

    if (destLat != null && destLng != null) {
      const destColor =
        status.toLowerCase() === "delivered" ? "#39ff14" : "#00f0ff";
      const destMarker = L.marker([destLat, destLng], {
        icon: createEndpointIcon("D", destColor),
      }).addTo(map);
      destMarker.bindPopup(
        `<div style="font-family:'JetBrains Mono',monospace;font-size:12px;color:#e0e6f0;background:#1a1f2e;padding:8px;border:1px solid #2a3040;border-radius:6px;">
          <div style="color:${destColor};font-weight:bold;margin-bottom:4px;">DESTINATION</div>
          <div>${destName || "Unknown"}</div>
        </div>`,
        { className: "cyber-popup" }
      );
      markers.push(destMarker);
    }

    if (points.length > 0) {
      const bounds = L.latLngBounds(points);
      map.fitBounds(bounds, { padding: [30, 30], maxZoom: 10 });
    }
  }, [events, originLat, originLng, originName, destLat, destLng, destName, status, futureStops]);

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
      </div>
    </div>
  );
}
