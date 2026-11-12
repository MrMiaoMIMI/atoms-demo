/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: {
          950: "#070b16",
          900: "#0a0f1f",
          850: "#0d1424",
          800: "#111a2e",
          700: "#1a2540",
        },
        accent: {
          DEFAULT: "#6c8cff",
          soft: "#8fa8ff",
        },
        mint: "#38e1c6",
      },
      fontFamily: {
        sans: [
          "Inter",
          "PingFang SC",
          "Microsoft YaHei",
          "system-ui",
          "sans-serif",
        ],
        mono: ["JetBrains Mono", "ui-monospace", "SFMono-Regular", "monospace"],
      },
      keyframes: {
        rise: {
          // Transform-only on purpose: an opacity-0 first frame can leave rows
          // invisible in headless screenshots / throttled tabs.
          "0%": { transform: "translateY(6px)" },
          "100%": { transform: "translateY(0)" },
        },
        shimmer: {
          "0%": { backgroundPosition: "200% 0" },
          "100%": { backgroundPosition: "-200% 0" },
        },
      },
      animation: {
        rise: "rise .28s ease both",
        shimmer: "shimmer 2.4s linear infinite",
      },
    },
  },
  plugins: [],
};
