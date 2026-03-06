export const AGENT_NAME: string = 'Peropero'
export const AGENT_AVATAR_TEXT: string = 'P'
export const APP_TITLE: string = '萌动链接：PeroperoChat！'
export const API_BASE: string =
  typeof window !== 'undefined' && window.electron ? 'http://localhost:9120/api' : '/api'
