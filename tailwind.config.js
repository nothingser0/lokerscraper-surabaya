/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./api/**/*.py",
    "./static/**/*.js"
  ],
  theme: {
    extend: {
      fontFamily: { sans: ['"Plus Jakarta Sans"', 'sans-serif'] },
      colors: {
        cream: '#F4F4F0',
        ink: '#111111',
        limepill: '#D4F542',
        softgray: '#E6E6E1',
      }
    }
  },
  plugins: [],
}
