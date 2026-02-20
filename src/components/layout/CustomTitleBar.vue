<template>
  <div
    class="h-8 w-full flex items-center justify-between select-none z-[9999] fixed top-0 left-0 right-0 transition-colors duration-300"
    :class="transparent ? 'bg-transparent' : 'bg-slate-900/50 backdrop-blur-sm'"
    style="-webkit-app-region: drag"
  >
    <!-- 左侧：应用标题 / 图标 -->
    <div class="flex items-center gap-3 px-4 pointer-events-none text-slate-400">
      <div class="w-3 h-3 rounded-full bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.4)]"></div>
      <span class="text-xs font-medium tracking-wide font-mono opacity-80">{{ title }}</span>
    </div>

    <!-- 右侧：窗口控制 -->
    <div class="flex items-center h-full" style="-webkit-app-region: no-drag">
      <!-- 模式切换 -->
      <button
        v-if="showModeToggle"
        class="h-full px-3 flex items-center justify-center hover:bg-slate-800/50 text-slate-400 hover:text-white transition-all duration-200 gap-2 mr-1"
        :title="isWorkMode ? 'Switch to Chat' : 'Switch to Work'"
        @click="$emit('toggle-mode')"
      >
        <component :is="isWorkMode ? MessageSquare : Briefcase" class="w-3.5 h-3.5" />
        <span class="text-[10px] font-bold tracking-wider uppercase opacity-80">{{
          isWorkMode ? 'Chat' : 'Work'
        }}</span>
      </button>

      <!-- 最小化 -->
      <button
        class="h-full w-12 flex items-center justify-center hover:bg-slate-800/50 text-slate-400 hover:text-white transition-all duration-200 group"
        @click="minimize"
      >
        <Minus class="w-4 h-4 group-hover:scale-110 transition-transform" />
      </button>

      <!-- 最大化 / 还原 -->
      <button
        class="h-full w-12 flex items-center justify-center hover:bg-slate-800/50 text-slate-400 hover:text-white transition-all duration-200 group"
        @click="toggleMaximize"
      >
        <component
          :is="isMaximized ? Copy : Square"
          class="w-3.5 h-3.5 group-hover:scale-110 transition-transform"
        />
      </button>

      <!-- 关闭 -->
      <button
        class="h-full w-12 flex items-center justify-center hover:bg-red-500 text-slate-400 hover:text-white transition-all duration-200 group"
        @click="close"
      >
        <X class="w-4 h-4 group-hover:scale-110 transition-transform" />
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { invoke } from '../../utils/ipcAdapter'
import { Minus, Square, Copy, X, Briefcase, MessageSquare } from 'lucide-vue-next'
import { APP_TITLE } from '../../config'

defineProps({
  title: {
    type: String,
    default: APP_TITLE
  },
  transparent: {
    type: Boolean,
    default: true
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

const minimize = () => invoke('window-minimize')
const toggleMaximize = async () => {
  await invoke('window-maximize')
  isMaximized.value = await invoke('window-is-maximized')
}
const close = () => invoke('window-close')

onMounted(async () => {
  try {
    isMaximized.value = await invoke('window-is-maximized')
  } catch {
    // 回退或忽略
  }
})
</script>

<style scoped>
/* 使用 Tailwind 不需要额外的样式 */
</style>
