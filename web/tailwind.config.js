/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{vue,ts,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        // Shore Memory Console tokens（和 design/tokens.css 对齐）
        shore: {
          bg: '#0B0B12',
          surface: '#11121A',
          card: '#161827',
          elev: '#191A26',
          hover: '#14151F',
          selected: '#1A1B28',
          line: '#1F2130',
          border: '#242636'
        },
        ink: {
          0: '#FFFFFF',
          1: '#EDEEF7',
          2: '#C2C6D9',
          3: '#9097AB',
          4: '#666B80',
          5: '#414657',
          6: '#2A2D3A'
        },
        accent: {
          DEFAULT: '#7C5CFF',
          hi: '#8E7BFF',
          lo: '#6A4DFF',
          soft: 'rgba(124,92,255,0.12)',
          ring: 'rgba(124,92,255,0.35)'
        },
        state: {
          active: '#10B981',
          superseded: '#7C5CFF',
          invalidated: '#F43F5E',
          archived: '#64748B'
        },
        sig: {
          blue: '#38BDF8',
          amber: '#F59E0B'
        }
      },
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        display: [
          'Geist',
          'Inter',
          'ui-sans-serif',
          'system-ui',
          'sans-serif'
        ],
        mono: ['Geist Mono', 'JetBrains Mono', 'ui-monospace', 'monospace']
      },
      borderRadius: {
        card: '16px',
        panel: '12px',
        btn: '10px',
        pill: '9999px'
      },
      boxShadow: {
        'accent-sm': '0 4px 14px rgba(124,92,255,0.25)',
        accent: '0 6px 20px rgba(124,92,255,0.35)',
        'accent-lg': '0 10px 32px rgba(124,92,255,0.45)',
        'halo-selected': '0 0 0 2px rgba(124,92,255,0.45), 0 0 24px rgba(124,92,255,0.55)'
      },
      transitionTimingFunction: {
        shore: 'cubic-bezier(0.2, 0.8, 0.2, 1)'
      },
      transitionDuration: {
        '240': '240ms'
      }
    }
  },
  plugins: []
}
