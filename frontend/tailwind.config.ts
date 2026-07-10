import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        // AGRIOS brand palette — derived from logo (Design System v1)
        // CRITICAL: Do NOT revert to #16a34a — this is the exact logo green.
        brand: {
          50:  "#e8f5eb",
          100: "#c5e5cc",
          200: "#9ed4aa",
          300: "#74c287",
          400: "#52b469",
          500: "#33a64d",
          600: "#076524",   // PRIMARY — exact AGRIOS logo Forest Green
          700: "#065720",
          800: "#054a1b",
          900: "#033c14",
        },
        // AGRIOS Navy — OS / technology pillar (Design System v1)
        navy: {
          50:  "#e8edf8",
          100: "#c6d0ef",
          200: "#a1b1e6",
          300: "#7891dc",
          400: "#5677d5",
          500: "#355fcd",
          600: "#063491",   // PRIMARY — exact AGRIOS logo Navy Blue
          700: "#052c7d",
          800: "#04246a",
          900: "#031c57",
        },
        // Module accent colours (Design System v1)
        module: {
          poultry:    "#076524",
          rabbit:     "#D97706",
          dairy:      "#0284C7",
          fish:       "#0D9488",
          crop:       "#92400E",
          enterprise: "#7C3AED",
        },
        // Alert severity colours (used across Health, Finance, ARIA)
        severity: {
          info:     "#3b82f6",
          warning:  "#f59e0b",
          alert:    "#ef4444",
          critical: "#7c3aed",
        },
      },
      // Minimum touch target size (Engineering Constitution: 48x48px)
      minHeight: {
        touch: "48px",
        "touch-primary": "56px",
      },
      minWidth: {
        touch: "48px",
      },
      // Safe area for bottom navigation on modern phones
      spacing: {
        "bottom-nav": "64px",
        "top-bar": "56px",
        "safe-bottom": "env(safe-area-inset-bottom)",
      },
    },
  },
  plugins: [],
};

export default config;
