/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        obsidian: {
          DEFAULT: '#0C0C0F',
          darker: '#111118',
          dark: '#13131A',
          light: '#17172A',
          lighter: '#1A1A26',
          border: '#252535',
          'border-muted': '#333345'
        },
        accent: {
          dota: '#FF6B00',
          ai: '#A78BFA',
          'ai-dark': '#200D44',
          win: '#22C55E',
          loss: '#FF4444'
        }
      },
      borderRadius: {
        'xl': '12px',
        'lg': '10px',
        'md': '8px',
        'sm': '7px',
      },
      fontFamily: {
        mono: ['JetBrains Mono', 'monospace'],
        sans: ['Inter', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
