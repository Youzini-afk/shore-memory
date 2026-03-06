<template>
  <div
    v-if="visible"
    class="fixed z-[9999] bg-white/95 backdrop-blur-sm pixel-border-moe shadow-xl py-1 min-w-[160px] pixel-ui"
    :style="{ top: y + 'px', left: x + 'px' }"
    @click.stop
    @contextmenu.prevent
  >
    <div v-for="(item, index) in items" :key="index">
      <div v-if="item.type === 'separator'" class="h-[2px] bg-moe-pink/10 my-1 mx-2"></div>
      <button
        v-else
        class="w-full text-left px-3 py-1.5 text-xs text-moe-cocoa hover:bg-moe-pink hover:text-white flex items-center justify-between group transition-colors font-bold"
        :class="{ 'opacity-50 cursor-not-allowed': item.disabled }"
        :disabled="item.disabled"
        @click="handleClick(item)"
      >
        <span>{{ item.label }}</span>
        <span
          v-if="item.shortcut"
          class="text-[10px] text-moe-cocoa/40 group-hover:text-white/80 ml-4 font-mono"
          >{{ item.shortcut }}</span
        >
      </button>
    </div>
  </div>
</template>

<script setup>
import { onMounted, onUnmounted } from 'vue'

defineProps({
  visible: Boolean,
  x: { type: Number, default: 0 },
  y: { type: Number, default: 0 },
  items: { type: Array, default: () => [] }
  // [{ label: 标签, action: 动作, type: 'item'|'separator' 类型, disabled: 禁用, shortcut: 快捷键 }]
})

const emit = defineEmits(['close', 'action'])

const handleClick = (item) => {
  if (item.disabled) return
  item.action()
  emit('close')
}

const close = () => emit('close')

onMounted(() => {
  window.addEventListener('click', close)
  window.addEventListener('contextmenu', close) // 在其他地方右键单击时关闭
  window.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') close()
  })
})

onUnmounted(() => {
  window.removeEventListener('click', close)
  window.removeEventListener('contextmenu', close)
  window.removeEventListener('keydown', close)
})
</script>
