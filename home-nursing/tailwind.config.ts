import type { Config } from "tailwindcss";

export default {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: { 50: "#eef8f6", 100: "#d5eee9", 500: "#1f8a78", 600: "#17705f", 700: "#125a4c", 900: "#0b3a31" },
        ink: { 500: "#4b5563", 700: "#1f2937", 900: "#0f172a" },
        alert: { 50: "#fef2f2", 600: "#b91c1c" },
      },
      fontFamily: { sans: ["Inter", "system-ui", "sans-serif"] },
    },
  },
  plugins: [],
} satisfies Config;
