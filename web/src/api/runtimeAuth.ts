export type ApiKeySource = 'session' | 'local' | 'window' | 'env' | 'none'

export interface ApiKeyState {
  key?: string
  source: ApiKeySource
}

const LOCAL_STORAGE_KEY = 'shore:api-key'
const SESSION_STORAGE_KEY = 'shore:api-key:session'

type Listener = (state: ApiKeyState) => void

const listeners = new Set<Listener>()

function normalize(value: string | null | undefined): string | undefined {
  const trimmed = value?.trim()
  return trimmed ? trimmed : undefined
}

function readWindowApiKey(): string | undefined {
  if (typeof window === 'undefined') return undefined
  return normalize((window as Window & { __SHORE_API_KEY__?: string }).__SHORE_API_KEY__)
}

function readEnvApiKey(): string | undefined {
  return normalize(import.meta.env.VITE_SHORE_API_KEY)
}

function readStorage(storage: Storage | undefined, key: string): string | undefined {
  if (!storage) return undefined
  try {
    return normalize(storage.getItem(key))
  } catch {
    return undefined
  }
}

function writeStorage(storage: Storage | undefined, key: string, value: string | null) {
  if (!storage) return
  try {
    if (value === null) {
      storage.removeItem(key)
    } else {
      storage.setItem(key, value)
    }
  } catch {
    return
  }
}

export function getApiKeyState(): ApiKeyState {
  if (typeof window !== 'undefined') {
    const sessionKey = readStorage(window.sessionStorage, SESSION_STORAGE_KEY)
    if (sessionKey) return { key: sessionKey, source: 'session' }
    const localKey = readStorage(window.localStorage, LOCAL_STORAGE_KEY)
    if (localKey) return { key: localKey, source: 'local' }
  }

  const windowKey = readWindowApiKey()
  if (windowKey) return { key: windowKey, source: 'window' }

  const envKey = readEnvApiKey()
  if (envKey) return { key: envKey, source: 'env' }

  return { source: 'none' }
}

export function getApiKey(): string | undefined {
  return getApiKeyState().key
}

export function setStoredApiKey(value: string, remember: boolean): ApiKeyState {
  const normalized = normalize(value)
  if (!normalized || typeof window === 'undefined') {
    return clearStoredApiKey()
  }

  writeStorage(window.sessionStorage, SESSION_STORAGE_KEY, remember ? null : normalized)
  writeStorage(window.localStorage, LOCAL_STORAGE_KEY, remember ? normalized : null)
  const next = getApiKeyState()
  listeners.forEach((listener) => listener(next))
  return next
}

export function clearStoredApiKey(): ApiKeyState {
  if (typeof window !== 'undefined') {
    writeStorage(window.sessionStorage, SESSION_STORAGE_KEY, null)
    writeStorage(window.localStorage, LOCAL_STORAGE_KEY, null)
  }
  const next = getApiKeyState()
  listeners.forEach((listener) => listener(next))
  return next
}

export function subscribeApiKey(listener: Listener): () => void {
  listeners.add(listener)
  return () => listeners.delete(listener)
}
