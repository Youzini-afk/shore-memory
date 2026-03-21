import { describe, it, expect, vi } from 'vitest'
import { startGateway, stopGateway, getGatewayLogs } from '@main/services/gateway'

// Mock logger
vi.mock('@main/utils/logger', () => ({
  logger: {
    info: vi.fn(),
    error: vi.fn(),
    warn: vi.fn(),
    debug: vi.fn()
  }
}))

/**
 * Gateway Service Tests
 *
 * Gateway 已嵌入 Python 后端，这些函数现在是空操作 stub。
 * 测试仅验证接口兼容性和基本行为。
 */
describe('Gateway Service (Embedded Stub)', () => {
  it('startGateway 应该是一个无参数的空操作', async () => {
    // 应该可以正常调用且不抛出异常
    await expect(startGateway()).resolves.toBeUndefined()
  })

  it('stopGateway 应该是一个空操作并返回 Promise<void>', async () => {
    await expect(stopGateway()).resolves.toBeUndefined()
  })

  it('getGatewayLogs 应该返回日志数组', async () => {
    // 调用 startGateway 会往 logHistory 推送一条记录
    await startGateway()
    const logs = getGatewayLogs()
    expect(Array.isArray(logs)).toBe(true)
    expect(logs.length).toBeGreaterThan(0)
    expect(logs.some((log: string) => log.includes('已嵌入'))).toBe(true)
  })
})
