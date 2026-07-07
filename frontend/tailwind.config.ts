import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        // Premium dark navy/black base with a single green accent, used
        // consistently across the marketing pages and the app screens.
        background: {
          DEFAULT: "#05080F",
          surface: "#0B1120",
          elevated: "#111A2E",
        },
        border: {
          DEFAULT: "#1E293B",
        },
        accent: {
          DEFAULT: "#22C55E",
          muted: "#16A34A",
          soft: "#86EFAC",
        },
        foreground: {
          DEFAULT: "#E5E7EB",
          muted: "#94A3B8",
          subtle: "#64748B",
        },
        danger: "#F87171",
        warning: "#FBBF24",
      },
      fontFamily: {
        sans: [
          "Inter",
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "Segoe UI",
          "Roboto",
          "sans-serif",
        ],
        mono: [
          "JetBrains Mono",
          "ui-monospace",
          "SFMono-Regular",
          "Menlo",
          "monospace",
        ],
      },
      boxShadow: {
        glow: "0 0 0 1px rgba(34,197,94,0.15), 0 8px 30px rgba(34,197,94,0.08)",
      },
      backgroundImage: {
        "grid-pattern":
          "linear-gradient(to right, rgba(148,163,184,0.06) 1px, transparent 1px), linear-gradient(to bottom, rgba(148,163,184,0.06) 1px, transparent 1px)",
      },
    },
  },
  plugins: [],
};

export default config;
