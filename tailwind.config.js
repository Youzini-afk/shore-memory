/** @type {import('tailwindcss').Config} */
export default {
  content: [
    './index.html',
    './src/**/*.{vue,js,ts,jsx,tsx}',
    '!./src/api/**/*.{js,ts}',
    '!**/node_modules/**'
  ],
  theme: {
    extend: {
      colors: {
        moe: {
          sky: '#A7D8F0',
          pink: '#F9A8D4',
          purple: '#C084FC',
          yellow: '#FDE047',
          cocoa: '#2D1B1E',
          cloud: '#FFFFFF'
        }
      },
      backdropBlur: {
        xs: '2px'
      }
    }
  },
  plugins: []
}
