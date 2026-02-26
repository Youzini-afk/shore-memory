import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import path from 'path'
import { EventEmitter } from 'events'
import * as fs from 'fs-extra'
import * as child_process from 'child_process'
import { startGateway, stopGateway, getGatewayLogs } from '@main/services/gateway'
import { logger } from '@main/utils/logger'
import { appEvents } from '@main/events'

// Mock environment
vi.mock('@main/utils/env', () => ({
  isPackaged: false,
  paths: {
    resources: '/mock/resources',
    userData: '/mock/userData'
  }
}))

// Mock logger
vi.mock('@main/utils/logger', () => ({
  logger: {
    info: vi.fn(),
    error: vi.fn(),
    warn: vi.fn(),
    debug: vi.fn()
  }
}))

// Mock fs-extra with shared mock functions for named and default exports
vi.mock('fs-extra', () => {
  const pathExists = vi.fn()
  const ensureDir = vi.fn()
  const remove = vi.fn()
  return {
    pathExists,
    ensureDir,
    remove,
    default: {
      pathExists,
      ensureDir,
      remove
    }
  }
})

// Mock child_process with shared mock functions
vi.mock('child_process', () => {
  const spawn = vi.fn()
  return {
    spawn,
    default: {
      spawn
    }
  }
})

// Mock tree-kill
vi.mock('tree-kill', () => ({
  default: vi.fn((pid, signal, cb) => cb && cb(null))
}))

describe('Gateway Service', () => {
  let mockWindow: any
  let mockProcess: any

  beforeEach(() => {
    vi.clearAllMocks()

    // Setup Mock Window
    mockWindow = {
      isDestroyed: () => false,
      webContents: {
        send: vi.fn()
      }
    }

    // Setup Mock Child Process
    mockProcess = new EventEmitter()
    mockProcess.pid = 12345
    mockProcess.stdout = new EventEmitter()
    mockProcess.stderr = new EventEmitter()
    mockProcess.kill = vi.fn()
    mockProcess.exitCode = null

    vi.mocked(child_process.spawn).mockReturnValue(mockProcess as any)
  })

  afterEach(() => {
    stopGateway()
  })

  it('应该能正确查找到 Gateway 路径并启动', async () => {
    // Mock fs.pathExists to find gateway at first dev path
    vi.mocked(fs.pathExists).mockImplementation(async (p: string) => {
      // Normalize path for comparison to avoid slash issues
      const normalizedP = path.normalize(p)
      // Simulate gateway exe exists (check for both dev paths and potential fallbacks)
      if (
        normalizedP.includes('gateway') &&
        (normalizedP.endsWith('exe') || !path.extname(normalizedP))
      )
        return true

      // Simulate token file creation (eventually)
      if (normalizedP.includes('gateway_token.json')) return true
      return false
    })

    // Ensure mockProcess is clean
    mockProcess.exitCode = null

    await startGateway(mockWindow)

    expect(child_process.spawn).toHaveBeenCalled()
    const spawnArgs = vi.mocked(child_process.spawn).mock.calls[0]
    // Check if path contains gateway executable
    expect(spawnArgs[0]).toMatch(/gateway(\.exe)?$/)
    // Check env vars
    expect(spawnArgs[2].env?.GATEWAY_TOKEN_PATH).toContain('gateway_token.json')
  })

  it('应该在 Gateway 启动失败时抛出错误', async () => {
    vi.useFakeTimers()

    // Mock fs.pathExists to find gateway but NOT token
    vi.mocked(fs.pathExists).mockImplementation(async (p: string) => {
      const normalizedP = path.normalize(p)
      if (
        normalizedP.includes('gateway') &&
        (normalizedP.endsWith('exe') || !path.extname(normalizedP))
      )
        return true
      if (normalizedP.includes('gateway_token.json')) return false // Token never created
      return false
    })

    // Simulate process exit
    mockProcess.exitCode = 1

    // Start gateway (don't await yet)
    const startPromise = startGateway(mockWindow)

    // Catch the error to prevent unhandled rejection warning, but we still need to verify it
    startPromise.catch(() => {})

    // Fast-forward time to skip the 5s retry loop
    await vi.advanceTimersByTimeAsync(6000)

    // Expect error due to timeout/failure to create token
    await expect(startPromise).rejects.toThrow(/Gateway 启动超时或失败/)

    vi.useRealTimers()
  })

  it('应该能正确处理 stdout 日志', async () => {
    vi.mocked(fs.pathExists).mockImplementation(async (p: string) => {
      const normalizedP = path.normalize(p)
      if (
        normalizedP.includes('gateway') &&
        (normalizedP.endsWith('exe') || !path.extname(normalizedP))
      )
        return true
      if (normalizedP.includes('gateway_token.json')) return true
      return false
    })

    // Ensure mockProcess is clean
    mockProcess.exitCode = null

    await startGateway(mockWindow)

    // Emit stdout data
    mockProcess.stdout.emit('data', Buffer.from('Info: Server started\n'))

    expect(logger.info).toHaveBeenCalledWith('Gateway', 'Info: Server started')

    // Verify log history
    const logs = getGatewayLogs()
    expect(logs).toContain('Info: Server started')
  })

  it('应该能正确区分 stderr 中的错误和普通日志', async () => {
    vi.mocked(fs.pathExists).mockImplementation(async (p: string) => {
      const normalizedP = path.normalize(p)
      if (
        normalizedP.includes('gateway') &&
        (normalizedP.endsWith('exe') || !path.extname(normalizedP))
      )
        return true
      if (normalizedP.includes('gateway_token.json')) return true
      return false
    })

    // Ensure mockProcess is clean
    mockProcess.exitCode = null

    await startGateway(mockWindow)

    // Emit normal stderr (Go log)
    mockProcess.stderr.emit('data', Buffer.from('2024/01/01 12:00:00 Normal log\n'))
    expect(logger.info).toHaveBeenCalledWith('Gateway', '2024/01/01 12:00:00 Normal log')

    // Emit error stderr
    mockProcess.stderr.emit('data', Buffer.from('2024/01/01 12:00:00 [ERROR] Something failed\n'))
    expect(logger.error).toHaveBeenCalledWith(
      'Gateway',
      '2024/01/01 12:00:00 [ERROR] Something failed'
    )
  })

  it('应该在 Gateway 意外退出时触发 crash 事件', async () => {
    vi.mocked(fs.pathExists).mockImplementation(async (p: string) => {
      const normalizedP = path.normalize(p)
      if (
        normalizedP.includes('gateway') &&
        (normalizedP.endsWith('exe') || !path.extname(normalizedP))
      )
        return true
      if (normalizedP.includes('gateway_token.json')) return true
      return false
    })

    // Ensure mockProcess is clean
    mockProcess.exitCode = null

    const emitSpy = vi.spyOn(appEvents, 'emit')

    await startGateway(mockWindow)

    // Simulate unexpected close
    mockProcess.emit('close', 1)

    expect(logger.error).toHaveBeenCalledWith('Gateway', 'Gateway 意外崩溃，触发联动停止')
    expect(emitSpy).toHaveBeenCalledWith('gateway-crashed', 1)
  })

  it('stopGateway 应该能正常停止进程', async () => {
    vi.mocked(fs.pathExists).mockImplementation(async (p: string) => {
      const normalizedP = path.normalize(p)
      if (
        normalizedP.includes('gateway') &&
        (normalizedP.endsWith('exe') || !path.extname(normalizedP))
      )
        return true
      if (normalizedP.includes('gateway_token.json')) return true
      return false
    })

    // Ensure mockProcess is clean
    mockProcess.exitCode = null

    await startGateway(mockWindow)

    stopGateway()

    // Wait for tree-kill callback (mocked)
    // Since we mocked tree-kill, we can just check if process was set to null
    // But verify if treeKill was called
    const treeKill = await import('tree-kill')
    expect(treeKill.default).toHaveBeenCalledWith(12345, 'SIGKILL', expect.any(Function))

    // Verify gatewayProcess is null (we can't access it directly, but startGateway should allow starting again)
    // If we call startGateway again, it should spawn a new process
    vi.mocked(child_process.spawn).mockClear()
    await startGateway(mockWindow)
    expect(child_process.spawn).toHaveBeenCalled()
  })
})
