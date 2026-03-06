<template>
  <div
    class="h-8 w-full flex items-center justify-between select-none z-[9999] fixed top-0 left-0 right-0 transition-all duration-300 pixel-ui"
    :class="[
      transparent
        ? 'bg-transparent'
        : isWorkMode
          ? 'bg-[#0f172a] border-b-2 border-slate-700'
          : 'bg-sky-50 border-b-2 border-sky-100',
      isMaximized ? 'px-4' : ''
    ]"
    :style="isMaximized ? { paddingTop: '4px' } : {}"
    style="-webkit-app-region: drag"
  >
    <!-- 左侧：应用标题 / 图标 -->
    <div
      class="flex items-center gap-3 px-4 pointer-events-none"
      :class="isWorkMode ? 'text-slate-400' : 'text-sky-700'"
    >
      <div
        class="w-3 h-3"
        :class="isWorkMode ? 'bg-slate-600 pixel-border-sm-dark' : 'bg-moe-pink pixel-border-moe'"
      ></div>
      <span class="text-xs font-bold tracking-wide font-mono opacity-90">{{ title }}</span>
    </div>

    <!-- 右侧：窗口控制 -->
    <div class="flex items-center h-full" style="-webkit-app-region: no-drag">
      <!-- 模式切换 -->
      <button
        v-if="showModeToggle"
        class="h-full px-3 flex items-center justify-center transition-all duration-200 gap-2 mr-1 group"
        :class="
          isWorkMode
            ? 'hover:bg-white/5 text-slate-400 hover:text-amber-500'
            : 'hover:bg-sky-100 text-sky-600/70 hover:text-sky-600'
        "
        :title="isWorkMode ? '切换至对话' : '切换至工作'"
        @click="$emit('toggle-mode')"
      >
        <PixelIcon :name="isWorkMode ? 'chat' : 'briefcase'" size="xs" />
        <span class="text-[10px] font-bold tracking-wider uppercase opacity-80">{{
          isWorkMode ? 'Chat' : 'Work'
        }}</span>
      </button>

      <!-- 最小化 -->
      <button
        class="h-full w-12 flex items-center justify-center transition-all duration-200 group"
        :class="
          isWorkMode
            ? 'hover:bg-white/5 text-slate-400 hover:text-sky-400'
            : 'hover:bg-sky-100 text-sky-600/70 hover:text-sky-600'
        "
        @click="minimize"
      >
        <PixelIcon name="minus" size="sm" />
      </button>

      <!-- 最大化 / 还原 -->
      <button
        class="h-full w-12 flex items-center justify-center transition-all duration-200 group"
        :class="
          isWorkMode
            ? 'hover:bg-white/5 text-slate-400 hover:text-sky-400'
            : 'hover:bg-sky-100 text-sky-600/70 hover:text-sky-600'
        "
        @click="toggleMaximize"
      >
        <PixelIcon :name="isMaximized ? 'copy' : 'square'" size="sm" />
      </button>

      <!-- 关闭 -->
      <button
        class="h-full w-12 flex items-center justify-center transition-all duration-200 group"
        :class="
          isWorkMode
            ? 'hover:bg-red-500/80 text-slate-400 hover:text-white'
            : 'hover:bg-red-500 text-sky-600/70 hover:text-white'
        "
        @click="close"
      >
        <PixelIcon name="close" size="sm" />
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { invoke, listen } from '../../utils/ipcAdapter'
import PixelIcon from '../ui/PixelIcon.vue'
import { APP_TITLE } from '../../config'

defineProps({
  title: {
    type: String,
    default: APP_TITLE
  },
  transparent: {
    type: Boolean,
    default: false
  },
  isWorkMode: {
    type: Boolean,
    default: false
  },
  showModeToggle: {
    type: Boolean,
    default: false
  }
})
defineEmits(['toggle-mode'])

const isMaximized = ref(false)

const updateMaximizedState = async () => {
  try {
    isMaximized.value = await invoke('window-is-maximized')
  } catch (e) {
    console.warn('Failed to get window maximize state', e)
  }
}

const minimize = () => invoke('window-minimize')
const toggleMaximize = async () => {
  try {
    // 立即乐观更新 UI
    isMaximized.value = !isMaximized.value
    // 调用主进程并获取最终真实状态
    const newState = await invoke('window-toggle-maximize')
    if (newState !== null && newState !== undefined) {
      isMaximized.value = newState
    }
  } catch (e) {
    console.error('Maximize toggle failed', e)
    // 失败时回滚
    updateMaximizedState()
  }
}
const close = () => invoke('window-close')

let unlistenState = null

onMounted(async () => {
  updateMaximizedState()

  // 监听来自 Electron 主进程的状态变更事件
  unlistenState = await listen('window-maximized-state-changed', (state) => {
    isMaximized.value = !!state
  })
})

onUnmounted(() => {
  if (unlistenState) unlistenState()
})
</script>

<style scoped>
/* 使用 Tailwind 不需要额外的样式 */
</style>
