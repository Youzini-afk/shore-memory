<template>
  <div ref="triggerRef" class="relative inline-block" @mouseenter="show" @mouseleave="hide">
    <slot></slot>

    <Teleport to="body">
      <Transition
        enter-active-class="transition duration-100 ease-out"
        enter-from-class="opacity-0 translate-y-1"
        enter-to-class="opacity-100 translate-y-0"
        leave-active-class="transition duration-75 ease-in"
        leave-from-class="opacity-100 translate-y-0"
        leave-to-class="opacity-0 translate-y-1"
      >
        <div
          v-if="visible"
          ref="tooltipRef"
          class="fixed z-[9999] px-3 py-1.5 text-xs font-bold text-slate-600 bg-white pixel-border-sky pointer-events-none select-none max-w-xs break-words pixel-ui"
          :style="positionStyle"
        >
          {{ content }}
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<script setup>
import { ref, computed, nextTick } from 'vue'

const props = defineProps({
  content: {
    type: String,
    default: ''
  },
  placement: {
    type: String,
    default: 'top', // top, bottom, left, right
    validator: (value) => ['top', 'bottom', 'left', 'right'].includes(value)
  }
})

const visible = ref(false)
const triggerRef = ref(null)
const tooltipRef = ref(null)
const position = ref({ top: 0, left: 0 })

const positionStyle = computed(() => ({
  top: `${position.value.top}px`,
  left: `${position.value.left}px`
}))

const updatePosition = async () => {
  if (!triggerRef.value) return

  await nextTick()

  // 如果 tooltip 还没渲染出来（第一次显示），需要先让它渲染才能获取尺寸
  // 这里利用 nextTick 等待 v-if=true 生效
  if (!tooltipRef.value) return

  const triggerRect = triggerRef.value.getBoundingClientRect()
  const tooltipRect = tooltipRef.value.getBoundingClientRect()
  const gap = 8 // 间距

  let top = 0
  let left = 0

  switch (props.placement) {
    case 'top':
      top = triggerRect.top - tooltipRect.height - gap
      left = triggerRect.left + (triggerRect.width - tooltipRect.width) / 2
      break
    case 'bottom':
      top = triggerRect.bottom + gap
      left = triggerRect.left + (triggerRect.width - tooltipRect.width) / 2
      break
    case 'left':
      top = triggerRect.top + (triggerRect.height - tooltipRect.height) / 2
      left = triggerRect.left - tooltipRect.width - gap
      break
    case 'right':
      top = triggerRect.top + (triggerRect.height - tooltipRect.height) / 2
      left = triggerRect.right + gap
      break
  }

  // 边界检查（简单处理，防止溢出屏幕）
  const padding = 10
  if (left < padding) left = padding
  if (left + tooltipRect.width > window.innerWidth - padding) {
    left = window.innerWidth - tooltipRect.width - padding
  }
  if (top < padding) top = padding
  if (top + tooltipRect.height > window.innerHeight - padding) {
    top = window.innerHeight - tooltipRect.height - padding
  }

  position.value = { top, left }
}

const show = () => {
  if (!props.content) return
  visible.value = true
  updatePosition()
}

const hide = () => {
  visible.value = false
}
</script>
