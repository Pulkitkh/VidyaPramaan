/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: { sans: ['"Inter Variable"', "system-ui", "-apple-system", '"Segoe UI"', "sans-serif"] },
      colors: {
        navy: { 50: "#eef3fa", 100: "#d7e2f1", 600: "#1d4577", 700: "#14325c", 800: "#0f2645", 900: "#0a1a30" },
        saffron: { 50: "#fdf3e8", 100: "#fbe3c8", 500: "#e07b1a", 600: "#c4650d" },
        ink: { DEFAULT: "#0b0b0b", 2: "#52514e", 3: "#898781" },
        line: "#e1e0d9",
        page: "#f6f7f9",
        status: { good: "#0ca30c", warning: "#fab219", serious: "#ec835a", critical: "#d03b3b", goodtext: "#006300" },
      },
      boxShadow: { card: "0 1px 2px rgba(16,24,40,.06), 0 1px 3px rgba(16,24,40,.08)" },
    },
  },
  plugins: [],
};
