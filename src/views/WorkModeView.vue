<template>
  <div
    class="absolute inset-0 bg-[#1e293b] text-slate-200 font-sans flex overflow-hidden p-4 gap-4 pixel-ui pixel-grid-overlay"
  >
    <!-- 像素背景点缀 -->
    <div class="absolute inset-0 pointer-events-none opacity-10">
      <div
        v-for="i in 10"
        :key="'pixel-' + i"
        class="absolute bg-white/20"
        :style="{
          width: '4px',
          height: '4px',
          top: Math.random() * 100 + '%',
          left: Math.random() * 100 + '%'
        }"
      ></div>
    </div>
    <!-- 错误遮罩 -->
    <div
      v-if="error"
      class="absolute inset-0 z-[60] flex items-center justify-center bg-black/80 backdrop-blur-sm p-8"
    >
      <div
        class="bg-[#1e293b] border border-red-500/30 p-6 pixel-border-dark shadow-2xl max-w-2xl w-full"
      >
        <div class="flex items-center gap-3 text-red-400 mb-4">
          <PixelIcon name="close" size="sm" />
          <span class="text-xl font-bold">组件错误</span>
        </div>
        <pre
          class="bg-black/50 p-4 pixel-border-sm-dark text-left overflow-auto text-xs font-mono text-slate-300 mb-6 border border-moe-cocoa/30"
          >{{ error }}</pre
        >
        <div class="flex justify-end">
          <button
            class="px-6 py-2.5 bg-slate-800 hover:bg-slate-700 pixel-border-sm-dark transition text-white font-medium flex items-center gap-2 border border-moe-cocoa/30"
            @click="emit('exit', false)"
          >
            <PixelIcon name="logout" size="xs" />
            退出工作模式
          </button>
        </div>
      </div>
    </div>

    <!-- 加载遮罩 -->
    <div
      v-if="!internalReady && !error"
      class="absolute inset-0 z-[60] flex items-center justify-center bg-[#1e293b] pixel-grid-overlay"
    >
      <div class="flex flex-col items-center gap-6">
        <div class="relative">
          <div class="text-moe-pink">
            <PixelIcon name="loader" size="3xl" animation="spin" />
          </div>
        </div>
        <span class="text-moe-pink/60 text-sm font-bold tracking-widest animate-pulse uppercase"
          >正在初始化工作环境...</span
        >
      </div>
    </div>

    <!-- 左侧面板: 资源管理器 (悬浮卡片) -->
    <div
      v-show="internalReady && !error"
      class="w-72 bg-[#1e293b]/80 backdrop-blur-md pixel-border-dark flex flex-col shadow-2xl overflow-hidden transition-all duration-300 group/sidebar border border-moe-cocoa/20"
    >
      <!-- 面板标题栏 -->
      <div
        class="h-14 px-5 flex items-center justify-between border-b border-moe-cocoa/30 bg-black/20"
      >
        <div class="flex items-center gap-2 text-moe-sky">
          <PixelIcon name="folder" size="sm" />
          <span class="font-bold tracking-wide text-sm">项目工程</span>
        </div>
      </div>

      <!-- 文件树 -->
      <div class="flex-1 overflow-hidden">
        <FileExplorer @file-selected="onFileSelected" />
      </div>
    </div>

    <!-- 主内容区域 (悬浮卡片) -->
    <div
      v-show="internalReady && !error"
      class="flex-1 flex flex-col relative gap-4 overflow-hidden min-h-0"
    >
      <!-- 顶部导航栏 -->
      <header
        class="h-14 px-6 bg-[#1e293b]/80 backdrop-blur-md pixel-border-dark flex items-center justify-between shadow-lg shrink-0 border border-moe-cocoa/20"
      >
        <!-- 面包屑 / 状态 -->
        <div class="flex items-center gap-4">
          <div
            class="flex items-center gap-2 px-3 py-1 bg-moe-pink/10 border border-moe-pink/20 pixel-border-sm-dark"
          >
            <div class="w-2 h-2 bg-moe-pink animate-pulse"></div>
            <span class="text-moe-pink text-xs font-bold tracking-wide uppercase">专注模式</span>
          </div>
          <div class="h-4 w-px bg-moe-cocoa/30"></div>
          <span class="text-slate-400 text-sm flex items-center gap-2">
            <PixelIcon name="layout" size="xs" />
            <span class="font-bold opacity-80">工作区</span>
          </span>
        </div>

        <!-- 工作模式操作 -->
        <div class="flex items-center gap-3">
          <button
            class="flex items-center gap-2 px-4 py-2 hover:bg-red-500/10 text-slate-400 hover:text-red-400 pixel-border-sm-dark transition-all duration-200 group border border-transparent"
            title="取消工作 (不保存日志)"
            @click="emit('exit', false)"
          >
            <PixelIcon name="close" size="xs" class="group-hover:scale-110 transition-transform" />
            <span class="text-sm font-medium">取消工作</span>
          </button>

          <button
            class="flex items-center gap-2 px-5 py-2 bg-moe-pink hover:bg-pink-400 text-white pixel-border-sm-dark transition-all duration-200 shadow-lg shadow-moe-pink/20 group hover:scale-105 active:scale-95 border border-moe-cocoa/30"
            title="完成工作 (生成日志)"
            @click="emit('exit', true)"
          >
            <PixelIcon name="check" size="xs" class="group-hover:rotate-12 transition-transform" />
            <span class="text-sm font-bold">完成工作</span>
          </button>
        </div>
      </header>

      <!-- 编辑器 & 聊天 & 终端容器 -->
      <div class="flex-1 flex flex-col gap-4 overflow-hidden min-h-0">
        <!-- 编辑器 & 聊天分屏视图 -->
        <div class="flex-1 flex gap-4 overflow-hidden min-h-0">
          <!-- 代码编辑器容器 -->
          <div
            class="flex-1 flex flex-col bg-[#1e293b]/80 backdrop-blur-md pixel-border-dark shadow-2xl overflow-hidden relative group/editor border border-moe-cocoa/20 z-10"
          >
            <!-- 编辑器标签页 -->
            <div
              class="h-10 bg-black/40 flex items-center px-2 gap-1 overflow-x-auto no-scrollbar border-b border-moe-cocoa/30"
            >
              <div
                v-for="file in openFiles"
                :key="file.path"
                class="group/tab flex items-center gap-2 px-4 py-1.5 text-xs pixel-border-sm-dark cursor-pointer transition-all border border-transparent min-w-[120px] max-w-[200px] relative"
                :class="
                  currentFile?.path === file.path
                    ? 'bg-moe-sky/20 text-moe-sky border-moe-sky/30 shadow-sm'
                    : 'text-slate-500 hover:bg-white/5 hover:text-slate-300'
                "
                @click="currentFile = file"
              >
                <PixelIcon name="file" size="xs" class="opacity-70" />
                <span class="truncate font-bold">{{ file.name }}</span>
                <!-- 关闭按钮 -->
                <button
                  class="absolute right-1 p-0.5 opacity-0 group-hover/tab:opacity-100 hover:bg-red-500/20 text-slate-400 hover:text-red-400 transition-all"
                  @click.stop="closeFile(file)"
                >
                  <PixelIcon name="close" size="xs" />
                </button>
                <!-- 未保存指示器 -->
                <div
                  v-if="dirtyFiles.has(file.path)"
                  class="absolute right-2 w-1.5 h-1.5 bg-moe-yellow shadow-[0_0_8px_rgba(253,224,71,0.5)]"
                ></div>
              </div>
            </div>

            <!-- 编辑器内容 -->
            <div class="flex-1 relative bg-[#0f172a]/50">
              <template v-if="currentFile">
                <CodeEditor
                  :initial-content="currentFile.content"
                  :language="getLanguage(currentFile.name)"
                  :file-path="currentFile.path"
                  class="h-full w-full"
                  @save="saveFile"
                  @change="onContentChange"
                />
              </template>
              <div
                v-else
                class="absolute inset-0 flex flex-col items-center justify-center text-slate-600/50"
              >
                <div class="p-6 pixel-border-sm-dark bg-slate-800/20 mb-6 animate-pulse">
                  <PixelIcon name="code" size="2xl" class="opacity-50" />
                </div>
                <p class="text-sm font-medium tracking-wide uppercase text-slate-500">
                  选择一个文件以开始编辑
                </p>
                <p class="text-xs text-slate-600 mt-2">使用左侧资源管理器浏览文件</p>
              </div>

              <!-- 悬浮保存按钮 -->
              <Transition name="fade">
                <button
                  v-if="currentFile && dirtyFiles.has(currentFile.path)"
                  class="absolute bottom-6 right-6 p-4 bg-moe-pink hover:bg-pink-400 text-white pixel-border-sm-dark shadow-lg shadow-moe-pink/40 transition-all hover:scale-110 active:scale-95 z-20 group flex items-center gap-2 border border-moe-cocoa/30"
                  title="保存文件 (Ctrl+S)"
                  @click="saveFile(currentFile.content)"
                >
                  <PixelIcon name="save" size="md" />
                  <span
                    class="max-w-0 overflow-hidden group-hover:max-w-[100px] transition-all duration-300 whitespace-nowrap font-bold text-sm"
                    >保存更改</span
                  >
                </button>
              </Transition>
            </div>
          </div>

          <!-- 聊天区域 (悬浮侧边栏) -->
          <div
            class="w-[400px] flex flex-col bg-[#1e293b]/80 backdrop-blur-md pixel-border-dark shadow-2xl overflow-hidden transition-all duration-500 border border-moe-cocoa/20"
          >
            <ChatInterface
              :key="agentId"
              :work-mode="true"
              :disabled="!internalReady"
              class="flex-1"
              :target-id="agentId"
              :agent-name="agentName"
            />
          </div>
        </div>

        <!-- 终端管理器 -->
        <TerminalManager />
      </div>
    </div>

    <CustomDialog
      v-model:visible="dialog.visible"
      :type="dialog.type"
      :title="dialog.title"
      :message="dialog.message"
      @confirm="handleDialogConfirm"
      @cancel="handleDialogCancel"
    />
  </div>
</template>

<script setup>
import { ref, onMounted, onActivated, onErrorCaptured, reactive, computed, watch } from 'vue'
import FileExplorer from '../components/ide/FileExplorer.vue'
import CodeEditor from '../components/ide/CodeEditor.vue'
import ChatInterface from '../components/chat/ChatInterface.vue'
import CustomDialog from '../components/ui/CustomDialog.vue'
import TerminalManager from '../components/ide/TerminalManager.vue'
import PixelIcon from '../components/ui/PixelIcon.vue'

const props = defineProps({
  isReady: {
    type: Boolean,
    default: false
  }
})

// 动态获取后端基础 URL 喵~ 🌸
const API_BASE = window.location.protocol + '//' + (window.location.hostname || 'localhost') + ':9120'

const emit = defineEmits(['exit', 'start-work'])

// 对话框状态
const dialog = reactive({
  visible: false,
  type: 'alert',
  title: '',
  message: '',
  resolve: null
})

const showDialog = ({ type, title, message }) => {
  return new Promise((resolve) => {
    dialog.type = type
    dialog.title = title
    dialog.message = message
    dialog.resolve = resolve
    dialog.visible = true
  })
}

const handleDialogConfirm = () => {
  if (dialog.resolve) dialog.resolve(true)
  dialog.visible = false
}

const handleDialogCancel = () => {
  if (dialog.resolve) dialog.resolve(false)
  dialog.visible = false
}

// 错误处理
const error = ref(null)
onErrorCaptured((err) => {
  console.error('工作模式视图错误:', err)
  error.value = err.message
  return true
})

// 状态
const internalReady = ref(false) // 初始不就绪
const agentName = ref('Pero')
const agentId = ref('pero')

// 监听父组件就绪状态，只有后端完成 work_mode/enter 后才真正开始加载
watch(() => props.isReady, (newVal) => {
  if (newVal && !internalReady.value) {
    initWorkMode()
  }
}, { immediate: true })

const initWorkMode = async () => {
  try {
    await fetchActiveAgent()
    internalReady.value = true
  } catch (e) {
    console.error('[WorkMode] 初始化失败:', e)
    error.value = '工作环境初始化失败，请检查网络连接或后端状态喵~'
  }
}

const fetchActiveAgent = async () => {
  try {
    const res = await fetch(`${API_BASE}/api/agents`)
    if (res.ok) {
      const agents = await res.json()
      const active = agents.find((a) => a.is_active)
      if (active) {
        agentName.value = active.name
        agentId.value = active.id
      }
    }
  } catch (e) {
    console.error(e)
    throw e // 向上传递错误以触发 UI 提示
  }
}

const openFiles = ref([])
const currentFile = ref(null)
const dirtyFiles = ref(new Set())

onMounted(() => {
  console.log('WorkModeView Mounted')
  // 如果父组件已经就绪，直接初始化
  if (props.isReady) {
    initWorkMode()
  }
})

onActivated(() => {
  console.log('WorkModeView Activated')
  fetchActiveAgent()
})

// 文件处理
// 文件选择逻辑优化
const onFileSelected = async (fileNode) => {
  if (fileNode.type === 'directory') return

  const existing = openFiles.value.find((f) => f.path === fileNode.path)
  if (existing) {
    currentFile.value = existing
    return
  }

  try {
    const res = await fetch(`${API_BASE}/api/ide/file/read`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path: fileNode.path })
    })
    
    if (!res.ok) {
      const errData = await res.json().catch(() => ({}))
      throw new Error(errData.detail || '读取文件失败')
    }
    
    const data = await res.json()
    const newFile = { ...fileNode, content: data.content }
    openFiles.value.push(newFile)
    currentFile.value = newFile
  } catch (e) {
    console.error('[WorkMode] 文件读取错误:', e)
    if (window.$notify) {
      window.$notify(e.message, 'error', '文件读取失败')
    }
  }
}

const closeFile = async (file) => {
  if (dirtyFiles.value.has(file.path)) {
    const confirmed = await showDialog({
      type: 'confirm',
      title: '未保存更改',
      message: `'${file.name}' 有未保存的更改。确定要放弃更改并关闭吗？`
    })

    if (!confirmed) {
      return
    }
    dirtyFiles.value.delete(file.path)
  }

  const idx = openFiles.value.indexOf(file)
  if (idx > -1) {
    openFiles.value.splice(idx, 1)
    if (currentFile.value === file) {
      currentFile.value = openFiles.value[openFiles.value.length - 1] || null
    }
  }
}

const getLanguage = (filename) => {
  const ext = filename.split('.').pop().toLowerCase()

  const map = {
    py: 'python',
    js: 'javascript',
    ts: 'typescript',
    vue: 'html', // Monaco 没有内置 Vue 支持，使用 HTML 效果尚可
    html: 'html',
    css: 'css',
    scss: 'scss',
    less: 'less',
    json: 'json',
    md: 'markdown',
    rs: 'rust',
    java: 'java',
    c: 'c',
    cpp: 'cpp',
    go: 'go',
    sh: 'shell',
    bash: 'shell',
    sql: 'sql',
    yaml: 'yaml',
    yml: 'yaml',
    xml: 'xml',
    ini: 'ini',
    toml: 'ini',
    bat: 'bat',
    ps1: 'powershell'
  }

  return map[ext] || 'plaintext'
}

const onContentChange = (newContent) => {
  if (currentFile.value) {
    currentFile.value.content = newContent
    dirtyFiles.value.add(currentFile.value.path)
  }
}

const saveFile = async (content) => {
  if (!currentFile.value) return

  try {
    const res = await fetch('http://localhost:9120/api/ide/file/write', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        path: currentFile.value.path,
        content: content
      })
    })

    if (res.ok) {
      dirtyFiles.value.delete(currentFile.value.path)
      // 可选：Toast 通知
    } else {
      showDialog({ type: 'alert', title: '错误', message: '保存文件失败' })
    }
  } catch (e) {
    console.error(e)
    showDialog({ type: 'alert', title: '错误', message: '保存文件时出错' })
  }
}
</script>

<style scoped>
/* 深色主题自定义滚动条 */
.custom-scrollbar::-webkit-scrollbar {
  width: 4px;
}
.custom-scrollbar::-webkit-scrollbar-track {
  background: transparent;
}
.custom-scrollbar::-webkit-scrollbar-thumb {
  background: #2d1b1e80; /* moe-cocoa with transparency */
  border-radius: 0;
}
.custom-scrollbar::-webkit-scrollbar-thumb:hover {
  background: #2d1b1e;
}
</style>
