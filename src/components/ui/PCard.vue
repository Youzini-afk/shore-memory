<script setup lang="ts">
import { computed } from 'vue'
import PixelIcon from './PixelIcon.vue'

const props = defineProps<{
  hoverable?: boolean
  glass?: boolean
  bordered?: boolean
  active?: boolean
  padding?: string
  color?: string
  noBlur?: boolean
  /** 开启微3D质感 (喵~🐾) */
  soft3d?: boolean
  /** 开启像素风格 (Minecraft Mode) */
  pixel?: boolean
  /** 糖果色变体: 'purple', 'pink', 'orange', 'green', 'sky' */
  variant?: 'purple' | 'pink' | 'orange' | 'green' | 'sky'
  /** 开启外发光效果 */
  glow?: boolean
  /** 是否允许溢出显示 (用于包含下拉框时) */
  overflowVisible?: boolean
  /** 是否让内容区域撑满高度 (喵~🐾) */
  fullHeight?: boolean
}>()

const cardClasses = computed(() => {
  if (props.pixel) {
    let classes = 'relative transition-all duration-300 pixel-border-sky bg-white'
    if (props.overflowVisible) {
      classes += ' overflow-visible'
    } else {
      classes += ' overflow-hidden'
    }
    if (props.hoverable) {
      classes +=
        ' pixel-hover-lift press-effect cursor-pointer active:scale-95 transition-transform'
    }
    if (props.active) {
      classes += ' bg-sky-50'
    }
    return classes
  }

  let classes = 'relative transition-all duration-500 rounded-[2rem]' // 更圆润的圆角

  if (props.overflowVisible) {
    classes += ' overflow-visible'
  } else {
    classes += ' overflow-hidden'
  }

  // 变体背景色与阴影处理
  if (props.variant === 'purple') {
    classes += ' bg-purple-50/80 border-purple-100 shadow-purple-200/30'
  } else if (props.variant === 'pink') {
    classes += ' bg-pink-50/80 border-pink-100 shadow-pink-200/30'
  } else if (props.variant === 'orange') {
    classes += ' bg-orange-50/80 border-orange-100 shadow-orange-200/30'
  } else if (props.variant === 'green') {
    classes += ' bg-emerald-50/80 border-emerald-100 shadow-emerald-200/30'
  } else {
    if (props.glass) {
      classes += ' glass-effect shadow-xl shadow-sky-100/20'
    } else {
      classes += ' bg-white/90 border border-sky-100 shadow-xl shadow-sky-100/20'
    }
  }

  if (props.soft3d) {
    classes += ' soft-3d-shadow'
  }

  if (props.hoverable) {
    classes +=
      ' hover:translate-y-[-6px] hover:shadow-2xl hover:bg-white/80 cursor-pointer active:scale-95 transition-all duration-500 ease-[cubic-bezier(0.34,1.56,0.64,1)]'
  }

  if (props.bordered) {
    classes += ' border-2 border-slate-800/50 ring-1 ring-sky-100/30'
  }

  if (props.glow) {
    const glowColors = {
      purple: 'shadow-purple-400/20',
      pink: 'shadow-pink-400/20',
      orange: 'shadow-orange-400/20',
      green: 'shadow-emerald-400/20',
      sky: 'shadow-sky-400/20'
    }
    classes += ` shadow-lg ${glowColors[props.variant || 'sky']}`
  }

  if (props.active) {
    classes += ' ring-4 ring-sky-300/30 bg-sky-50/60'
  }

  return classes
})
</script>

<template>
  <div
    :class="[cardClasses, pixel ? 'pixel-border-sky' : 'rounded-2xl', 'relative group/pcard']"
    :style="{ padding: padding || '1.5rem' }"
  >
    <!-- 悬停闪光 ✨ -->
    <div
      v-if="hoverable"
      class="absolute top-4 right-4 opacity-0 group-hover/pcard:opacity-100 transition-all duration-500 scale-0 group-hover/pcard:scale-125 z-20 pointer-events-none"
    >
      <div class="text-sky-400 drop-shadow-[0_0_8px_rgba(14,165,233,0.5)]">
        <PixelIcon name="sparkle" size="sm" animation="spin" />
      </div>
    </div>

    <div v-if="$slots.header" class="mb-4 border-b border-slate-800/50 pb-3">
      <slot name="header" />
    </div>
    <div :class="['relative z-10', { 'flex-1 h-full flex flex-col': fullHeight }]">
      <slot />
    </div>
    <!-- 可选发光效果 -->
    <div
      class="absolute -top-10 -right-10 w-32 h-32 bg-sky-500/5 blur-[60px] rounded-full pointer-events-none group-hover/pcard:bg-sky-500/10 transition-colors"
    />
  </div>
</template>
