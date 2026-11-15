import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          50: "#eef4ff",
          100: "#dde7fd",
          500: "#3b5bdb",
          600: "#2f4ac4",
          700: "#283da3",
        },
      },
    },
  },
  plugins: [],
};
export default config;
