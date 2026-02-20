import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import NotificationManager from '@/components/ui/NotificationManager.vue'

// 模拟 ipcAdapter
vi.mock('@/utils/ipcAdapter', () => ({
  listen: vi.fn().mockResolvedValue(vi.fn())
}))

describe('NotificationManager.vue', () => {
  it('renders correctly', () => {
    const wrapper = mount(NotificationManager)
    expect(wrapper.exists()).toBe(true)
    expect(wrapper.find('.notification-container').exists()).toBe(true)
  })

  it('adds and removes notifications', async () => {
    const wrapper = mount(NotificationManager)

    // 使用暴露的全局方法或访问组件实例
    // 注意：window.$notify 是在 script setup 中设置的，但我们在 JSDOM 环境中
    // 最好访问内部方法（如果已暴露），但 script setup 默认是关闭的
    // 我们可以模拟调用该方法（如果通过 defineExpose 暴露），
    // 或者我们可以测试 window.$notify 的副作用（如果它设置在 window 上）。

    expect(window.$notify).toBeDefined()

    // 添加通知
    window.$notify('Test Message', 'info', 'Test Title')
    await wrapper.vm.$nextTick()

    const items = wrapper.findAll('.notification-item')
    expect(items.length).toBe(1)
    expect(items[0].text()).toContain('Test Message')
    expect(items[0].text()).toContain('Test Title')

    // 移除通知 (点击关闭按钮)
    await items[0].find('.close-btn').trigger('click')
    expect(wrapper.findAll('.notification-item').length).toBe(0)
  })

  it('auto removes notification after duration', async () => {
    vi.useFakeTimers()
    const wrapper = mount(NotificationManager)

    window.$notify('Auto Remove', 'info', '', 1000)
    await wrapper.vm.$nextTick()
    expect(wrapper.findAll('.notification-item').length).toBe(1)

    vi.advanceTimersByTime(1000)
    await wrapper.vm.$nextTick()
    expect(wrapper.findAll('.notification-item').length).toBe(0)

    vi.useRealTimers()
  })
})
