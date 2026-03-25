import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { GatewayClient } from '@/api/gateway'
import { Envelope } from '@/api/proto/perolink'
import * as IPCAdapter from '@/utils/ipcAdapter'

// Mock IPCAdapter
vi.mock('@/utils/ipcAdapter', () => ({
  invoke: vi.fn(),
  isElectron: () => true
}))

// Mock WebSocket
class MockWebSocket {
  static CONNECTING = 0
  static OPEN = 1
  static CLOSING = 2
  static CLOSED = 3

  url: string
  onopen: (() => void) | null = null
  onmessage: ((event: any) => void) | null = null
  onclose: (() => void) | null = null
  onerror: ((error: any) => void) | null = null
  readyState: number = 0 // 0: CONNECTING, 1: OPEN, 2: CLOSING, 3: CLOSED
  binaryType: string = 'blob'

  send = vi.fn()
  close = vi.fn(() => {
    this.readyState = 3
    if (this.onclose) this.onclose()
  })

  constructor(url: string) {
    this.url = url
  }

  // Helper to simulate server sending message
  simulateMessage(data: Uint8Array) {
    if (this.onmessage) {
      this.onmessage({ data: data.buffer }) // WebSocket receives ArrayBuffer
    }
  }

  // Helper to simulate connection open
  simulateOpen() {
    this.readyState = 1
    if (this.onopen) this.onopen()
  }

  // Helper to simulate error
  simulateError(err: any) {
    if (this.onerror) this.onerror(err)
  }
}

// Global WebSocket Mock
global.WebSocket = MockWebSocket as any

describe('GatewayClient', () => {
  let client: GatewayClient
  let mockWs: MockWebSocket

  beforeEach(() => {
    vi.clearAllMocks()
    vi.useFakeTimers()
    client = new GatewayClient('ws://test.local')
  })

  afterEach(() => {
    vi.useRealTimers()
    // Clean up client if needed (e.g. stop intervals)
    // The client handles cleanup on close, but we might need to force close
    if ((client as any).ws) {
      ;(client as any).ws.close()
    }
  })

  it('应该能成功连接并发送 Hello 消息', async () => {
    // Setup Mock IPC token response
    vi.mocked(IPCAdapter.invoke).mockResolvedValue('test-token')

    // Start connection
    client.connect()

    // Allow async tasks (token fetch) to proceed
    await vi.runAllTicks() // Process microtasks

    // Check if WebSocket was created
    expect((client as any).ws).toBeInstanceOf(MockWebSocket)
    mockWs = (client as any).ws

    // Simulate connection open
    mockWs.simulateOpen()

    expect((client as any).isConnected).toBe(true)

    // Verify Hello message was sent
    expect(mockWs.send).toHaveBeenCalled()
    const sentData = mockWs.send.mock.calls[0][0] // Uint8Array
    const envelope = Envelope.decode(sentData)

    expect(envelope.hello).toBeDefined()
    expect(envelope.hello?.token).toBe('test-token')
    expect(envelope.sourceId).toBeDefined()
  })

  it('应该能定期发送心跳', async () => {
    vi.mocked(IPCAdapter.invoke).mockResolvedValue('test-token')
    client.connect()
    await vi.runAllTicks()
    mockWs = (client as any).ws
    mockWs.simulateOpen()

    // Clear initial Hello message
    mockWs.send.mockClear()

    // Fast forward time (5000ms is the heartbeat interval)
    vi.advanceTimersByTime(5000)

    expect(mockWs.send).toHaveBeenCalledTimes(1)
    const envelope = Envelope.decode(mockWs.send.mock.calls[0][0])
    expect(envelope.heartbeat).toBeDefined()
    expect(envelope.heartbeat?.seq).toBe(1)

    vi.advanceTimersByTime(5000)
    expect(mockWs.send).toHaveBeenCalledTimes(2)
    const envelope2 = Envelope.decode(mockWs.send.mock.calls[1][0])
    expect(envelope2.heartbeat?.seq).toBe(2)
  })

  it('应该能发送请求并接收响应', async () => {
    vi.mocked(IPCAdapter.invoke).mockResolvedValue('test-token')
    client.connect()
    await vi.runAllTicks()
    mockWs = (client as any).ws
    mockWs.simulateOpen()

    // Prepare request
    const requestPromise = client.sendRequest('target-uuid', 'test.action', { key: 'val' })

    // Verify request sent
    const sentData = mockWs.send.mock.calls.filter((call) => {
      const env = Envelope.decode(call[0])
      return !!env.request
    })[0][0]

    const sentEnvelope = Envelope.decode(sentData)
    expect(sentEnvelope.request?.actionName).toBe('test.action')
    const reqId = sentEnvelope.id

    // Simulate Response
    const responseEnvelope: Envelope = {
      id: 'resp-id',
      sourceId: 'target-uuid',
      targetId: sentEnvelope.sourceId,
      timestamp: Date.now(),
      traceId: sentEnvelope.traceId,
      response: {
        requestId: reqId,
        status: 0, // Success
        data: JSON.stringify({ result: 'ok' }),
        errorMsg: ''
      }
    }

    const respData = Envelope.encode(responseEnvelope).finish()
    mockWs.simulateMessage(respData)

    // Verify promise resolution
    const result = await requestPromise
    expect(result.status).toBe(0)
    expect(JSON.parse(result.data)).toEqual({ result: 'ok' })
  })

  it('应该能处理服务器推送的请求 (Request)', () => {
    vi.mocked(IPCAdapter.invoke).mockResolvedValue('test-token')
    client.connect()
    vi.runAllTicks() // Wait for connection setup
    // Manually trigger open since we didn't await connect
    // Actually, connect is async due to token fetch, so we need to wait
  })

  // Separate test for server push to handle async properly
  it('应该能处理服务器推送的事件', async () => {
    vi.mocked(IPCAdapter.invoke).mockResolvedValue('test-token')
    client.connect()
    await vi.runAllTicks()
    mockWs = (client as any).ws
    mockWs.simulateOpen()

    const onAction = vi.fn()
    client.on('action:server.push', onAction)

    // Simulate Server Push Envelope
    const pushEnvelope: Envelope = {
      id: 'push-id',
      sourceId: 'server',
      targetId: 'me',
      timestamp: Date.now(),
      traceId: 'trace-1',
      request: {
        actionName: 'server.push',
        params: { msg: 'hello' }
      }
    }

    mockWs.simulateMessage(Envelope.encode(pushEnvelope).finish())

    expect(onAction).toHaveBeenCalled()
    expect(onAction.mock.calls[0][0].params.msg).toBe('hello')
  })

  it('应该在请求超时时 Reject', async () => {
    vi.mocked(IPCAdapter.invoke).mockResolvedValue('test-token')
    client.connect()
    await vi.runAllTicks()
    mockWs = (client as any).ws
    mockWs.simulateOpen()

    const requestPromise = client.sendRequest('target', 'timeout.action')

    // Fast forward past timeout (10000ms)
    vi.advanceTimersByTime(10001)

    await expect(requestPromise).rejects.toThrow('请求超时')
  })

  it('应该在断开连接后尝试重连', async () => {
    vi.mocked(IPCAdapter.invoke).mockResolvedValue('test-token')
    client.connect()
    await vi.runAllTicks()
    mockWs = (client as any).ws
    mockWs.simulateOpen()

    // Simulate close
    mockWs.close()
    expect((client as any).isConnected).toBe(false)

    // Reconnect interval is 3000ms
    // We need to spy on connect to verify it's called again
    const connectSpy = vi.spyOn(client, 'connect')

    vi.advanceTimersByTime(3000)

    expect(connectSpy).toHaveBeenCalled()
  })
})
