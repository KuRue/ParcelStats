"use client";

import dynamic from "next/dynamic";
import { Loader2 } from "lucide-react";

const ParcelGlobe = dynamic(() => import("./parcel-globe"), {
  ssr: false,
  loading: () => (
    <div className="absolute inset-0 flex items-center justify-center">
      <Loader2 className="w-8 h-8 text-cyber-cyan animate-spin" />
    </div>
  ),
});

export default ParcelGlobe;

export type { GlobeShipment, GlobeFlight } from "./parcel-globe";

export function webglAvailable(): boolean {
  if (typeof window === "undefined") return true;
  try {
    const canvas = document.createElement("canvas");
    return !!(
      window.WebGLRenderingContext &&
      (canvas.getContext("webgl") || canvas.getContext("experimental-webgl"))
    );
  } catch {
    return false;
  }
}
