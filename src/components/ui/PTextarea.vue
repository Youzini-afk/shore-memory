<script setup lang="ts">
import PixelIcon from './PixelIcon.vue'

defineProps<{
  modelValue: string
  label?: string
  icon?: string
  placeholder?: string
  rows?: number
  disabled?: boolean
}>()

const emit = defineEmits(['update:modelValue'])

/**
 * 处理文本域输入事件 🐾
 */
const handleInput = (e: Event) => {
  const target = e.target as HTMLTextAreaElement
  emit('update:modelValue', target.value)
}
</script>

<template>
  <div class="space-y-2 w-full">
    <!-- 标签 🐾 -->
    <label
      v-if="label"
      class="text-[10px] font-black text-slate-400 uppercase tracking-widest flex items-center gap-2 px-1"
    >
      <PixelIcon v-if="icon" :name="icon" size="xs" class="opacity-70" />
      {{ label }}
    </label>

    <div class="relative group/ptextarea w-full">
      <!-- 文本域主体 🐾 -->
      <textarea
        :value="modelValue"
        :rows="rows || 3"
        :placeholder="placeholder"
        :disabled="disabled"
        class="w-full px-4 py-3 bg-white/50 border border-sky-100 rounded-2xl text-sm text-slate-700 placeholder-slate-400 focus:outline-none focus:border-sky-400 focus:ring-4 focus:ring-sky-100 transition-all hover:bg-white/80 hover:border-sky-200 focus:shadow-[0_0_20px_rgba(14,165,233,0.1)] resize-none custom-scrollbar relative z-10 font-sans leading-relaxed"
        :class="{ 'opacity-50 cursor-not-allowed': disabled }"
        @input="handleInput"
      ></textarea>

      <!-- 装饰性光晕 ✨ -->
      <div
        class="absolute inset-0 bg-sky-500/5 blur-xl rounded-2xl opacity-0 group-focus-within/ptextarea:opacity-100 transition-opacity duration-700 pointer-events-none"
      ></div>

      <!-- 可爱的小装饰 🐾 -->
      <div
        class="absolute right-4 bottom-3 opacity-0 group-hover/ptextarea:opacity-40 group-focus-within/ptextarea:opacity-100 group-focus-within/ptextarea:text-sky-500/50 transition-all duration-300 pointer-events-none z-20 text-[10px] select-none"
      >
        <PixelIcon name="paw" size="xs" />
      </div>

      <!-- 底部动态装饰线 ⚡ -->
      <div
        class="absolute bottom-0 left-1/2 -translate-x-1/2 w-0 h-[2px] bg-gradient-to-r from-transparent via-sky-500/40 to-transparent group-focus-within/ptextarea:w-2/3 transition-all duration-700 rounded-full z-20"
      ></div>
    </div>
  </div>
</template>

<style scoped>
/* 自定义滚动条样式 🐾 */
.custom-scrollbar::-webkit-scrollbar {
  width: 4px;
}
.custom-scrollbar::-webkit-scrollbar-track {
  background: transparent;
}
.custom-scrollbar::-webkit-scrollbar-thumb {
  background: rgba(14, 165, 233, 0.2);
  border-radius: 10px;
}
.custom-scrollbar::-webkit-scrollbar-thumb:hover {
  background: rgba(14, 165, 233, 0.4);
}
</style>
