<script setup lang="ts">
/**
 * 数字输入框组件 - 具有可爱质感的主题化组件 (喵~🐾)
 */
import PixelIcon from './PixelIcon.vue'

const props = defineProps<{
  modelValue: number
  min?: number
  max?: number
  step?: number
  disabled?: boolean
}>()

const emit = defineEmits(['update:modelValue'])

/**
 * 更新数值，确保在最小值和最大值范围内
 */
const updateValue = (val: number) => {
  if (props.disabled) return
  let newValue = val
  if (props.min !== undefined && newValue < props.min) newValue = props.min
  if (props.max !== undefined && newValue > props.max) newValue = props.max
  emit('update:modelValue', newValue)
}

/**
 * 减少数值
 */
const decrease = () => updateValue(props.modelValue - (props.step || 1))

/**
 * 增加数值
 */
const increase = () => updateValue(props.modelValue + (props.step || 1))
</script>

<template>
  <div class="flex items-center group/pinputnum">
    <!-- 减少按钮 -->
    <button
      class="w-9 h-9 flex items-center justify-center bg-white/50 hover:bg-sky-100 border border-sky-100 rounded-l-xl transition-all duration-300 disabled:opacity-30 disabled:cursor-not-allowed hover:border-sky-300 active:scale-90"
      :disabled="disabled || (min !== undefined && modelValue <= min)"
      @click="decrease"
    >
      <PixelIcon
        name="minus"
        size="xs"
        class="text-slate-400 group-hover/pinputnum:text-sky-600 transition-colors"
      />
    </button>

    <!-- 数值显示 -->
    <div
      class="min-w-[40px] px-2 h-9 flex items-center justify-center bg-white/80 border-y border-sky-100 text-sm font-mono text-sky-600 shadow-inner group-hover/pinputnum:border-sky-300 transition-all duration-300"
    >
      {{ modelValue }}
    </div>

    <!-- 增加按钮 -->
    <button
      class="w-9 h-9 flex items-center justify-center bg-white/50 hover:bg-sky-100 border border-sky-100 rounded-r-xl transition-all duration-300 disabled:opacity-30 disabled:cursor-not-allowed hover:border-sky-300 active:scale-90"
      :disabled="disabled || (max !== undefined && modelValue >= max)"
      @click="increase"
    >
      <PixelIcon
        name="plus"
        size="xs"
        class="text-slate-400 group-hover/pinputnum:text-sky-600 transition-colors"
      />
    </button>

    <!-- 可爱的小尾巴 ✨ -->
    <div
      class="ml-2 opacity-0 group-hover/pinputnum:opacity-100 transition-all duration-500 -translate-x-2 group-hover/pinputnum:translate-x-0 pointer-events-none text-xs text-sky-400/60 italic"
    >
      <PixelIcon name="paw" size="xs" />
    </div>
  </div>
</template>
