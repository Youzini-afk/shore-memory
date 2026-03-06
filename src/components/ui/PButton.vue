<script setup lang="ts">
/**
 * 按钮组件 - 具有可爱质感的主题化组件 (喵~🐾)
 */
import { computed } from 'vue'
import PixelIcon from './PixelIcon.vue'

const props = defineProps<{
  variant?:
    | 'primary'
    | 'secondary'
    | 'danger'
    | 'ghost'
    | 'outline'
    | 'glass'
    | 'sky'
    | 'warning'
    | 'success'
  size?: 'xs' | 'sm' | 'md' | 'lg'
  loading?: boolean
  disabled?: boolean
  icon?: any
  block?: boolean
  /** 是否开启可爱点击效果 */
  cute?: boolean
  /** 是否强制像素风格 */
  pixel?: boolean
}>()

const emit = defineEmits(['click'])

const baseClasses =
  'relative inline-flex items-center justify-center font-bold tracking-wide transition-all duration-300 focus:outline-none disabled:opacity-50 disabled:cursor-not-allowed press-effect overflow-hidden group/pbutton'

const variantClasses = computed(() => {
  switch (props.variant) {
    case 'primary':
    case 'sky':
      return 'pixel-border-sky bg-sky-400 hover:bg-sky-500 text-white shadow-sm'
    case 'secondary':
      return 'pixel-border-sm bg-white hover:bg-slate-50 text-slate-700'
    case 'danger':
      return 'pixel-border-pink bg-rose-500 hover:bg-rose-600 text-white shadow-sm'
    case 'warning':
      return 'pixel-border-orange bg-amber-400 hover:bg-amber-500 text-white shadow-sm'
    case 'success':
      return 'pixel-border-green bg-emerald-400 hover:bg-emerald-500 text-white shadow-sm'
    case 'ghost':
      return 'bg-transparent hover:bg-sky-50 text-slate-500 hover:text-sky-600'
    case 'outline':
      return 'pixel-border-sm bg-transparent text-slate-500 hover:text-sky-600 hover:pixel-border-sky hover:bg-sky-50'
    case 'glass':
    default:
      return 'pixel-border-sky bg-white/90 text-slate-700 hover:bg-white'
  }
})

const sizeClasses = computed(() => {
  switch (props.size) {
    case 'xs':
      return 'px-2.5 py-1.5 text-xs'
    case 'sm':
      return 'px-3.5 py-2 text-sm'
    case 'lg':
      return 'px-8 py-3.5 text-lg'
    case 'md':
    default:
      return 'px-5 py-2.5 text-sm'
  }
})

/**
 * 处理点击事件
 */
const handleClick = (event: MouseEvent) => {
  if (!props.disabled && !props.loading) {
    emit('click', event)
  }
}
</script>

<template>
  <button
    :class="[baseClasses, variantClasses, sizeClasses, { 'w-full': block }]"
    :disabled="disabled || loading"
    @click="handleClick"
  >
    <!-- 背景光效 -->
    <div
      class="absolute inset-0 bg-gradient-to-r from-transparent via-white/10 to-transparent -translate-x-full group-hover/pbutton:animate-[shimmer_1.5s_infinite] pointer-events-none"
    ></div>

    <!-- 加载状态 -->
    <PixelIcon v-if="loading" name="refresh" animation="spin" class="mr-2 opacity-80" size="sm" />

    <!-- 图标 -->
    <component
      :is="icon"
      v-else-if="icon"
      class="mr-2 h-4 w-4 transition-transform group-hover/pbutton:scale-110"
    />

    <!-- 按钮文字 -->
    <span class="relative z-10">
      <slot />
    </span>

    <!-- 可爱的小星星 (仅限 primary/sky 或开启 cute) -->
    <div
      v-if="(variant === 'primary' || variant === 'sky' || cute) && !loading"
      class="absolute -top-1 -right-1 opacity-0 group-hover/pbutton:opacity-100 transition-all duration-500 scale-50 group-hover/pbutton:scale-100 rotate-12"
    >
      <PixelIcon name="sparkle" size="xs" class="text-white" />
    </div>
  </button>
</template>

<style scoped>
@keyframes shimmer {
  100% {
    transform: translateX(100%);
  }
}
</style>
