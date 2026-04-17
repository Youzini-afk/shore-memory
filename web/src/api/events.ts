/**
 * WebSocket 事件客户端：
 * - 自动重连（指数退避）
 * - 订阅 / 退订 / type 过滤
 * - 状态上报（disconnected / connecting / open / lagged）
 */

import type { ServerEvent, ServerEventType } from './types'

export type EventsStatus = 'disconnected' | 'connecting' | 'open' | 'error' | 'lagged'

type Listener = (evt: ServerEvent) => void
type StatusListener = (status: EventsStatus) => void

export interface EventsClientOptions {
  /** 绝对或相对 URL，留空则同源 /v1/events */
  url?: string
  /** 最大重连间隔（毫秒） */
  maxBackoffMs?: number
  /** 自动重连 */
  autoReconnect?: boolean
}

export class EventsClient {
  private url: string
  private ws: WebSocket | null = null
  private status: EventsStatus = 'disconnected'
  private listeners = new Set<Listener>()
  private typeListeners = new Map<string, Set<Listener>>()
  private statusListeners = new Set<StatusListener>()
  private backoff = 500
  private maxBackoff: number
  private autoReconnect: boolean
  private shouldRun = false
  private reconnectTimer: number | null = null
  private lastEventAt: number | null = null

  constructor(opts: EventsClientOptions = {}) {
    this.url = opts.url ?? this.defaultUrl()
    this.maxBackoff = opts.maxBackoffMs ?? 15000
    this.autoReconnect = opts.autoReconnect ?? true
  }

  private defaultUrl(): string {
    if (typeof window === 'undefined') return '/v1/events'
    const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
    return `${proto}://${window.location.host}/v1/events`
  }

  connect(): void {
    this.shouldRun = true
    this.open()
  }

  disconnect(): void {
    this.shouldRun = false
    if (this.reconnectTimer !== null) {
      window.clearTimeout(this.reconnectTimer)
      this.reconnectTimer = null
    }
    if (this.ws) {
      this.ws.close(1000, 'client-disconnect')
      this.ws = null
    }
    this.setStatus('disconnected')
  }

  on(listener: Listener): () => void {
    this.listeners.add(listener)
    return () => this.listeners.delete(listener)
  }

  onType(type: ServerEventType, listener: Listener): () => void {
    let set = this.typeListeners.get(type)
    if (!set) {
      set = new Set()
      this.typeListeners.set(type, set)
    }
    set.add(listener)
    return () => {
      set?.delete(listener)
      if (set?.size === 0) this.typeListeners.delete(type)
    }
  }

  onStatus(listener: StatusListener): () => void {
    this.statusListeners.add(listener)
    // 初始同步一次
    listener(this.status)
    return () => this.statusListeners.delete(listener)
  }

  getStatus(): EventsStatus {
    return this.status
  }

  getLastEventAt(): number | null {
    return this.lastEventAt
  }

  private open(): void {
    this.setStatus('connecting')
    try {
      this.ws = new WebSocket(this.url)
    } catch (err) {
      console.warn('[EventsClient] open failed', err)
      this.scheduleReconnect()
      return
    }

    this.ws.onopen = () => {
      this.backoff = 500
      this.setStatus('open')
    }

    this.ws.onmessage = (evt) => {
      this.lastEventAt = Date.now()
      let parsed: ServerEvent | null = null
      try {
        const raw = typeof evt.data === 'string' ? evt.data : ''
        parsed = JSON.parse(raw) as ServerEvent
      } catch {
        return
      }
      if (!parsed || !parsed.type) return
      if (parsed.type === 'lagged') {
        this.setStatus('lagged')
        // lagged 只是提示丢事件，仍继续跑
        setTimeout(() => {
          if (this.status === 'lagged') this.setStatus('open')
        }, 1500)
      }
      this.emit(parsed)
    }

    this.ws.onerror = () => {
      this.setStatus('error')
    }

    this.ws.onclose = () => {
      this.ws = null
      if (this.shouldRun && this.autoReconnect) {
        this.scheduleReconnect()
      } else {
        this.setStatus('disconnected')
      }
    }
  }

  private scheduleReconnect(): void {
    if (!this.shouldRun) return
    if (this.reconnectTimer !== null) return
    const delay = this.backoff
    this.backoff = Math.min(this.backoff * 2, this.maxBackoff)
    this.reconnectTimer = window.setTimeout(() => {
      this.reconnectTimer = null
      this.open()
    }, delay)
  }

  private emit(evt: ServerEvent): void {
    this.listeners.forEach((fn) => {
      try {
        fn(evt)
      } catch (err) {
        console.warn('[EventsClient] listener error', err)
      }
    })
    const typeSet = this.typeListeners.get(evt.type)
    typeSet?.forEach((fn) => {
      try {
        fn(evt)
      } catch (err) {
        console.warn('[EventsClient] type listener error', err)
      }
    })
  }

  private setStatus(status: EventsStatus): void {
    if (this.status === status) return
    this.status = status
    this.statusListeners.forEach((fn) => fn(status))
  }
}

// 单例
let globalClient: EventsClient | null = null
export function getEventsClient(): EventsClient {
  if (!globalClient) {
    globalClient = new EventsClient()
  }
  return globalClient
}
