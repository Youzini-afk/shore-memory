import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import TerminalPanel from '@/components/terminal/TerminalPanel.vue'
import { listen, invoke } from '@/utils/ipcAdapter'
import { nextTick } from 'vue'

// 模拟 ipcAdapter
vi.mock('@/utils/ipcAdapter', () => ({
  listen: vi.fn(),
  invoke: vi.fn()
}))

// 模拟 Element Plus 组件
const ElIcon = { template: '<span class="el-icon"><slot /></span>' }
const ElCheckbox = {
  template:
    '<input type="checkbox" :checked="modelValue" @change="$emit(\'update:modelValue\', $event.target.checked)" />',
  props: ['modelValue', 'label', 'size']
}
const ElButton = {
  template: '<button class="el-button" @click="$emit(\'click\')"><slot /></button>'
}

// 模拟图标组件
const Monitor = { template: '<svg>Monitor</svg>' }
const Delete = { template: '<svg>Delete</svg>' }

describe('TerminalPanel.vue', () => {
  let wrapper: any
  let listeners: Record<string, Function> = {}

  beforeEach(() => {
    vi.useFakeTimers()
    vi.clearAllMocks()
    listeners = {}

    // 默认 mock 实现
    ;(invoke as any).mockResolvedValue([])
    ;(listen as any).mockImplementation((event: string, callback: Function) => {
      listeners[event] = callback
      return Promise.resolve(() => {}) // 返回 unlisten 函数
    })
  })

  afterEach(() => {
    vi.useRealTimers()
    if (wrapper) wrapper.unmount()
  })

  const mountComponent = () => {
    return mount(TerminalPanel, {
      global: {
        components: {
          'el-icon': ElIcon,
          'el-checkbox': ElCheckbox,
          'el-button': ElButton,
          Monitor,
          Delete
        }
      }
    })
  }

  it('渲染正常', async () => {
    wrapper = mountComponent()
    await flushPromises()

    expect(wrapper.exists()).toBe(true)
    expect(wrapper.find('.terminal-header').exists()).toBe(true)
    expect(wrapper.find('.terminal-content').exists()).toBe(true)
    expect(wrapper.text()).toContain('实时终端')
  })

  it('应该加载历史日志', async () => {
    const historyLogs = ['[INFO] System started', '[WARN] Low memory']
    ;(invoke as any).mockResolvedValue(historyLogs)

    wrapper = mountComponent()
    await flushPromises() // 等待 onMounted 中的异步操作

    // 检查是否渲染了日志
    const logLines = wrapper.findAll('.log-line')
    expect(logLines.length).toBe(2)
    expect(logLines[0].text()).toContain('System started')
    expect(logLines[1].text()).toContain('Low memory')
  })

  it('监听 backend-log 并添加日志', async () => {
    wrapper = mountComponent()
    await flushPromises()

    // 确保监听器已注册
    expect(listeners['backend-log']).toBeDefined()

    // 模拟收到后端日志事件
    const callback = listeners['backend-log']
    callback({ payload: '[ERROR] Connection failed' })

    // 触发定时器更新 (addLog 内部有 setTimeout)
    vi.advanceTimersByTime(200)
    await nextTick()

    const logLines = wrapper.findAll('.log-line')
    expect(logLines.length).toBe(1)
    expect(logLines[0].text()).toContain('Connection failed')
    expect(logLines[0].classes()).toContain('error') // 检查类型推断是否正确
  })

  it('点击清空按钮应该清空日志', async () => {
    // 预先加载一些日志
    ;(invoke as any).mockResolvedValue(['Log 1', 'Log 2'])

    wrapper = mountComponent()
    await flushPromises()

    expect(wrapper.findAll('.log-line').length).toBe(2)

    // 点击清空按钮
    const clearBtn = wrapper.find('.el-button')
    await clearBtn.trigger('click')

    expect(wrapper.findAll('.log-line').length).toBe(0)
  })

  it('应该能拦截控制台日志 (Hook Console)', async () => {
    wrapper = mountComponent()
    await flushPromises()

    // 监听 console.log
    const consoleSpy = vi.spyOn(console, 'log')

    // 触发 console.log
    console.log('Frontend log message')

    // 应该被拦截并添加到界面
    vi.advanceTimersByTime(200)
    await nextTick()

    const logLines = wrapper.findAll('.log-line')
    const frontendLog = logLines.find((l: any) => l.text().includes('Frontend log message'))

    expect(frontendLog).toBeDefined()
    expect(frontendLog?.text()).toContain('[frontend]') // 检查来源标记
  })
})
