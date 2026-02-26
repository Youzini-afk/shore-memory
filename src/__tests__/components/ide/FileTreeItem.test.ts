import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import FileTreeItem from '@/components/ide/FileTreeItem.vue'

// 模拟 Lucide 图标
vi.mock('lucide-vue-next', () => {
  const MockIcon = { template: '<svg class="lucide-icon"></svg>' }
  return {
    Folder: MockIcon,
    FolderOpen: MockIcon,
    File: MockIcon,
    FileCode: MockIcon,
    FileJson: MockIcon,
    FileText: MockIcon
  }
})

describe('FileTreeItem.vue', () => {
  const defaultProps = {
    item: {
      name: 'test-file.js',
      path: '/root/test-file.js',
      type: 'file'
    },
    level: 0
  }

  beforeEach(() => {
    vi.clearAllMocks()
    // 模拟 fetch
    global.fetch = vi.fn()
  })

  it('正确渲染文件名和缩进', () => {
    const wrapper = mount(FileTreeItem, {
      props: {
        ...defaultProps,
        level: 2
      }
    })

    expect(wrapper.text()).toContain('test-file.js')
    // 使用 DOM 属性检查样式
    const container = wrapper.find('.cursor-pointer')
    expect((container.element as HTMLElement).style.paddingLeft).toBe('32px')
  })

  it('点击文件应该触发 select 事件', async () => {
    const wrapper = mount(FileTreeItem, {
      props: defaultProps
    })

    await wrapper.find('.cursor-pointer').trigger('click')
    expect(wrapper.emitted('select')).toBeTruthy()
    expect(wrapper.emitted('select')?.[0]).toEqual([defaultProps.item])
  })

  it('点击目录应该切换展开状态', async () => {
    const dirProps = {
      item: {
        name: 'src',
        path: '/root/src',
        type: 'directory'
      },
      level: 0
    }

    // 模拟 fetch 返回空数组
    ;(global.fetch as any).mockResolvedValue({
      ok: true,
      json: async () => []
    })

    const wrapper = mount(FileTreeItem, {
      props: dirProps
    })

    // 点击展开
    await wrapper.find('.cursor-pointer').trigger('click')
    await flushPromises()

    // 应该调用 fetch 加载子文件
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/ide/files?path=%2Froot%2Fsrc')
    )
  })

  it('右键点击应该触发 contextmenu 事件', async () => {
    const wrapper = mount(FileTreeItem, {
      props: defaultProps
    })

    await wrapper.find('.cursor-pointer').trigger('contextmenu.prevent')
    expect(wrapper.emitted('contextmenu')).toBeTruthy()
    // 检查事件参数结构 { event: MouseEvent, item: Object }
    const eventPayload = wrapper.emitted('contextmenu')?.[0][0] as any
    expect(eventPayload.item).toEqual(defaultProps.item)
    expect(eventPayload.event).toBeDefined()
  })
})
