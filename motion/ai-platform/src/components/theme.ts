// One place for colours, type and canvas size, shared by every clip.

export const theme = {
  width: 1080,
  height: 1350, // 4:5, LinkedIn feed
  fps: 30,

  bg: '#0a0f15',
  bgGlow: '#0f1a26',
  grid: '#1b2633',
  panel: '#101923',
  panelHi: '#13202c',
  text: '#f1f5f9',
  muted: '#94a3b8',
  faint: '#475569',
  neutral: '#cbd5e1', // humans and third parties (GitHub)

  // Accents: one per "half". For the agent factory clip:
  // cyan = what runs today, amber = the v2 roadmap.
  cyan: '#22d3ee',
  amber: '#f5a524',

  fonts: {
    // Install JetBrains Mono for the intended look; the others are fallbacks.
    mono: '"JetBrains Mono", "DejaVu Sans Mono", Menlo, monospace',
    sans: 'Inter, "Helvetica Neue", Arial, sans-serif',
  },
};

export type Theme = typeof theme;
