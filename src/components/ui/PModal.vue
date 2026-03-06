<script setup lang="ts">
/**
 * 模态框组件 - 具有现代毛玻璃质感与可爱装饰的主题化组件 (喵~✨)
 */
import { ref, watch, onUnmounted } from 'vue'
import PixelIcon from './PixelIcon.vue'

const props = defineProps<{
  modelValue: boolean
  title?: string
  width?: string
  closeOnOverlayClick?: boolean
  /** 是否允许内容溢出显示 (用于包含下拉框时) */
  overflowVisible?: boolean
}>()

const emit = defineEmits(['update:modelValue', 'close'])

const overlayRef = ref<HTMLElement | null>(null)

/**
 * 关闭模态框
 */
const close = () => {
  emit('update:modelValue', false)
  emit('close')
}

/**
 * 处理遮罩层点击事件
 */
const handleOverlayClick = (e: MouseEvent) => {
  if (props.closeOnOverlayClick && e.target === overlayRef.value) {
    close()
  }
}

// 当模态框打开时锁定 body 滚动
watch(
  () => props.modelValue,
  (val) => {
    if (val) {
      document.body.style.overflow = 'hidden'
    } else {
      document.body.style.overflow = ''
    }
  }
)

onUnmounted(() => {
  document.body.style.overflow = ''
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
        v-if="modelValue"
        ref="overlayRef"
        class="fixed inset-0 z-[100] flex items-center justify-center bg-slate-500/10 backdrop-blur-md p-4 transition-all duration-300"
        @click="handleOverlayClick"
      >
        <div
          class="relative w-full max-w-lg bg-white/70 backdrop-blur-2xl border border-sky-100 rounded-[2rem] shadow-2xl shadow-sky-200/40 transform transition-all duration-500 hover:border-sky-300 group/pmodal"
          :class="overflowVisible ? 'overflow-visible' : 'overflow-hidden'"
          :style="{ maxWidth: width || '32rem' }"
          @click.stop
        >
          <!-- 装饰性渐变背景 ✨ -->
          <div
            class="absolute -right-20 -top-20 w-48 h-48 bg-sky-400/5 blur-[60px] rounded-full pointer-events-none group-hover/pmodal:bg-sky-400/10 transition-all duration-700"
          ></div>
          <div
            class="absolute -left-20 -bottom-20 w-48 h-48 bg-sky-400/5 blur-[60px] rounded-full pointer-events-none group-hover/pmodal:bg-sky-400/10 transition-all duration-700"
          ></div>

          <!-- 顶部标题栏 -->
          <div
            class="relative z-10 flex items-center justify-between px-8 py-6 border-b border-sky-50 bg-sky-50/20"
          >
            <div class="flex items-center gap-3">
              <div
                class="w-1.5 h-6 bg-gradient-to-b from-sky-400 to-sky-500 rounded-full shadow-[0_0_10px_rgba(14,165,233,0.3)]"
              ></div>
              <h3 class="text-xl font-bold text-slate-700/90 tracking-normal flex items-center gap-2">
                {{ title }}
                <span
                  class="text-xs text-sky-400/60 opacity-0 group-hover/pmodal:opacity-100 transition-opacity duration-500"
                  >✨</span
                >
              </h3>
            </div>
            <button
              class="text-slate-400 hover:text-sky-500 transition-all duration-300 rounded-xl p-2 hover:bg-sky-50 hover:rotate-90 active:scale-90"
              @click="close"
            >
              <PixelIcon name="close" size="md" />
            </button>
          </div>

          <!-- 主体内容 -->
          <div
            class="relative z-10 p-8 max-h-[75vh] overflow-y-auto custom-scrollbar text-slate-600 leading-relaxed"
          >
            <slot />
          </div>

          <!-- 底部按钮栏 -->
          <div
            v-if="$slots.footer"
            class="relative z-10 px-8 py-6 bg-sky-50/30 border-t border-sky-50 flex justify-end gap-3"
          >
            <slot name="footer" />
          </div>

          <!-- 底部可爱装饰 🐾 -->
          <div
            class="absolute bottom-2 left-1/2 -translate-x-1/2 opacity-0 group-hover/pmodal:opacity-100 transition-all duration-700 translate-y-2 group-hover/pmodal:translate-y-0 text-[10px] text-sky-500/30 font-mono pointer-events-none"
          >
            PAW PRINT OF APPROVAL 🐾
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>
