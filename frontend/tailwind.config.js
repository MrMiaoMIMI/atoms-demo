/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          DEFAULT: "#4267FF",
          text: "#425CE1",
          50: "#ECF1FF",
          100: "#DDE7FF",
          200: "#CBDAFF",
          300: "#9AB4FF",
          400: "#7D9AFF",
          500: "#4267FF",
          600: "#425CE1",
          700: "#293A90",
        },
        base: {
          DEFAULT: "#F6F6F6",
          sidebar: "#EBEBEA",
          card: "#FFFFFF",
        },
        ink: {
          95: "rgba(12,12,12,0.95)",
          80: "rgba(12,12,12,0.80)",
          55: "rgba(12,12,12,0.55)",
          30: "rgba(12,12,12,0.30)",
          12: "rgba(12,12,12,0.12)",
        },
        line: {
          2: "rgba(12,12,12,0.02)",
          4: "rgba(12,12,12,0.04)",
          6: "rgba(12,12,12,0.06)",
          8: "rgba(12,12,12,0.08)",
          12: "rgba(12,12,12,0.12)",
        },
        positive: "#41A35D",
        warning: "#D87A16",
        danger: "#C9444A",
        violet: "#895AF6",
      },
      fontFamily: {
        sans: [
          '"IBM Plex Sans"',
          "PingFang SC",
          "Hiragino Sans GB",
          "Microsoft YaHei",
          "Noto Sans CJK SC",
          "system-ui",
          "sans-serif",
        ],
        serif: ['"IBM Plex Serif"', "Songti SC", "STSong", "Georgia", "serif"],
        mono: ['"IBM Plex Mono"', "Menlo", "Consolas", "monospace"],
      },
      boxShadow: {
        composer: "0 1px 2px rgba(12,12,12,0.02), 0 18px 40px -24px rgba(12,12,12,0.18)",
        pill: "0 1px 2px rgba(12,12,12,0.06)",
        float: "0 8px 28px rgba(12,12,12,0.12)",
        panel: "0 0 0 1px rgba(12,12,12,0.02)",
      },
      keyframes: {
        rise: {
          "0%": { transform: "translateY(6px)" },
          "100%": { transform: "translateY(0)" },
        },
        fade: {
          "0%": { opacity: "0" },
          "100%": { opacity: "1" },
        },
        blink: {
          "50%": { opacity: "0" },
        },
        "pulse-soft": {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0.45" },
        },
      },
      animation: {
        rise: "rise .24s ease both",
        fade: "fade .2s ease both",
        blink: "blink 1s step-end infinite",
        "pulse-soft": "pulse-soft 1.6s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};
