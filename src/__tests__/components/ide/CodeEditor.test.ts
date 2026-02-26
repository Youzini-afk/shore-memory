import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import CodeEditor from '@/components/ide/CodeEditor.vue'

// 使用 vi.hoisted 创建可以被 mock factory 访问的变量
const { mockEditorInstance, mockMonaco } = vi.hoisted(() => {
  return {
    mockEditorInstance: {
      onDidChangeModelContent: vi.fn(),
      addCommand: vi.fn(),
      getValue: vi.fn(() => 'mock code')
    },
    mockMonaco: {
      KeyMod: {
        CtrlCmd: 2048
      },
      KeyCode: {
        KeyS: 49
      }
    }
  }
})

// 模拟 @guolao/vue-monaco-editor 模块
vi.mock('@guolao/vue-monaco-editor', () => {
  return {
    VueMonacoEditor: {
      name: 'VueMonacoEditor',
      template: '<div class="vue-monaco-editor-mock"></div>',
      props: ['value', 'language', 'theme', 'options'],
      emits: ['update:value', 'mount'],
      mounted() {
        // 在挂载时触发 mount 事件，传递 mock 对象
        // @ts-ignore
        this.$emit('mount', mockEditorInstance, mockMonaco)
      }
    }
  }
})

describe('CodeEditor.vue', () => {
  let wrapper: any

  beforeEach(() => {
    vi.clearAllMocks()

    // 每次测试前重置 mockEditorInstance 的 mock 函数
    mockEditorInstance.onDidChangeModelContent.mockReset()
    mockEditorInstance.addCommand.mockReset()
  })

  it('渲染正常', () => {
    wrapper = mount(CodeEditor, {
      props: {
        initialContent: 'console.log("hello")',
        language: 'javascript'
      }
    })

    expect(wrapper.exists()).toBe(true)
    expect(wrapper.find('.vue-monaco-editor-mock').exists()).toBe(true)
  })

  it('初始化时应该正确设置内容', () => {
    wrapper = mount(CodeEditor, {
      props: {
        initialContent: 'console.log("hello")'
      }
    })

    // 检查内部 code ref 是否被正确初始化
    expect(wrapper.vm.code).toBe('console.log("hello")')
  })

  it('监听 initialContent 变化并更新编辑器内容', async () => {
    wrapper = mount(CodeEditor, {
      props: {
        initialContent: 'initial'
      }
    })

    await wrapper.setProps({ initialContent: 'updated' })
    expect(wrapper.vm.code).toBe('updated')
  })

  it('编辑器内容变化时应该触发 change 事件', () => {
    wrapper = mount(CodeEditor)

    // 此时组件已挂载，handleMount 已被调用，回调已被注册
    expect(mockEditorInstance.onDidChangeModelContent).toHaveBeenCalled()

    // 获取 handleMount 中注册的回调
    const onChangeCallback = mockEditorInstance.onDidChangeModelContent.mock.calls[0][0]

    // 模拟内容变化
    wrapper.vm.code = 'new content'
    onChangeCallback()

    expect(wrapper.emitted('change')).toBeTruthy()
    expect(wrapper.emitted('change')[0]).toEqual(['new content'])
  })

  it('按下 Ctrl+S 应该触发 save 事件', () => {
    wrapper = mount(CodeEditor)

    expect(mockEditorInstance.addCommand).toHaveBeenCalled()

    // 获取 handleMount 中注册的命令回调
    const saveCallback = mockEditorInstance.addCommand.mock.calls[0][1]

    // 模拟触发保存
    wrapper.vm.code = 'content to save'
    saveCallback()

    expect(wrapper.emitted('save')).toBeTruthy()
    expect(wrapper.emitted('save')[0]).toEqual(['content to save'])
  })
})
