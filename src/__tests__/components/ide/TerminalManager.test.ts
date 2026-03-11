import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount } from '@vue/test-utils'
import TerminalManager from '@/components/ide/TerminalManager.vue'
import * as IPCAdapter from '@/utils/ipcAdapter'

// Mock PixelIcon
vi.mock('@/components/ui/PixelIcon.vue', () => ({
  default: {
    name: 'PixelIcon',
    props: ['name', 'size', 'animation'],
    template: '<span :class="\'icon-\' + name" />'
  }
}))

// Mock Lucide icons (if any are still used elsewhere)
vi.mock('lucide-vue-next', () => ({
  Terminal: { template: '<span class="icon-terminal" />' },
  ChevronDown: { template: '<span class="icon-chevron-down" />' },
  ChevronUp: { template: '<span class="icon-chevron-up" />' },
  Square: { template: '<span class="icon-square" />' }
}))

describe('TerminalManager.vue', () => {
  let mockListenCallback: (event: any) => void
  let mockUnlisten: any

  beforeEach(() => {
    mockUnlisten = vi.fn()
    // Mock listen function to capture the callback
    vi.spyOn(IPCAdapter, 'listen').mockImplementation((event, callback) => {
      if (event === 'ws-message') {
        mockListenCallback = callback
      }
      return Promise.resolve(mockUnlisten)
    })
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  const createWrapper = () => {
    return mount(TerminalManager, {
      attachTo: document.body // 为了测试滚动和样式
    })
  }

  it('应该在挂载时开始监听 ws-message', async () => {
    const wrapper = createWrapper()
    await wrapper.vm.$nextTick()
    expect(IPCAdapter.listen).toHaveBeenCalledWith('ws-message', expect.any(Function))
    wrapper.unmount()
  })

  it('收到 terminal_init 消息时应该创建新终端', async () => {
    const wrapper = createWrapper()
    await wrapper.vm.$nextTick()

    // 模拟收到初始化消息
    mockListenCallback({
      payload: {
        type: 'terminal_init',
        pid: 123,
        command: 'npm run dev'
      }
    })
    await wrapper.vm.$nextTick()

    // 验证终端列表
    // @ts-ignore
    expect(wrapper.vm.terminals).toHaveLength(1)
    // @ts-ignore
    expect(wrapper.vm.terminals[0]).toEqual({
      pid: 123,
      command: 'npm run dev',
      output: '',
      active: true,
      exitCode: null
    })

    // 验证自动展开和切换
    // @ts-ignore
    expect(wrapper.vm.isCollapsed).toBe(false)
    // @ts-ignore
    expect(wrapper.vm.activePid).toBe(123)

    wrapper.unmount()
  })

  it('收到 terminal_output 消息时应该更新输出', async () => {
    const wrapper = createWrapper()
    await wrapper.vm.$nextTick()

    // 初始化终端
    mockListenCallback({
      payload: { type: 'terminal_init', pid: 123, command: 'echo hello' }
    })
    await wrapper.vm.$nextTick()

    // 发送输出
    mockListenCallback({
      payload: { type: 'terminal_output', pid: 123, content: 'Hello World\n' }
    })
    await wrapper.vm.$nextTick()

    // 验证输出内容
    // @ts-ignore
    expect(wrapper.vm.terminals[0].output).toBe('Hello World\n')

    // 验证 DOM 更新
    const outputEl = wrapper.find('.whitespace-pre-wrap')
    expect(outputEl.text()).toContain('Hello World')

    wrapper.unmount()
  })

  it('收到 terminal_exit 消息时应该更新状态', async () => {
    const wrapper = createWrapper()
    await wrapper.vm.$nextTick()

    // 初始化终端
    mockListenCallback({
      payload: { type: 'terminal_init', pid: 123, command: 'ls' }
    })
    await wrapper.vm.$nextTick()

    // 发送退出消息
    mockListenCallback({
      payload: { type: 'terminal_exit', pid: 123, exit_code: 0 }
    })
    await wrapper.vm.$nextTick()

    // 验证状态
    // @ts-ignore
    const term = wrapper.vm.terminals[0]
    expect(term.active).toBe(false)
    expect(term.exitCode).toBe(0)

    // 验证 UI 显示退出代码
    expect(wrapper.text()).toContain('进程已结束，退出代码 0')

    wrapper.unmount()
  })

  it('切换终端应该显示对应的内容', async () => {
    const wrapper = createWrapper()
    await wrapper.vm.$nextTick()

    // 创建两个终端
    mockListenCallback({
      payload: { type: 'terminal_init', pid: 1, command: 'cmd1' }
    })
    mockListenCallback({
      payload: { type: 'terminal_init', pid: 2, command: 'cmd2' }
    })
    await wrapper.vm.$nextTick()

    // 给两个终端添加输出
    mockListenCallback({ payload: { type: 'terminal_output', pid: 1, content: 'Output 1' } })
    mockListenCallback({ payload: { type: 'terminal_output', pid: 2, content: 'Output 2' } })
    await wrapper.vm.$nextTick()

    // 默认应该是最后一个初始化的 (pid 2)
    // @ts-ignore
    expect(wrapper.vm.activePid).toBe(2)
    expect(wrapper.text()).toContain('Output 2')
    expect(wrapper.text()).not.toContain('Output 1')

    // 切换到 pid 1
    // @ts-ignore
    wrapper.vm.activePid = 1
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('Output 1')
    expect(wrapper.text()).not.toContain('Output 2')

    wrapper.unmount()
  })

  it('点击折叠按钮应该切换折叠状态', async () => {
    const wrapper = createWrapper()
    // 默认是折叠的
    // @ts-ignore
    expect(wrapper.vm.isCollapsed).toBe(true)

    // 默认显示 ChevronUp (因为是折叠状态)
    const toggleBtn = wrapper.find('.icon-chevron-up').element.closest('button')
    // @ts-ignore
    await toggleBtn.click()

    // @ts-ignore
    expect(wrapper.vm.isCollapsed).toBe(false)

    wrapper.unmount()
  })
})
