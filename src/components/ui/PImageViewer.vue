<script setup lang="ts">
import { X, ChevronLeft, ChevronRight } from 'lucide-vue-next'
import { onMounted, onUnmounted } from 'vue'

const props = defineProps<{
  images: string[]
  initialIndex?: number
  visible: boolean
}>()

const emit = defineEmits(['update:visible', 'close'])

const currentIndex = defineModel<number>('index', { default: 0 })

/**
 * 关闭查看器 🐾
 */
const close = () => {
  emit('update:visible', false)
  emit('close')
}

/**
 * 上一张 ⬅️
 */
const prev = () => {
  if (currentIndex.value > 0) {
    currentIndex.value--
  }
}

/**
 * 下一张 ➡️
 */
const next = () => {
  if (currentIndex.value < props.images.length - 1) {
    currentIndex.value++
  }
}

/**
 * 键盘快捷键支持 ⌨️
 */
const handleKeydown = (e: KeyboardEvent) => {
  if (!props.visible) return
  if (e.key === 'Escape') close()
  if (e.key === 'ArrowLeft') prev()
  if (e.key === 'ArrowRight') next()
}

onMounted(() => {
  window.addEventListener('keydown', handleKeydown)
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeydown)
})
</script>

<template>
  <Teleport to="body">
    <Transition
      enter-active-class="transition duration-300 ease-out"
      enter-from-class="opacity-0 scale-95"
      enter-to-class="opacity-100 scale-100"
      leave-active-class="transition duration-200 ease-in"
      leave-from-class="opacity-100 scale-100"
      leave-to-class="opacity-0 scale-95"
    >
      <div
        v-if="visible"
        class="fixed inset-0 z-[9999] bg-white/70 backdrop-blur-xl flex items-center justify-center p-4 md:p-10 select-none group/viewer"
        @click.self="close"
      >
        <!-- 背景装饰光晕 ✨ -->
        <div
          class="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-full max-w-4xl h-full max-h-[80vh] bg-sky-100/50 blur-[120px] rounded-full pointer-events-none animate-pulse"
        ></div>

        <!-- 关闭按钮 🐾 -->
        <button
          class="absolute top-6 right-6 p-3 text-slate-400 hover:text-rose-500 bg-white/50 hover:bg-rose-50 rounded-2xl border border-sky-100 transition-all hover:scale-110 active:scale-90 z-50 group/close shadow-sm"
          title="关闭 (Esc)"
          @click="close"
        >
          <X class="w-6 h-6 group-hover/close:rotate-90 transition-transform duration-300" />
        </button>

        <!-- 导航按钮 - 左 ⬅️ -->
        <button
          v-if="images.length > 1"
          class="absolute left-6 top-1/2 -translate-y-1/2 p-4 text-slate-400 hover:text-sky-600 bg-white/50 hover:bg-sky-50 rounded-2xl border border-sky-100 transition-all hover:scale-110 active:scale-90 z-50 disabled:opacity-20 disabled:cursor-not-allowed group/prev shadow-sm"
          :disabled="currentIndex === 0"
          @click.stop="prev"
        >
          <ChevronLeft class="w-8 h-8 group-hover/prev:-translate-x-1 transition-transform" />
        </button>

        <!-- 导航按钮 - 右 ➡️ -->
        <button
          v-if="images.length > 1"
          class="absolute right-6 top-1/2 -translate-y-1/2 p-4 text-slate-400 hover:text-sky-600 bg-white/50 hover:bg-sky-50 rounded-2xl border border-sky-100 transition-all hover:scale-110 active:scale-90 z-50 disabled:opacity-20 disabled:cursor-not-allowed group/next shadow-sm"
          :disabled="currentIndex === images.length - 1"
          @click.stop="next"
        >
          <ChevronRight class="w-8 h-8 group-hover/next:translate-x-1 transition-transform" />
        </button>

        <!-- 图片计数器 🐾 -->
        <div
          v-if="images.length > 1"
          class="absolute bottom-10 left-1/2 -translate-x-1/2 px-6 py-2 bg-white/90 backdrop-blur-xl border border-sky-100 rounded-full text-slate-800 text-sm font-bold shadow-2xl flex items-center gap-3"
        >
          <span class="text-sky-500">{{ currentIndex + 1 }}</span>
          <span class="text-slate-300">/</span>
          <span>{{ images.length }}</span>
          <span class="text-xs opacity-50 ml-2 animate-bounce">🐾</span>
        </div>

        <!-- 主图片展示 🖼️ -->
        <div class="relative group/image max-w-full max-h-full flex items-center justify-center">
          <img
            :src="images[currentIndex]"
            class="max-w-full max-h-[85vh] object-contain shadow-[0_0_50px_rgba(0,0,0,0.5)] rounded-lg transition-transform duration-500 group-hover/viewer:scale-[1.01]"
            @click.stop
          />

          <!-- 悬浮时的可爱装饰 ✨ -->
          <div
            class="absolute -top-4 -right-4 text-2xl opacity-0 group-hover/image:opacity-100 transition-all duration-500 transform group-hover/image:translate-y-2 group-hover/image:-translate-x-2"
          >
            ✨
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
/* 渐变背景过度 */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
