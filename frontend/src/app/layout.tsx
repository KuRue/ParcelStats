import type { Metadata } from "next";
import { AuthProvider } from "@/components/ui/auth-provider";
import "@/styles/globals.css";

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
        </AuthProvider>
      </body>
    </html>
  );
}
