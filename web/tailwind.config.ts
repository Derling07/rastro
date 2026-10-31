import type { Config } from "tailwindcss";

export default {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        ink: "var(--ink)",
        panel: "var(--panel)",
        line: "var(--line)",
        muted: "var(--muted)",
        pack: "var(--pack)",
        alta: "var(--alta)",
      },
      fontFamily: {
        sans: ["var(--font-source)", "Source Sans 3", "system-ui", "sans-serif"],
        display: ["var(--font-note)", "Fraunces", "Georgia", "serif"],
      },
      fontSize: {
        hero: ["120px", { lineHeight: "1", fontWeight: "700" }],
      },
    },
  },
  plugins: [],
} satisfies Config;
