import type { Metadata, Viewport } from "next";
import { AuthProvider } from "@/components/ui/auth-provider";
import { MobileNav } from "@/components/ui/mobile-nav";
import "@/styles/globals.css";

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
  userScalable: false,
  themeColor: "#00f0ff",
};

export const metadata: Metadata = {
  title: "ParcelStats - AI-Powered Package Tracking",
  description:
    "Community-powered predictive parcel tracking with AI-driven ETA estimates and route analysis.",
  keywords: [
    "package tracking",
    "parcel tracking",
    "AI tracking",
    "delivery prediction",
  ],
  manifest: "/manifest.json",
  appleWebApp: {
    capable: true,
    statusBarStyle: "black-translucent",
    title: "ParcelStats",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-cyber-bg bg-grid-pattern bg-grid bg-scan-line">
        <AuthProvider>
          <div className="relative z-10">{children}</div>
          <MobileNav />
        </AuthProvider>
      </body>
    </html>
  );
}
