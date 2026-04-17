/**
 * 统一 HTTP 客户端：
 * - 注入 x-request-id
 * - 统一错误结构
 * - 支持超时 / AbortController
 * - 可覆盖 base URL（dev 走 proxy，prod 同源）
 */

export class ShoreApiError extends Error {
  status: number
  body?: unknown
  constructor(status: number, message: string, body?: unknown) {
    super(message)
    this.status = status
    this.body = body
    this.name = 'ShoreApiError'
  }
}

export interface RequestOptions extends Omit<RequestInit, 'body'> {
  query?: Record<string, unknown>
  body?: unknown
  timeoutMs?: number
  /** 允许临时覆盖 API base */
  baseUrl?: string
}

function resolveBase(): string {
  // 生产：同源（axum 托管）
  // 开发：经 Vite proxy（也是同源 /v1）
  // 测试 / 自托管可用 window.__SHORE_API__ 覆盖
  const injected = (typeof window !== 'undefined' &&
    (window as unknown as { __SHORE_API__?: string }).__SHORE_API__) as string | undefined
  return injected || import.meta.env.VITE_SHORE_API || ''
}

function buildUrl(path: string, query?: Record<string, unknown>, base?: string): string {
  const prefix = base ?? resolveBase()
  const sep = path.startsWith('/') ? '' : '/'
  const absolute = `${prefix}${sep}${path}`
  if (!query) return absolute
  const params = new URLSearchParams()
  for (const [k, v] of Object.entries(query)) {
    if (v === undefined || v === null) continue
    if (Array.isArray(v)) {
      for (const item of v) params.append(k, String(item))
    } else {
      params.append(k, String(v))
    }
  }
  const qs = params.toString()
  if (!qs) return absolute
  return `${absolute}${absolute.includes('?') ? '&' : '?'}${qs}`
}

function genRequestId(): string {
  // crypto.randomUUID 已在现代浏览器 + Node 18+ 可用
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return (crypto as Crypto).randomUUID()
  }
  return `r-${Math.random().toString(36).slice(2)}-${Date.now().toString(36)}`
}

export async function apiRequest<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const { query, body, timeoutMs = 15000, baseUrl, headers, method, ...rest } = opts

  const url = buildUrl(path, query, baseUrl)
  const reqId = genRequestId()

  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort('timeout'), timeoutMs)

  const finalHeaders = new Headers(headers || {})
  finalHeaders.set('x-request-id', reqId)
  if (!finalHeaders.has('accept')) finalHeaders.set('accept', 'application/json')

  let serializedBody: BodyInit | undefined
  if (body !== undefined && body !== null) {
    if (typeof body === 'string' || body instanceof FormData || body instanceof Blob) {
      serializedBody = body as BodyInit
    } else {
      serializedBody = JSON.stringify(body)
      if (!finalHeaders.has('content-type')) finalHeaders.set('content-type', 'application/json')
    }
  }

  let res: Response
  try {
    res = await fetch(url, {
      ...rest,
      method: method ?? (body ? 'POST' : 'GET'),
      headers: finalHeaders,
      body: serializedBody,
      signal: controller.signal
    })
  } catch (err) {
    clearTimeout(timer)
    if ((err as Error).name === 'AbortError') {
      throw new ShoreApiError(0, `请求超时: ${path}`)
    }
    throw new ShoreApiError(0, `网络错误: ${(err as Error).message}`)
  }
  clearTimeout(timer)

  const contentType = res.headers.get('content-type') || ''
  const isJson = contentType.includes('application/json')
  const parsed: unknown = isJson ? await res.json().catch(() => null) : await res.text()

  if (!res.ok) {
    const message =
      (isJson && parsed && typeof parsed === 'object' && 'error' in parsed
        ? String((parsed as { error: unknown }).error)
        : typeof parsed === 'string'
          ? parsed
          : res.statusText) || `HTTP ${res.status}`
    throw new ShoreApiError(res.status, message, parsed)
  }

  return parsed as T
}

export const api = {
  get: <T>(path: string, opts: Omit<RequestOptions, 'body' | 'method'> = {}) =>
    apiRequest<T>(path, { ...opts, method: 'GET' }),
  post: <T>(path: string, body?: unknown, opts: Omit<RequestOptions, 'body' | 'method'> = {}) =>
    apiRequest<T>(path, { ...opts, method: 'POST', body }),
  patch: <T>(path: string, body?: unknown, opts: Omit<RequestOptions, 'body' | 'method'> = {}) =>
    apiRequest<T>(path, { ...opts, method: 'PATCH', body }),
  delete: <T>(path: string, opts: Omit<RequestOptions, 'body' | 'method'> = {}) =>
    apiRequest<T>(path, { ...opts, method: 'DELETE' })
}
