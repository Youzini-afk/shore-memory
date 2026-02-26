import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import CustomDialog from '@/components/ui/CustomDialog.vue'

describe('CustomDialog.vue', () => {
  it('当 visible 为 false 时不应该渲染', () => {
    const wrapper = mount(CustomDialog, {
      props: {
        visible: false
      }
    })
    expect(wrapper.find('.fixed').exists()).toBe(false)
  })

  it('当 visible 为 true 时应该渲染', () => {
    const wrapper = mount(CustomDialog, {
      props: {
        visible: true
      }
    })
    expect(wrapper.find('.fixed').exists()).toBe(true)
    expect(wrapper.text()).toContain('提示') // 默认标题
  })

  it('应该正确渲染标题和消息', () => {
    const wrapper = mount(CustomDialog, {
      props: {
        visible: true,
        title: '测试标题',
        message: '测试消息内容'
      }
    })
    expect(wrapper.text()).toContain('测试标题')
    expect(wrapper.text()).toContain('测试消息内容')
  })

  it('Alert 模式下应该只有一个确定按钮', () => {
    const wrapper = mount(CustomDialog, {
      props: {
        visible: true,
        type: 'alert'
      }
    })
    // 查找包含"确定"文本的按钮
    const confirmBtn = wrapper.findAll('button').find((b) => b.text().includes('确定'))
    const cancelBtn = wrapper.findAll('button').find((b) => b.text().includes('取消'))

    expect(confirmBtn).toBeDefined()
    expect(cancelBtn).toBeUndefined()
  })

  it('Confirm 模式下应该有确定和取消按钮', () => {
    const wrapper = mount(CustomDialog, {
      props: {
        visible: true,
        type: 'confirm'
      }
    })
    const confirmBtn = wrapper.findAll('button').find((b) => b.text().includes('确定'))
    const cancelBtn = wrapper.findAll('button').find((b) => b.text().includes('取消'))

    expect(confirmBtn).toBeDefined()
    expect(cancelBtn).toBeDefined()
  })

  it('点击确定按钮应该触发 confirm 事件', async () => {
    const wrapper = mount(CustomDialog, {
      props: {
        visible: true
      }
    })
    const confirmButton = wrapper.findAll('button').find((b) => b.text() === '确定')
    if (!confirmButton) throw new Error('Confirm button not found')
    await confirmButton.trigger('click')

    expect(wrapper.emitted('confirm')).toBeTruthy()
    // 默认非 prompt 模式不带参数
    expect(wrapper.emitted('confirm')?.[0]).toEqual([])
  })

  it('点击取消按钮应该触发 cancel 和 update:visible 事件', async () => {
    const wrapper = mount(CustomDialog, {
      props: {
        visible: true,
        type: 'confirm'
      }
    })
    const cancelButton = wrapper.findAll('button').find((b) => b.text() === '取消')
    if (!cancelButton) throw new Error('Cancel button not found')
    await cancelButton.trigger('click')

    expect(wrapper.emitted('cancel')).toBeTruthy()
    expect(wrapper.emitted('update:visible')).toBeTruthy()
    expect(wrapper.emitted('update:visible')?.[0]).toEqual([false])
  })

  it('Prompt 模式下应该显示输入框', async () => {
    const wrapper = mount(CustomDialog, {
      props: {
        visible: true,
        type: 'prompt',
        placeholder: '请输入...'
      }
    })

    const input = wrapper.find('input')
    expect(input.exists()).toBe(true)
    expect(input.attributes('placeholder')).toBe('请输入...')
  })

  it('Prompt 模式下确认应该返回输入的值', async () => {
    const wrapper = mount(CustomDialog, {
      props: {
        visible: true,
        type: 'prompt'
      }
    })

    const input = wrapper.find('input')
    await input.setValue('Hello World')

    const confirmButton = wrapper.findAll('button').find((b) => b.text() === '确定')
    if (!confirmButton) throw new Error('Confirm button not found')
    await confirmButton.trigger('click')

    expect(wrapper.emitted('confirm')?.[0]).toEqual(['Hello World'])
  })
})
