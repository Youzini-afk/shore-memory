<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  modelValue: number
  min?: number
  max?: number
  step?: number
  disabled?: boolean
  showInput?: boolean
}>()

const emit = defineEmits(['update:modelValue'])

/**
 * 计算当前值占总长度的百分比 📊
 */
const percentage = computed(() => {
  const min = props.min || 0
  const max = props.max || 100
  return ((props.modelValue - min) / (max - min)) * 100
})

/**
 * 处理滑动输入事件 🐾
 */
const handleInput = (e: Event) => {
  const target = e.target as HTMLInputElement
  emit('update:modelValue', Number(target.value))
}
</script>

<template>
  <div class="flex items-center gap-4 group/pslider">
    <!-- 滑动条轨道 🐾 -->
    <div class="relative flex-1 h-6 flex items-center select-none">
      <div
        class="w-full h-2.5 bg-sky-100/50 rounded-full overflow-hidden shadow-inner border border-sky-200/30"
      >
        <div
          class="h-full bg-gradient-to-r from-sky-300 to-sky-400 transition-all duration-150 shadow-[0_0_10px_rgba(14,165,233,0.2)] relative group-hover/pslider:from-sky-200 group-hover/pslider:to-sky-300"
          :style="{ width: `${percentage}%` }"
        >
          <!-- 内部装饰线条 ✨ -->
          <div
            class="absolute inset-0 bg-[linear-gradient(45deg,rgba(255,255,255,0.1)_25%,transparent_25%,transparent_50%,rgba(255,255,255,0.1)_50%,rgba(255,255,255,0.1)_75%,transparent_75%,transparent)] bg-[length:10px_10px] animate-[shimmer_20s_linear_infinite]"
          ></div>
        </div>
      </div>

      <!-- 原生 Range 输入框 (透明，用于交互) 🖱️ -->
      <input
        type="range"
        :value="modelValue"
        :min="min"
        :max="max"
        :step="step"
        :disabled="disabled"
        class="absolute inset-0 w-full h-full opacity-0 cursor-pointer disabled:cursor-not-allowed z-20"
        @input="handleInput"
      />

      <!-- 自定义滑块 Handle 🐾 -->
      <div
        class="absolute w-6 h-6 bg-white rounded-full shadow-[0_4px_12px_rgba(14,165,233,0.2)] border-2 border-sky-400 pointer-events-none transition-all duration-150 z-10 flex items-center justify-center group-hover/pslider:scale-110 group-active/pslider:scale-95 group-hover/pslider:border-sky-300"
        :style="{ left: `calc(${percentage}% - 12px)` }"
      >
        <div
          class="w-2 h-2 bg-sky-400 rounded-full animate-pulse group-hover/pslider:bg-sky-300"
        ></div>

        <!-- 悬浮时的提示小猫爪 🐾 -->
        <div
          class="absolute -top-6 left-1/2 -translate-x-1/2 text-[10px] opacity-0 group-hover/pslider:opacity-100 group-hover/pslider:-top-8 transition-all duration-300 pointer-events-none text-sky-400 drop-shadow-sm"
        >
          🐾
        </div>
      </div>
    </div>

    <!-- 可选的数字输入框 🔢 -->
    <div v-if="showInput" class="w-16">
      <input
        type="number"
        :value="modelValue"
        :min="min"
        :max="max"
        :step="step"
        :disabled="disabled"
        class="w-full bg-sky-50 border border-sky-100 rounded-xl px-2 py-1.5 text-xs text-center text-slate-700 focus:outline-none focus:border-sky-300 focus:ring-4 focus:ring-sky-100/50 transition-all hover:bg-sky-100 hover:border-sky-200 font-mono shadow-sm"
        @input="handleInput"
      />
    </div>
  </div>
</template>

<style scoped>
@keyframes shimmer {
  from {
    background-position: 0 0;
  }
  to {
    background-position: 100px 0;
  }
}

/* 隐藏 Firefox 的默认样式 */
input[type='range']::-moz-range-track {
  background: transparent;
  border: none;
}
input[type='range']::-moz-range-thumb {
  background: transparent;
  border: none;
}
</style>
