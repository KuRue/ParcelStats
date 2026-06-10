/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        cyber: {
          bg: "#0a0e17",
          surface: "#111827",
          card: "#1a1f2e",
          border: "#2a3040",
          "border-bright": "#3a4060",
          text: "#e0e6f0",
          muted: "#7a8599",
          cyan: "#00f0ff",
          "cyan-dim": "#00a3ad",
          green: "#39ff14",
          "green-dim": "#2ab80f",
          purple: "#bf00ff",
          "purple-dim": "#8a00ba",
          red: "#ff003c",
          orange: "#ff6600",
          yellow: "#ffdd00",
        },
      },
      fontFamily: {
        mono: ["JetBrains Mono", "Fira Code", "monospace"],
        display: ["Orbitron", "sans-serif"],
      },
      backgroundImage: {
        "grid-pattern":
          "linear-gradient(rgba(0,240,255,0.03) 1px, transparent 1px), linear-gradient(90deg, rgba(0,240,255,0.03) 1px, transparent 1px)",
        "scan-line":
          "repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(0,240,255,0.015) 2px, rgba(0,240,255,0.015) 4px)",
      },
      backgroundSize: {
        grid: "40px 40px",
      },
      boxShadow: {
        "cyber-glow": "0 0 10px rgba(0,240,255,0.18), 0 0 30px rgba(0,240,255,0.06)",
        "cyber-glow-green":
          "0 0 10px rgba(57,255,20,0.16), 0 0 30px rgba(57,255,20,0.05)",
        "cyber-glow-purple":
          "0 0 10px rgba(191,0,255,0.16), 0 0 30px rgba(191,0,255,0.05)",
      },
      animation: {
        pulse: "pulse 2s cubic-bezier(0.4,0,0.6,1) infinite",
        "glow-pulse": "glow-pulse 2s ease-in-out infinite",
        "scan": "scan 8s linear infinite",
      },
      keyframes: {
        "glow-pulse": {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0.5" },
        },
        scan: {
          "0%": { transform: "translateY(-100%)" },
          "100%": { transform: "translateY(100%)" },
        },
      },
    },
  },
  plugins: [],
};
