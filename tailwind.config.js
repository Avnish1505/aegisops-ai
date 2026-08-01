/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      boxShadow: {
        panel: '0 16px 40px rgba(0, 0, 0, 0.22)',
      },
      keyframes: {
        beacon: {
          '0%, 100%': { opacity: '0.85', transform: 'scale(0.88)' },
          '50%': { opacity: '0.15', transform: 'scale(1.25)' },
        },
      },
      animation: {
        beacon: 'beacon 1.7s ease-in-out infinite',
      },
    },
  },
  plugins: [],
}
