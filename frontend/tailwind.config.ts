import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#17202a",
        panel: "#f7f9fb",
        line: "#d9e2ec",
        risk: "#c2410c",
        safe: "#15803d",
        signal: "#0f766e"
      }
    }
  },
  plugins: []
} satisfies Config;
