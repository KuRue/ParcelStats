import Link from "next/link";
import { getServerSession } from "@/lib/auth";
import { redirect } from "next/navigation";
import {
  Package,
  BarChart3,
  Activity,
  Shield,
  Zap,
  Globe,
  ArrowRight,
  Terminal,
} from "lucide-react";

export default async function HomePage() {
  const session = await getServerSession();

  if (session) {
    redirect("/dashboard");
  }

  return (
    <div className="flex flex-col min-h-screen">
      <header className="border-b border-cyber-border bg-cyber-surface/80 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 h-16 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2">
            <Package className="w-6 h-6 text-cyber-cyan" />
            <span className="font-display font-bold text-lg text-cyber-cyan text-shadow-cyber">
              PARCELSTATS
            </span>
          </Link>
          <nav className="flex items-center gap-4">
            <Link
              href="/auth/signin"
              className="cyber-btn"
            >
              <Terminal className="w-4 h-4 mr-2" />
              Sign In
            </Link>
          </nav>
        </div>
      </header>

      <main className="flex-1">
        <section className="relative py-24 px-4">
          <div className="max-w-4xl mx-auto text-center">
            <div className="inline-flex items-center gap-2 cyber-badge-info mb-6">
              <Activity className="w-3 h-3" />
              <span>AI-Powered Tracking</span>
            </div>

            <h1 className="font-display text-5xl md:text-7xl font-bold mb-6 leading-tight">
              <span className="text-cyber-text">Track. </span>
              <span className="text-cyber-cyan text-shadow-cyber">Predict. </span>
              <span className="text-cyber-green text-shadow-green">Know.</span>
            </h1>

            <p className="text-cyber-muted text-lg md:text-xl max-w-2xl mx-auto mb-12">
              Community-powered parcel tracking that gets smarter with every
              shipment. AI-driven ETA predictions with confidence intervals
              across 25+ international carriers.
            </p>

            <div className="flex flex-col sm:flex-row gap-4 justify-center">
              <a
                href="/api/auth/signin"
                className="cyber-btn-primary cyber-btn text-lg px-8 py-3"
              >
                Start Tracking
                <ArrowRight className="w-5 h-5 ml-2 inline" />
              </a>
              <Link href="/stats" className="cyber-btn text-lg px-8 py-3">
                <BarChart3 className="w-5 h-5 mr-2 inline" />
                View Stats
              </Link>
            </div>
          </div>
        </section>

        <section className="py-16 px-4 border-t border-cyber-border/50">
          <div className="max-w-6xl mx-auto">
            <h2 className="font-display text-2xl text-center mb-12 text-cyber-text">
              How It Works
            </h2>
            <div className="grid md:grid-cols-3 gap-8">
              <div className="cyber-card text-center">
                <div className="w-12 h-12 rounded-full bg-cyber-cyan/10 border border-cyber-cyan/30 flex items-center justify-center mx-auto mb-4">
                  <Package className="w-6 h-6 text-cyber-cyan" />
                </div>
                <h3 className="font-display text-sm uppercase tracking-wider text-cyber-cyan mb-2">
                  01. Track
                </h3>
                <p className="text-cyber-muted text-sm">
                  Add your tracking number. We pull data from 25+ carriers
                  using APIs and intelligent scraping.
                </p>
              </div>

              <div className="cyber-card text-center">
                <div className="w-12 h-12 rounded-full bg-cyber-purple/10 border border-cyber-purple/30 flex items-center justify-center mx-auto mb-4">
                  <Zap className="w-6 h-6 text-cyber-purple" />
                </div>
                <h3 className="font-display text-sm uppercase tracking-wider text-cyber-purple mb-2">
                  02. Predict
                </h3>
                <p className="text-cyber-muted text-sm">
                  Our ML model analyzes route patterns, historical data, and
                  carrier performance to predict delivery with confidence levels.
                </p>
              </div>

              <div className="cyber-card text-center">
                <div className="w-12 h-12 rounded-full bg-cyber-green/10 border border-cyber-green/30 flex items-center justify-center mx-auto mb-4">
                  <Shield className="w-6 h-6 text-cyber-green" />
                </div>
                <h3 className="font-display text-sm uppercase tracking-wider text-cyber-green mb-2">
                  03. Improve
                </h3>
                <p className="text-cyber-muted text-sm">
                  Every tracked package feeds our model. More users = better
                  predictions. The network effect makes everyone smarter.
                </p>
              </div>
            </div>
          </div>
        </section>

        <section className="py-16 px-4 border-t border-cyber-border/50">
          <div className="max-w-6xl mx-auto text-center">
            <h2 className="font-display text-2xl text-cyber-text mb-8">
              Supported Carriers
            </h2>
            <div className="flex items-center justify-center gap-2 mb-4">
              <Globe className="w-5 h-5 text-cyber-cyan" />
              <span className="text-cyber-cyan font-display text-3xl font-bold">25+</span>
              <span className="text-cyber-muted">international carriers</span>
            </div>
            <div className="flex flex-wrap justify-center gap-2">
              {[
                "USPS", "UPS", "FedEx", "DHL Express", "Royal Mail",
                "Canada Post", "Australia Post", "Deutsche Post", "GLS",
                "Hermes", "China Post", "Japan Post", "La Poste", "PostNord",
                "Swiss Post", "Correos", "Poste Italiane", "India Post",
                "Singapore Post", "Thai Post",
              ].map((carrier) => (
                <span key={carrier} className="cyber-badge-info">
                  {carrier}
                </span>
              ))}
              <span className="cyber-badge-purple">+ more</span>
            </div>
          </div>
        </section>
      </main>

      <footer className="border-t border-cyber-border py-8 px-4">
        <div className="max-w-7xl mx-auto flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <Package className="w-4 h-4 text-cyber-cyan" />
            <span className="font-mono text-sm text-cyber-muted">
              ParcelStats v0.1.0
            </span>
          </div>
          <p className="font-mono text-xs text-cyber-muted/60">
            Open source parcel tracking. MIT License.
          </p>
        </div>
      </footer>
    </div>
  );
}
