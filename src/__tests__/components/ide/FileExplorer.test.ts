import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import FileExplorer from '@/components/ide/FileExplorer.vue'
import CustomDialog from '@/components/ui/CustomDialog.vue'

// 模拟图标
vi.mock('lucide-vue-next', () => {
  const MockIcon = { template: '<span class="icon" />' }
  return {
    Plus: MockIcon,
    FolderPlus: MockIcon,
    RefreshCw: MockIcon,
    Search: MockIcon,
    // FileTreeItem 需要的图标
    Folder: MockIcon,
    FolderOpen: MockIcon,
    File: MockIcon,
    FileCode: MockIcon,
    FileJson: MockIcon,
    FileText: MockIcon
  }
})

// 模拟子组件 FileTreeItem (模块级 Mock)
vi.mock('@/components/ide/FileTreeItem.vue', () => ({
  default: {
    template:
      '<div class="file-tree-item" @click="$emit(\'select\', item)" @contextmenu.prevent.stop="$emit(\'contextmenu\', { event: $event, item })">{{ item.name }}</div>',
    props: ['item', 'level'],
    emits: ['select', 'contextmenu']
  }
}))

describe('FileExplorer.vue', () => {
  let wrapper: any

  const mockFiles = [
    {
      name: 'src',
      path: '/src',
      type: 'directory',
      children: [{ name: 'main.js', path: '/src/main.js', type: 'file' }]
    },
    { name: 'README.md', path: '/README.md', type: 'file' }
  ]

  beforeEach(() => {
    vi.clearAllMocks()
    global.fetch = vi.fn()
    // 默认 fetch 返回文件列表
    ;(global.fetch as any).mockResolvedValue({
      ok: true,
      json: async () => mockFiles
    })
  })

  const mountComponent = () => {
    return mount(FileExplorer, {
      global: {
        components: {
          // CustomDialog 需要真实渲染以便我们可以触发它的事件
          CustomDialog
        },
        stubs: {
          ContextMenu: true // ContextMenu 可以 stub，我们主要测试数据流
        }
      }
    })
  }

  it('初始化时应该加载文件列表', async () => {
    wrapper = mountComponent()
    await flushPromises()

    expect(global.fetch).toHaveBeenCalledWith(expect.stringContaining('/api/ide/files'))
    expect(wrapper.findAll('.file-tree-item').length).toBe(2) // src 和 README.md
  })

  it('搜索过滤功能', async () => {
    wrapper = mountComponent()
    await flushPromises()

    const searchInput = wrapper.find('input[type="text"]')
    await searchInput.setValue('README')

    // 应该只显示 README.md
    expect(wrapper.findAll('.file-tree-item').length).toBe(1)
    expect(wrapper.find('.file-tree-item').text()).toBe('README.md')
  })

  it('新建文件流程', async () => {
    wrapper = mountComponent()
    await flushPromises()

    // 模拟 fetch create 成功
    ;(global.fetch as any).mockImplementation((url: string) => {
      if (url.includes('/file/create')) {
        return Promise.resolve({ ok: true, json: () => ({}) })
      }
      return Promise.resolve({ ok: true, json: () => mockFiles }) // 刷新时返回
    })

    // 触发新建文件按钮 (第一个按钮)
    const createBtn = wrapper.findAll('button')[0]
    await createBtn.trigger('click')

    // 应该显示 Dialog
    const dialog = wrapper.findComponent(CustomDialog)
    expect(dialog.props('visible')).toBe(true)
    expect(dialog.props('title')).toBe('新建文件')

    // 模拟输入文件名并确认
    const input = dialog.find('input')
    await input.setValue('new-file.ts')
    await dialog
      .findAll('button')
      .find((b: any) => b.text() === '确定')
      ?.trigger('click')
    await flushPromises()

    // 应该调用创建 API
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/file/create'),
      expect.objectContaining({
        method: 'POST',
        body: expect.stringContaining('new-file.ts')
      })
    )
  })

  it('删除文件流程', async () => {
    wrapper = mountComponent()
    await flushPromises()

    // 确保列表加载完毕
    expect(wrapper.findAll('.file-tree-item').length).toBeGreaterThan(0)

    // 模拟 fetch delete 成功
    ;(global.fetch as any).mockImplementation((url: string) => {
      if (url.includes('/file/delete')) {
        return Promise.resolve({ ok: true, json: () => ({}) })
      }
      // 默认返回 mockFiles
      return Promise.resolve({ ok: true, json: () => mockFiles })
    })

    // 模拟右键点击项目触发上下文菜单
    const fileItems = wrapper.findAll('.file-tree-item')
    if (fileItems.length < 2) throw new Error('Not enough file items rendered')
    const fileItem = fileItems[1] // README.md

    // 必须提供 clientX/Y，否则 handleItemContextMenu 会认为事件无效
    await fileItem.trigger('contextmenu', { clientX: 100, clientY: 200 })

    // 检查 ContextMenu 是否显示 (通过 vm 状态)
    expect(wrapper.vm.contextMenu.visible).toBe(true)
    expect(wrapper.vm.contextMenu.targetItem.name).toBe('README.md')

    // 找到删除菜单项并执行 action
    const deleteOption = wrapper.vm.contextMenu.items.find((i: any) => i.label === '删除')
    expect(deleteOption).toBeDefined()

    // 执行删除动作
    deleteOption.action()
    await flushPromises() // 等待 Dialog 显示

    // 确认删除
    const dialog = wrapper.findComponent(CustomDialog)
    expect(dialog.props('visible')).toBe(true)
    expect(dialog.props('type')).toBe('confirm')

    await dialog
      .findAll('button')
      .find((b: any) => b.text() === '确定')
      ?.trigger('click')
    await flushPromises()

    // 应该调用删除 API
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/file/delete'),
      expect.objectContaining({
        method: 'POST',
        body: expect.stringContaining('README.md')
      })
    )
  })
})
