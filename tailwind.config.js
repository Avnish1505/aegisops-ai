/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        // Warm cream application surface. `sev.*` mirrors the fixed hex values
        // used directly in Grid.tsx SVG fills (SVG attributes can't read Tailwind
        // classes) — keep both in sync if these change.
        paper: {
          DEFAULT: '#faf6ee',
          raised: '#fffdf8',
          sunken: '#f1ead9',
        },
        ink: {
          50: '#f7f3ea',
          100: '#efe7d6',
          200: '#e2d7bf',
          300: '#cdbfa0',
          400: '#a89572',
          500: '#7d6a49',
          600: '#6b5b41',
          700: '#4a3f2c',
          800: '#33291b',
          900: '#241d13',
        },
        accent: {
          100: '#fbe3cd',
          300: '#d99a5c',
          600: '#93481f',
          700: '#7a3a1a',
          800: '#5c2c14',
        },
        sev: {
          critical: '#a13a24',
          high: '#95541a',
          medium: '#8a6a12',
          low: '#2f5478',
        },
        status: {
          available: '#3f6b46',
          blocked: '#a13a24',
          review: '#7a3a1a',
        },
      },
      boxShadow: {
        // Reserved for the rare element that truly needs to lift off the page
        // (e.g. the legend overlaid on the grid). Panels rely on borders, not shadow.
        soft: '0 1px 2px rgba(36, 29, 19, 0.06), 0 1px 1px rgba(36, 29, 19, 0.04)',
      },
      keyframes: {
        beacon: {
          '0%, 100%': { opacity: '0.9', transform: 'scale(0.94)' },
          '50%': { opacity: '0.35', transform: 'scale(1.12)' },
        },
      },
      animation: {
        beacon: 'beacon 2s ease-in-out infinite',
      },
    },
  },
  plugins: [],
}
