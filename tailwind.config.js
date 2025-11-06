/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./templates/**/*.html",
    "./invoice_processor/templates/**/*.html",
    "./static/js/**/*.js",
    "./invoice_processor/static/**/*.js",
  ],
  theme: {
    extend: {
      colors: {
        'primary-bg': '#F5F7FA',
        'card-bg': '#FFFFFF',
        'primary-accent': '#5B8DEF',
        'secondary-accent': '#8B7FE8',
        'success-accent': '#4ECDC4',
        'success': '#10B981',
        'warning': '#F59E0B',
        'error': '#EF4444',
        'info': '#3B82F6',
      },
      fontFamily: {
        'sans': ['Inter', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [],
}