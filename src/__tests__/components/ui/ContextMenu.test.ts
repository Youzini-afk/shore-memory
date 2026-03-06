import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import ContextMenu from '@/components/ui/ContextMenu.vue'

describe('ContextMenu.vue', () => {
  const defaultProps = {
    visible: true,
    x: 100,
    y: 200,
    items: [
      { label: 'Item 1', action: vi.fn() },
      { label: 'Item 2', action: vi.fn(), disabled: true },
      { type: 'separator' },
      { label: 'Item 3', action: vi.fn(), shortcut: 'Ctrl+C' }
    ]
  }

  it('正确渲染菜单项', () => {
    const wrapper = mount(ContextMenu, {
      props: defaultProps
    })

    // 检查位置
    const menu = wrapper.find('div')
    expect(menu.attributes('style')).toContain('top: 200px')
    expect(menu.attributes('style')).toContain('left: 100px')

    // 检查项目数量 (3个按钮，1个分隔符)
    expect(wrapper.findAll('button').length).toBe(3)
    expect(wrapper.findAll('.bg-\\[\\#454545\\]').length).toBe(1) // separator

    // 检查标签
    expect(wrapper.text()).toContain('Item 1')
    expect(wrapper.text()).toContain('Item 3')
    expect(wrapper.text()).toContain('Ctrl+C')
  })

  it('visible 为 false 时不渲染', () => {
    const wrapper = mount(ContextMenu, {
      props: { ...defaultProps, visible: false }
    })
    expect(wrapper.find('div').exists()).toBe(false)
  })

  it('点击项目应该触发动作并关闭', async () => {
    const wrapper = mount(ContextMenu, {
      props: defaultProps
    })

    await wrapper.findAll('button')[0].trigger('click')

    expect(defaultProps.items[0].action).toHaveBeenCalled()
    expect(wrapper.emitted('close')).toBeTruthy()
  })

  it('点击禁用项目不应该触发动作', async () => {
    const wrapper = mount(ContextMenu, {
      props: defaultProps
    })

    await wrapper.findAll('button')[1].trigger('click') // Item 2 is disabled

    expect(defaultProps.items[1].action).not.toHaveBeenCalled()
    expect(wrapper.emitted('close')).toBeFalsy()
  })

  it('点击外部应该关闭菜单', async () => {
    // 需要 attachTo document 才能测试 window 事件
    const wrapper = mount(ContextMenu, {
      props: { ...defaultProps },
      attachTo: document.body
    })

    // 模拟点击外部
    await document.body.click()
    expect(wrapper.emitted('close')).toBeTruthy()

    wrapper.unmount()
  })

  it('按下 Escape 键应该关闭菜单', async () => {
    const wrapper = mount(ContextMenu, {
      props: { ...defaultProps },
      attachTo: document.body
    })

    await wrapper.trigger('keydown', { key: 'Escape' })
    // 或者直接在 window 上触发
    const event = new KeyboardEvent('keydown', { key: 'Escape' })
    window.dispatchEvent(event)

    expect(wrapper.emitted('close')).toBeTruthy()

    wrapper.unmount()
  })
})
