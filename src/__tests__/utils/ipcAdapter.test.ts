import { describe, it, expect, vi, beforeEach } from 'vitest'
import * as IPCAdapter from '@/utils/ipcAdapter'

// 模拟 window.electron
const mockElectron = {
  invoke: vi.fn(),
  on: vi.fn()
}

// 设置全局模拟
vi.stubGlobal('window', {
  electron: mockElectron
})

describe('IPCAdapter', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('should call electron invoke when sending message', async () => {
    const channel = 'test-channel'
    const data = { key: 'value' }
    mockElectron.invoke.mockResolvedValue('response')

    // 模拟 isElectron 返回 true
    vi.spyOn(IPCAdapter, 'isElectron').mockReturnValue(true)

    const result = await IPCAdapter.invoke(channel, data)

    expect(mockElectron.invoke).toHaveBeenCalledWith(channel, data)
    expect(result).toBe('response')
  })

  // 如果需要，为浏览器模式添加更多测试
})
