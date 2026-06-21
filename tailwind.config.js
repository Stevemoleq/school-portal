/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: 'class',
  content: [
    './school_portal/templates/**/*.html',
    './school_portal/apps/**/templates/**/*.html',
    './school_portal/static/js/**/*.js',
  ],
  theme: {
    extend: {
      fontFamily: { sans: ['Inter', 'system-ui', 'sans-serif'] },
      colors: {
        brand: {
          50: '#eef2ff', 100: '#e0e7ff', 200: '#c7d2fe', 300: '#a5b4fc',
          400: '#818cf8', 500: '#6366f1', 600: '#4f46e5', 700: '#4338ca',
          800: '#3730a3', 900: '#312e81', 950: '#1e1b4b',
        },
        surface: {
          50: '#f8fafc', 100: '#f1f5f9', 200: '#e2e8f0', 300: '#cbd5e1',
          400: '#94a3b8', 500: '#64748b', 600: '#475569', 700: '#334155',
          800: '#1e293b', 900: '#0f172a', 950: '#020617',
        },
        scholarly: {
          50: '#eef2ff', 100: '#dbe4ff', 200: '#b9c8ff',
          300: '#8aa2ff', 400: '#5e7aff', 500: '#3a55f5',
          600: '#00288e', primary: '#00288e',
          'primary-container': '#1e40af',
          secondary: '#4e45d5',
          'secondary-container': '#1e1b4b',
          on: '#ffffff', 'on-variant': '#4a4a4f',
        }
      }
    }
  },
  plugins: [],
}
