import type { Config } from 'tailwindcss'

export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        're-red': '#8B0000',
        're-red-bright': '#CC0000',
        're-dark': '#0a0a0a',
        're-surface': '#141414',
        're-surface-2': '#1e1e1e',
        're-border': '#2a2a2a',
        're-text': '#d4d4d4',
        're-muted': '#6b6b6b',
      },
      fontFamily: {
        mono: ['JetBrains Mono', 'Courier New', 'monospace'],
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [],
} satisfies Config
