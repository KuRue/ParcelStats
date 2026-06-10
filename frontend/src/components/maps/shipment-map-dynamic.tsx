"use client";

import dynamic from "next/dynamic";

const ShipmentRouteMap = dynamic(
  () =>
    import("@/components/maps/shipment-map").then(
      (mod) => mod.ShipmentRouteMap
    ),
  {
    ssr: false,
    loading: () => (
      <div className="h-[300px] sm:h-[350px] bg-cyber-surface rounded border border-cyber-border flex items-center justify-center">
        <div className="text-center">
          <div className="w-6 h-6 border-2 border-cyber-cyan border-t-transparent rounded-full animate-spin mx-auto mb-2" />
          <p className="text-xs text-cyber-muted font-mono">Loading map...</p>
        </div>
      </div>
    ),
  }
);

export default ShipmentRouteMap;
