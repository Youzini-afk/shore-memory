<template>
  <div
    class="flex flex-col h-full bg-slate-950 text-slate-300 font-mono text-sm overflow-hidden relative group/terminal pixel-border-dark"
  >
    <!-- CRT Scanline Effect -->
    <div
      class="absolute inset-0 pointer-events-none z-10 bg-[linear-gradient(rgba(18,16,16,0)_50%,rgba(0,0,0,0.1)_50%),linear-gradient(90deg,rgba(255,0,0,0.03),rgba(0,255,0,0.01),rgba(0,0,255,0.03))]"
      style="
        background-size:
          100% 3px,
          3px 100%;
      "
    ></div>

    <div
      class="flex items-center justify-between px-4 py-2 bg-slate-900 border-b-2 border-slate-800 shrink-0 relative z-20"
    >
      <div class="flex items-center gap-2 font-bold text-slate-200">
        <div class="animate-pulse">
          <PixelIcon name="terminal" size="sm" class="text-moe-pink" />
        </div>
        <span class="tracking-wider pixel-font">NapCat 交互终端</span>
      </div>
      <div class="flex items-center gap-2">
        <button
          class="p-1.5 hover:bg-white/10 text-slate-400 hover:text-red-400 transition-colors group active:scale-90 pixel-border-sm-transparent hover:pixel-border-sm-dark"
          title="清空"
          @click="clearLogs"
        >
          <PixelIcon name="trash" size="xs" class="group-hover:shake" />
        </button>
      </div>
    </div>

    <div ref="logContainer" class="flex-1 overflow-y-auto p-4 custom-scrollbar relative z-0">
      <!-- 下载进度条 -->
      <div v-if="downloadProgress.active" class="mb-4 bg-slate-800 p-3 pixel-border-moe">
        <div class="flex justify-between text-xs mb-2 font-bold font-mono">
          <span class="text-moe-pink flex items-center gap-2">
            <PixelIcon name="download" size="xs" animation="bounce" />
            {{ downloadProgress.status }}
          </span>
          <span class="text-moe-sky">{{ downloadProgress.percent }}%</span>
        </div>
        <div class="w-full bg-slate-900 h-3 p-0.5 border border-slate-700">
          <div
            class="h-full transition-all duration-300 bg-moe-pink"
            :class="downloadProgress.error ? 'bg-red-500' : 'bg-moe-pink'"
            :style="{ width: `${downloadProgress.percent}%` }"
          ></div>
        </div>
      </div>

      <div
        v-for="log in logs"
        :key="log.id"
        class="break-all whitespace-pre-wrap leading-none font-mono text-[13px] hover:bg-white/5 transition-colors px-1"
      >
        <span class="text-slate-500 mr-2 opacity-70">[{{ log.time }}]</span>
        <span class="message" v-html="ansiToHtml(log.content)"></span>
      </div>
      <div
        v-if="logs.length === 0"
        class="flex flex-col items-center justify-center h-full text-slate-600 gap-3 opacity-50"
      >
        <PixelIcon name="terminal" size="xl" class="text-moe-pink/50" />
        <span class="text-xs tracking-widest uppercase pixel-font">等待 NapCat 进程输出...</span>
      </div>
    </div>

    <div class="p-3 bg-slate-900 border-t-2 border-slate-800 shrink-0 relative z-20">
      <div
        class="flex items-center gap-2 bg-slate-950 border-2 border-slate-800 px-3 py-2 focus-within:border-moe-pink/50 transition-colors group/input"
      >
        <PixelIcon
          name="chevron-right"
          size="xs"
          class="text-moe-pink shrink-0 group-focus-within/input:animate-pulse"
        />
        <input
          v-model="inputValue"
          class="flex-1 bg-transparent border-none outline-none text-moe-pink placeholder-slate-600 font-mono"
          placeholder="输入指令并回车..."
          spellcheck="false"
          @keyup.enter="sendCommand"
        />
        <span v-if="inputValue" class="text-[10px] text-moe-pink/50 animate-pulse pixel-font"
          >PRESS ENTER</span
        >
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, nextTick, watch, onMounted, onUnmounted } from 'vue'
import PixelIcon from '../ui/PixelIcon.vue'
import { listen, invoke } from '@/utils/ipcAdapter'

// 状态
const logs = ref([])
const inputValue = ref('')
const logContainer = ref(null)
const downloadProgress = ref({
  active: false,
  percent: 0,
  status: '',
  error: false,
  completed: false
})
let unlistenFn = null
let unlistenProgressFn = null

// 操作
const clearLogs = () => {
  logs.value = []
}

const scrollToBottom = () => {
  if (logContainer.value) {
    nextTick(() => {
      logContainer.value.scrollTop = logContainer.value.scrollHeight
    })
  }
}

watch(logs, () => scrollToBottom(), { deep: true })

const sendCommand = async () => {
  if (!inputValue.value.trim()) return

  const cmd = inputValue.value

  try {
    await invoke('send_napcat_command_wrapper', { command: cmd })

    // 将输入镜像到终端
    logs.value.push({
      time: new Date().toLocaleTimeString(),
      content: `> ${cmd}`,
      id: Date.now() + Math.random()
    })
    inputValue.value = ''
  } catch (e) {
    console.error(`[错误] 发送指令失败: ${e}`)
    // 简易错误提示
    logs.value.push({
      time: new Date().toLocaleTimeString(),
      content: `[Error] 发送指令失败: ${e}`,
      id: Date.now() + Math.random()
    })
  }
}

// ANSI 转 HTML 辅助函数
const ansiToHtml = (text) => {
  if (!text) return ''
  let result = text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')

  // 基本 ANSI 颜色
  const colors = {
    0: 'reset',
    30: 'text-slate-500', // 黑色
    31: 'text-red-400', // 红色
    32: 'text-emerald-400', // 绿色
    33: 'text-amber-400', // 黄色
    34: 'text-blue-400', // 蓝色
    35: 'text-purple-400', // 洋红
    36: 'text-cyan-400', // 青色
    37: 'text-slate-200', // 白色
    90: 'text-slate-600' // 亮黑
  }

  // 非常基础的实现
  // eslint-disable-next-line no-control-regex
  result = result.replace(/\x1b\[(\d+)m/g, (match, code) => {
    const className = colors[code]
    if (className === 'reset') return '</span>'
    if (className) return `<span class="${className}">`
    return ''
  })

  return result
}

onMounted(async () => {
  try {
    // 1. 首先获取历史记录以显示过去的日志（包括二维码）
    const history = await (await import('@/utils/ipcAdapter')).invoke('get_napcat_logs')
    if (history && history.length > 0) {
      logs.value = history.map((line) => ({
        time: new Date().toLocaleTimeString(),
        content: line,
        id: Date.now() + Math.random()
      }))
    }

    // 2. 开始监听新日志
    unlistenFn = await listen('napcat_log', (payload) => {
      // 在 Electron 中，payload 就是日志内容本身 (字符串)
      // 在 Tauri 中，payload 可能是 event.payload，但 ipcAdapter 已处理过
      const logLine = typeof payload === 'string' ? payload : payload.payload || String(payload)

      const timestamp = new Date().toLocaleTimeString()

      logs.value.push({
        time: timestamp,
        content: logLine,
        id: Date.now() + Math.random()
      })

      if (logs.value.length > 500) logs.value.shift()
    })

    // 3. 监听下载进度
    unlistenProgressFn = await listen('napcat-download-progress', (payload) => {
      // payload 格式: { percent, status, url, error, completed }
      downloadProgress.value = {
        active: true,
        percent: payload.percent,
        status: payload.status,
        error: payload.error || false,
        completed: payload.completed || false
      }

      if (payload.error) {
        ElMessage.error(`NapCat 安装失败: ${payload.status}`)
      }

      if (payload.completed || payload.error) {
        setTimeout(() => {
          downloadProgress.value.active = false
        }, 5000)
      }
    })
  } catch (e) {
    console.error('初始化 NapCat 日志失败', e)
  }
})

onUnmounted(() => {
  if (unlistenFn) {
    unlistenFn()
  }
  if (unlistenProgressFn) {
    unlistenProgressFn()
  }
})
</script>

<style scoped>
.terminal-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  background-color: #1e1e1e;
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
  user-select: text;
}

.download-progress-bar {
  padding: 10px 16px;
  background-color: #252526;
  border-bottom: 1px solid #3d3d3d;
}

.progress-info {
  display: flex;
  justify-content: space-between;
  margin-bottom: 5px;
  font-size: 12px;
  color: #ccc;
}

.terminal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 16px;
  background-color: #2d2d2d;
  border-bottom: 1px solid #3d3d3d;
  color: #ccc;
  user-select: none;
}

.terminal-header .title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: bold;
}

.terminal-content {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
  font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
  font-size: 13px;
  line-height: 1;
  color: #d4d4d4;
  white-space: pre-wrap;
  word-break: break-all;
}

/* 滚动条 */
.terminal-content::-webkit-scrollbar {
  width: 8px;
}
.terminal-content::-webkit-scrollbar-track {
  background: #1e1e1e;
}
.terminal-content::-webkit-scrollbar-thumb {
  background: #424242;
  border-radius: 4px;
}
.terminal-content::-webkit-scrollbar-thumb:hover {
  background: #4f4f4f;
}

.log-line {
  margin-bottom: 2px;
  display: flex;
  gap: 8px;
}

.timestamp {
  color: #6a9955;
  flex-shrink: 0;
}

.message {
  flex: 1;
}

/* 空状态 */
.empty-state {
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #666;
  gap: 10px;
}
.empty-icon {
  font-size: 48px;
  opacity: 0.5;
}

/* 输入区域 */
.terminal-input-area {
  display: flex;
  align-items: center;
  padding: 10px 12px;
  background-color: #252526;
  border-top: 1px solid #3d3d3d;
}

.input-prefix {
  color: #22c55e; /* emerald-500 */
  margin-right: 8px;
  display: flex;
  align-items: center;
}

.terminal-input {
  flex: 1;
  background: transparent;
  border: none;
  outline: none;
  color: #d4d4d4;
  font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
  font-size: 13px;
}

.terminal-input::placeholder {
  color: #666;
}

/* 类似 Tailwind 的 ANSI 文本颜色 */
.text-slate-500 {
  color: #64748b;
}
.text-red-400 {
  color: #f87171;
}
.text-emerald-400 {
  color: #34d399;
}
.text-amber-400 {
  color: #fbbf24;
}
.text-blue-400 {
  color: #60a5fa;
}
.text-purple-400 {
  color: #c084fc;
}
.text-cyan-400 {
  color: #22d3ee;
}
.text-slate-200 {
  color: #e2e8f0;
}
.text-slate-600 {
  color: #475569;
}
</style>
