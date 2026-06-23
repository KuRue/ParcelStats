"use client";

import { useState, useEffect } from "react";
import { CyberCard } from "@/components/ui/cyber-card";
import {
  Settings,
  User,
  Bell,
  Globe,
  Shield,
  Check,
  AlertTriangle,
  Server,
} from "lucide-react";
import Link from "next/link";

interface CarrierInfo {
  slug: string;
  name: string;
  type: string;
}

export function SettingsContent({ userEmail }: { userEmail: string }) {
  const [carriers, setCarriers] = useState<CarrierInfo[]>([]);
  const [preflightOn, setPreflightOn] = useState(true);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [compactView, setCompactView] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    fetch("/api/carriers")
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (data?.carriers) {
          setCarriers(
            data.carriers.map((c: CarrierInfo) => ({
              slug: c.slug,
              name: c.name,
              type: c.type || "api",
            }))
          );
        }
      })
      .catch(() => {});
  }, []);

  const handleSave = () => {
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  return (
    <div className="max-w-4xl mx-auto px-4 py-6 md:py-8 pb-24 md:pb-8">
      <div className="flex items-center gap-2 mb-6">
        <Settings className="w-6 h-6 text-cyber-cyan" />
        <h1 className="font-display text-xl font-bold text-cyber-cyan text-shadow-cyber">
          Settings
        </h1>
      </div>

      <div className="space-y-4">
        <CyberCard terminal title="Account" glow="cyan">
          <div className="flex items-center gap-3">
            <User className="w-5 h-5 text-cyber-cyan shrink-0" />
            <div className="min-w-0 flex-1">
              <p className="font-mono text-sm text-cyber-text">{userEmail}</p>
              <p className="font-mono text-xs text-cyber-muted">Google OAuth</p>
            </div>
            <Shield className="w-4 h-4 text-cyber-green shrink-0" />
          </div>
        </CyberCard>

        <CyberCard terminal title="Display Preferences" glow="purple">
          <div className="space-y-4">
            <Toggle
              label="Flight tracking overlay"
              description="Show live cargo flights on the shipment map for international packages"
              checked={preflightOn}
              onChange={setPreflightOn}
            />
            <Toggle
              label="Auto-refresh tracking"
              description="Automatically poll for new events every 60 seconds on active shipments"
              checked={autoRefresh}
              onChange={setAutoRefresh}
            />
            <Toggle
              label="Compact dashboard view"
              description="Show more shipments per screen with condensed cards"
              checked={compactView}
              onChange={setCompactView}
            />
          </div>
        </CyberCard>

        <CyberCard terminal title="Supported Carriers" glow="green">
          <p className="font-mono text-xs text-cyber-muted mb-3">
            {carriers.length} carriers configured
          </p>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
            {carriers.map((c) => (
              <div
                key={c.slug}
                className="flex items-center gap-2 border border-cyber-border/40 rounded px-2 py-1.5"
              >
                <div
                  className={`w-1.5 h-1.5 rounded-full ${
                    c.type === "api" ? "bg-cyber-green" : "bg-cyber-yellow"
                  }`}
                />
                <span className="font-mono text-xs text-cyber-text truncate">
                  {c.name}
                </span>
              </div>
            ))}
          </div>
          <p className="font-mono text-[10px] text-cyber-muted mt-3">
            <span className="inline-block w-1.5 h-1.5 rounded-full bg-cyber-green mr-1" />
            API-based (faster) &nbsp;&nbsp;
            <span className="inline-block w-1.5 h-1.5 rounded-full bg-cyber-yellow mr-1" />
            Playwright (browser scrape)
          </p>
        </CyberCard>

        <CyberCard terminal title="System Status" glow="cyan">
          <div className="space-y-2">
            <StatusRow label="ML Service" ok={true} />
            <StatusRow label="Flight Tracking" ok={true} detail="OpenSky Network" />
            <StatusRow label="Prediction Engine" ok={true} detail="Knowledge-based + ML" />
            <StatusRow label="Route Research Agent" ok={false} detail="Set OPENAI_API_KEY" />
          </div>
        </CyberCard>

        <CyberCard terminal title="API Keys" glow="purple">
          <p className="font-mono text-xs text-cyber-muted mb-3">
            Optional API keys for enhanced carrier tracking:
          </p>
          <div className="space-y-2">
            <KeyRow name="USPS Web Tools" envVar="USPS_WEB_TOOLS_USER_ID" signupUrl="registration.shippingapis.com" />
            <KeyRow name="UPS Developer" envVar="UPS_CLIENT_ID" envVar2="UPS_CLIENT_SECRET" signupUrl="ups.com/developers" />
            <KeyRow name="FedEx Developer" envVar="FEDEX_CLIENT_ID" envVar2="FEDEX_CLIENT_SECRET" signupUrl="developer.fedex.com" />
            <KeyRow name="OpenAI (Route Research)" envVar="OPENAI_API_KEY" signupUrl="platform.openai.com" />
          </div>
          <p className="font-mono text-[10px] text-cyber-muted mt-3">
            Set these in your{" "}
            <code className="text-cyber-cyan">.env</code>
            file and restart the ML service.
          </p>
        </CyberCard>

        <div className="flex items-center justify-between">
          <Link href="/dashboard" className="text-sm text-cyber-muted hover:text-cyber-cyan font-mono">
            ← Back to Dashboard
          </Link>
          <button
            onClick={handleSave}
            className="cyber-btn text-sm flex items-center gap-2"
          >
            {saved ? (
              <>
                <Check className="w-4 h-4 text-cyber-green" />
                Saved
              </>
            ) : (
              "Save Preferences"
            )}
          </button>
        </div>
      </div>
    </div>
  );
}

function Toggle({
  label,
  description,
  checked,
  onChange,
}: {
  label: string;
  description: string;
  checked: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <div className="flex items-start justify-between gap-4">
      <div className="min-w-0">
        <p className="font-mono text-sm text-cyber-text">{label}</p>
        <p className="font-mono text-xs text-cyber-muted">{description}</p>
      </div>
      <button
        onClick={() => onChange(!checked)}
        className={`relative shrink-0 w-11 h-6 rounded-full transition-colors ${
          checked ? "bg-cyber-cyan/40" : "bg-cyber-border/40"
        }`}
      >
        <div
          className={`absolute top-0.5 w-5 h-5 rounded-full transition-transform ${
            checked ? "translate-x-5 bg-cyber-cyan" : "translate-x-0.5 bg-cyber-muted"
          }`}
          style={{ boxShadow: checked ? "0 0 8px #00f0ff80" : "none" }}
        />
      </button>
    </div>
  );
}

function StatusRow({ label, ok, detail }: { label: string; ok: boolean; detail?: string }) {
  return (
    <div className="flex items-center justify-between">
      <div className="flex items-center gap-2">
        <div
          className={`w-2 h-2 rounded-full ${
            ok ? "bg-cyber-green" : "bg-cyber-yellow"
          }`}
          style={{ boxShadow: ok ? "0 0 6px #39ff1480" : "0 0 6px #ffdd0080" }}
        />
        <span className="font-mono text-xs text-cyber-text">{label}</span>
      </div>
      {detail && (
        <span className="font-mono text-[10px] text-cyber-muted">{detail}</span>
      )}
    </div>
  );
}

function KeyRow({
  name,
  envVar,
  envVar2,
  signupUrl,
}: {
  name: string;
  envVar: string;
  envVar2?: string;
  signupUrl: string;
}) {
  return (
    <div className="flex items-center justify-between border border-cyber-border/30 rounded px-3 py-2">
      <div>
        <p className="font-mono text-xs text-cyber-text">{name}</p>
        <p className="font-mono text-[10px] text-cyber-muted">
          {envVar}
          {envVar2 ? ` + ${envVar2}` : ""}
        </p>
      </div>
      <span className="font-mono text-[10px] text-cyber-cyan/60">
        {signupUrl}
      </span>
    </div>
  );
}
