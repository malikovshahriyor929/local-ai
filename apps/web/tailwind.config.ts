import type { Config } from "tailwindcss";
export default { content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"], theme: { extend: { colors: { background: "hsl(var(--background))", foreground: "hsl(var(--foreground))", card: "hsl(var(--card))", muted: "hsl(var(--muted))", border: "hsl(var(--border))", primary: "hsl(var(--primary))" } } }, plugins: [] } satisfies Config;
