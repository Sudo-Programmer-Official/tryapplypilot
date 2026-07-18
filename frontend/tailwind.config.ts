import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{vue,ts}"],
  theme: {
    extend: {
      colors: {
        canvas: "#f5efe3",
        ink: "#13212b",
        brass: "#a46b1f",
        clay: "#d97845",
        moss: "#2f6b5c",
        smoke: "#e6decf",
      },
      fontFamily: {
        display: ['"Space Grotesk"', "ui-sans-serif", "system-ui"],
        sans: ['"IBM Plex Sans"', "ui-sans-serif", "system-ui"],
      },
      boxShadow: {
        atmosphere: "0 24px 80px rgba(19, 33, 43, 0.12)",
      },
    },
  },
  plugins: [],
} satisfies Config;

