"use client";

import { useEffect, useRef } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { splitRouteAtAntimeridian, type LatLngTuple } from "@/lib/geo";
import {
  formatRegionalDateHour,
  formatStatusLabel,
  isDeliveredStatus,
  isIssueStatus,
  normalizedStatus,
} from "@/lib/utils";

interface ShipmentMapItem {
  id: string;
  trackingNumber: string;
  status: string;
  carrier: { name: string; slug: string };
  originName: string | null;
  originLat: string | null;
  originLng: string | null;
  destName: string | null;
  destLat: string | null;
  destLng: string | null;
  lastLat: string | null;
  lastLng: string | null;
  estimatedDelivery: string | null;
}

interface GlobalMapProps {
  shipments: ShipmentMapItem[];
  onSelect?: (shipmentId: string) => void;
  selectedId?: string | null;
}

function getStatusColor(status: string): string {
  const s = normalizedStatus(status);
  if (isDeliveredStatus(status)) return "#39ff14";
  if (s.includes("out for delivery")) return "#bf00ff";
  if (s.includes("transit")) return "#00f0ff";
  if (s.includes("custom")) return "#ffdd00";
  if (isIssueStatus(status)) return "#ff003c";
  return "#7a8599";
}

function createShipmentMarker(color: string, pulse: boolean = false) {
  const size = pulse ? 14 : 10;
  const glow = pulse
    ? `box-shadow:0 0 12px ${color}80, 0 0 30px ${color}40; animation:pulse 2s ease-in-out infinite;`
    : `box-shadow:0 0 8px ${color}60;`;

  return L.divIcon({
    className: "custom-marker",
    html: `<div style="
      width:${size}px;height:${size}px;
      background:${color};
      border:2px solid ${color};
      border-radius:50%;
      ${glow}
    "></div>`,
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2],
  });
}

function createEndpointDot(label: string, color: string) {
  return L.divIcon({
    className: "custom-marker",
    html: `<div style="
      width:8px;height:8px;
      background:${color}60;
      border:1px solid ${color}80;
      border-radius:50%;
    "></div>`,
    iconSize: [8, 8],
    iconAnchor: [4, 4],
  });
}

function addPolylineSegments(
  layer: L.LayerGroup,
  routeCoords: LatLngTuple[],
  options: L.PolylineOptions
) {
  splitRouteAtAntimeridian(routeCoords).forEach((segment) => {
    if (segment.length > 1) {
      L.polyline(segment, options).addTo(layer);
    }
  });
}

export function GlobalMap({ shipments, onSelect, selectedId }: GlobalMapProps) {
  const mapRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<L.Map | null>(null);
  const markersLayerRef = useRef<L.LayerGroup | null>(null);

  useEffect(() => {
    if (!mapRef.current || mapInstanceRef.current) return;

    const map = L.map(mapRef.current, {
      center: [25, 0],
      zoom: 2,
      zoomControl: false,
      attributionControl: false,
    });

    L.tileLayer(
      "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
      { maxZoom: 18, subdomains: "abcd" }
    ).addTo(map);

    L.control.zoom({ position: "bottomright" }).addTo(map);

    L.control
      .attribution({ position: "bottomleft", prefix: false })
      .addAttribution("&copy; <a href='https://carto.com/' style='color:#7a8599'>CARTO</a>")
      .addTo(map);

    markersLayerRef.current = L.layerGroup().addTo(map);
    mapInstanceRef.current = map;

    return () => {
      map.remove();
      mapInstanceRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapInstanceRef.current;
    const layer = markersLayerRef.current;
    if (!map || !layer) return;

    layer.clearLayers();

    if (shipments.length === 0) return;

    const allPoints: LatLngTuple[] = [];

    shipments.forEach((s) => {
      const color = getStatusColor(s.status);
      const isSelected = s.id === selectedId;
      const hasOrigin = s.originLat && s.originLng;
      const hasDest = s.destLat && s.destLng;
      const hasLast = s.lastLat && s.lastLng;
      const isActive =
        !isDeliveredStatus(s.status) &&
        !isIssueStatus(s.status);

      if (hasOrigin) {
        const origin = L.marker([parseFloat(s.originLat!), parseFloat(s.originLng!)], {
          icon: createEndpointDot("O", "#bf00ff"),
        }).addTo(layer);
        allPoints.push([parseFloat(s.originLat!), parseFloat(s.originLng!)]);
      }

      if (hasDest) {
        const dest = L.marker([parseFloat(s.destLat!), parseFloat(s.destLng!)], {
          icon: createEndpointDot("D", isActive ? "#00f0ff" : "#39ff14"),
        }).addTo(layer);
        allPoints.push([parseFloat(s.destLat!), parseFloat(s.destLng!)]);
      }

      const routePoints: LatLngTuple[] = [];
      if (hasOrigin) routePoints.push([parseFloat(s.originLat!), parseFloat(s.originLng!)]);

      if (hasLast) {
        routePoints.push([parseFloat(s.lastLat!), parseFloat(s.lastLng!)]);

        const marker = L.marker(
          [parseFloat(s.lastLat!), parseFloat(s.lastLng!)],
          { icon: createShipmentMarker(color, isActive) }
        ).addTo(layer);

        const eta = s.estimatedDelivery
          ? `<div style="color:#00f0ff;margin-top:4px;">ETA: ${formatRegionalDateHour(s.estimatedDelivery)}</div>`
          : "";

        marker.bindPopup(
          `<div style="font-family:'JetBrains Mono',monospace;font-size:11px;color:#e0e6f0;background:#1a1f2e;padding:10px;border:1px solid #2a3040;border-radius:6px;min-width:200px;">
            <div style="color:${color};font-weight:bold;font-size:10px;letter-spacing:1px;margin-bottom:6px;">${formatStatusLabel(s.status)}</div>
            <div style="margin-bottom:4px;">${s.trackingNumber}</div>
            <div style="color:#7a8599;font-size:10px;">${s.carrier.name}</div>
            ${eta}
          </div>`,
          { className: "cyber-popup" }
        );

        if (isSelected) {
          marker.openPopup();
        }

        if (onSelect) {
          marker.on("click", () => onSelect(s.id));
        }

        allPoints.push([parseFloat(s.lastLat!), parseFloat(s.lastLng!)]);
      }

      if (hasDest) routePoints.push([parseFloat(s.destLat!), parseFloat(s.destLng!)]);

      if (routePoints.length > 1) {
        addPolylineSegments(layer, routePoints, {
          color: color,
          weight: isSelected ? 2.5 : 1.5,
          opacity: isSelected ? 0.8 : 0.4,
          smoothFactor: 1.5,
        });

        if (isActive && hasLast && hasDest) {
          const predictedLine: LatLngTuple[] = [
            [parseFloat(s.lastLat!), parseFloat(s.lastLng!)],
            [parseFloat(s.destLat!), parseFloat(s.destLng!)],
          ];
          addPolylineSegments(layer, predictedLine, {
            color: "#bf00ff",
            weight: isSelected ? 1.5 : 1,
            opacity: isSelected ? 0.5 : 0.2,
            dashArray: "6, 6",
          });
        }
      }
    });

    if (allPoints.length > 0) {
      const bounds = L.latLngBounds(allPoints);
      map.fitBounds(bounds, { padding: [40, 40], maxZoom: 8 });
    }
  }, [shipments, onSelect, selectedId]);

  return (
    <div className="relative h-full">
      <div ref={mapRef} className="h-full w-full rounded overflow-hidden" />
      <div className="absolute top-2 left-2 z-[1000] flex flex-col gap-1">
        <div className="flex items-center gap-1 bg-cyber-bg/80 backdrop-blur-sm border border-cyber-border rounded px-2 py-1">
          <div className="w-2 h-2 rounded-full bg-cyber-cyan animate-pulse" />
          <span className="text-[9px] text-cyber-muted font-mono">
            {shipments.filter((s) => !isDeliveredStatus(s.status) && !isIssueStatus(s.status)).length} active
          </span>
        </div>
        <div className="flex items-center gap-1 bg-cyber-bg/80 backdrop-blur-sm border border-cyber-border rounded px-2 py-1">
          <div className="w-2 h-2 rounded-full bg-cyber-green" />
          <span className="text-[9px] text-cyber-muted font-mono">
            {shipments.filter((s) => isDeliveredStatus(s.status)).length} delivered
          </span>
        </div>
      </div>
    </div>
  );
}
