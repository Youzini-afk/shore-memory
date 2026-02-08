export const theme = {
  text: '#E8E3D5',
  dim: '#7B7F87',
  accent: '#F6C453', // Yellow/Orange
  accentSoft: '#F2A65A',
  border: '#3C414B',
  userBg: '#2B2F36',
  userText: '#F3EEE0',
  systemText: '#9BA3B2',
  error: '#F97066', // Red
  success: '#7DD3A5', // Green
  info: '#8CC8FF', // Blue-ish
  bg: '#1a1b26', // Dark background

  // UI Specific
  focusBorder: '#F6C453', // Same as accent
  blurBorder: '#565f89', // Lighter gray for better visibility
  selectionBg: '#F6C453',
  selectionFg: '#1a1b26', // Dark text on accent bg
  popupBg: '#24283b', // Slightly lighter than bg

  // Status Colors
  running: '#9ece6a', // Bright Green
  stopped: '#f7768e', // Red
  starting: '#e0af68', // Orange
  unknown: '#565f89' // Grey
}

// Helper to wrap text in blessed tags
export const format = {
  fg: (color: string, text: string) => `{${color}-fg}${text}{/${color}-fg}`,
  bg: (color: string, text: string) => `{${color}-bg}${text}{/${color}-bg}`,
  bold: (text: string) => `{bold}${text}{/bold}`,
  center: (text: string) => `{center}${text}{/center}`,
  right: (text: string) => `{right}${text}{/right}`
}
