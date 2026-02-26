import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ReActProcessViewer from '@/components/agent/ReActProcessViewer.vue'

// Mock config
vi.mock('../../config', () => ({
  AGENT_NAME: 'TestAgent'
}))

describe('ReActProcessViewer.vue', () => {
  const defaultSegments = [
    { type: 'text', content: '普通文本' },
    { type: 'action', content: '执行动作' },
    { type: 'thinking', content: '思考过程' },
    { type: 'error', content: '发生错误' },
    { type: 'reflection', content: '自我反思' }
  ]

  beforeEach(() => {
    // Mock fetch
    global.fetch = vi.fn()
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  it('应该正确渲染不同类型的 segment', () => {
    const wrapper = mount(ReActProcessViewer, {
      props: {
        segments: defaultSegments,
        isLive: false
      }
    })

    expect(wrapper.text()).toContain('普通文本')
    expect(wrapper.text()).toContain('执行动作')
    expect(wrapper.text()).toContain('思考过程')
    expect(wrapper.text()).toContain('发生错误')
    expect(wrapper.text()).toContain('自我反思')

    // 检查特定样式类是否存在
    expect(wrapper.find('.segment-text').exists()).toBe(true)
    expect(wrapper.find('.segment-action').exists()).toBe(true)
    expect(wrapper.find('.segment-thinking').exists()).toBe(true)
    expect(wrapper.find('.segment-error').exists()).toBe(true)
    expect(wrapper.find('.segment-reflection').exists()).toBe(true)
  })

  it('isLive 为 true 时应该显示控制工具栏', () => {
    const wrapper = mount(ReActProcessViewer, {
      props: {
        segments: [],
        isLive: true
      }
    })

    expect(wrapper.find('.toolbar').exists()).toBe(true)
    expect(wrapper.find('.injection-panel').exists()).toBe(true)
  })

  it('isLive 为 false 时不应该显示控制工具栏', () => {
    const wrapper = mount(ReActProcessViewer, {
      props: {
        segments: [],
        isLive: false
      }
    })

    expect(wrapper.find('.toolbar').exists()).toBe(false)
    expect(wrapper.find('.injection-panel').exists()).toBe(false)
  })

  it('Live 模式下挂载时应该轮询任务状态', async () => {
    vi.useFakeTimers()
    // Mock fetch response
    // @ts-ignore
    global.fetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ status: 'running' })
    })

    const wrapper = mount(ReActProcessViewer, {
      props: { segments: [], isLive: true }
    })

    expect(global.fetch).toHaveBeenCalledWith('http://localhost:9120/api/task/default/status')

    // 快进时间检查轮询
    await vi.advanceTimersByTimeAsync(2100)
    expect(global.fetch).toHaveBeenCalledTimes(2)

    vi.useRealTimers()
  })

  it('点击暂停按钮应该调用暂停 API', async () => {
    // 模拟 fetch 实现，区分 status 检查和操作请求
    // @ts-ignore
    global.fetch.mockImplementation((url) => {
      if (url.includes('/status')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ status: 'running' })
        })
      }
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({})
      })
    })

    const wrapper = mount(ReActProcessViewer, {
      props: { segments: [], isLive: true }
    })

    // 等待 mounted 时的 checkTaskStatus 完成
    await flushPromises()
    // @ts-ignore
    expect(wrapper.vm.isTaskPaused).toBe(false)

    // 初始状态为运行中，点击暂停
    const pauseBtn = wrapper.find('.pause-btn')
    await pauseBtn.trigger('click')

    // 等待异步操作
    await flushPromises()

    expect(global.fetch).toHaveBeenCalledWith(
      'http://localhost:9120/api/task/default/pause',
      expect.objectContaining({ method: 'POST' })
    )

    // 状态应该变为暂停
    // @ts-ignore
    expect(wrapper.vm.isTaskPaused).toBe(true)

    // 再次点击恢复
    await pauseBtn.trigger('click')
    await flushPromises()

    expect(global.fetch).toHaveBeenCalledWith(
      'http://localhost:9120/api/task/default/resume',
      expect.objectContaining({ method: 'POST' })
    )

    // 状态应该变回运行
    // @ts-ignore
    expect(wrapper.vm.isTaskPaused).toBe(false)
  })

  it('发送指令应该调用注入 API', async () => {
    // @ts-ignore
    global.fetch.mockResolvedValue({ ok: true, json: () => ({}) })

    const wrapper = mount(ReActProcessViewer, {
      props: { segments: [], isLive: true }
    })

    const input = wrapper.find('input')
    const sendBtn = wrapper.find('.send-btn')

    // 输入内容
    await input.setValue('停止思考')

    // 点击发送
    await sendBtn.trigger('click')
    await flushPromises()

    expect(global.fetch).toHaveBeenCalledWith(
      'http://localhost:9120/api/task/default/inject',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ instruction: '停止思考' })
      })
    )

    // 发送后应该清空输入框
    expect(input.element.value).toBe('')
  })

  it('没有 segments 时应该显示空状态提示', () => {
    const wrapper = mount(ReActProcessViewer, {
      props: { segments: [], isLive: false }
    })

    expect(wrapper.find('.empty-tip').text()).toBe('无思考过程记录')
  })
})
