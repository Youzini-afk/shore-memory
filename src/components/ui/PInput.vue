<script setup lang="ts">
import { useAttrs } from 'vue'
import PixelIcon from './PixelIcon.vue'

defineProps<{
  modelValue: string | number
  label?: string
  icon?: string
  type?: string
  placeholder?: string
  disabled?: boolean
  variant?: 'default' | 'white'
}>()

defineEmits<{
  (e: 'update:modelValue', value: string | number): void
}>()

const attrs = useAttrs()
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

    <div class="relative group/pinput w-full">
      <!-- 输入框主体 🐾 -->
      <input
        :type="type || 'text'"
        :value="modelValue"
        :placeholder="placeholder"
        :disabled="disabled"
        class="w-full px-4 py-2.5 border transition-all disabled:opacity-50 disabled:cursor-not-allowed font-sans text-sm relative z-10 rounded-2xl"
        :class="[
          variant === 'white'
            ? 'bg-white border-slate-100 focus:border-sky-300 focus:ring-4 focus:ring-sky-50'
            : 'bg-white/70 border-sky-100 focus:border-sky-300 focus:ring-4 focus:ring-sky-100',
          'text-slate-700 placeholder-slate-400 focus:outline-none hover:bg-white/90 hover:border-sky-200 focus:shadow-[0_0_20px_rgba(14,165,233,0.1)]'
        ]"
        v-bind="attrs"
        @input="$emit('update:modelValue', ($event.target as HTMLInputElement).value)"
      />

      <!-- 装饰性光晕 ✨ -->
      <div
        class="absolute inset-0 bg-sky-300/10 blur-xl rounded-2xl opacity-0 group-focus-within/pinput:opacity-100 transition-opacity duration-700 pointer-events-none"
      ></div>

      <!-- 可爱的小装饰 🐾 -->
      <div
        class="absolute right-3 top-1/2 -translate-y-1/2 opacity-0 group-hover/pinput:opacity-60 group-focus-within/pinput:opacity-100 group-focus-within/pinput:text-sky-400 transition-all duration-300 pointer-events-none z-20 text-[10px] select-none"
      >
        <PixelIcon name="paw" size="xs" />
      </div>

      <!-- 底部动态边框线 ⚡ -->
      <div
        class="absolute bottom-0 left-1/2 -translate-x-1/2 w-0 h-[2px] bg-gradient-to-r from-transparent via-sky-400 to-transparent group-focus-within/pinput:w-3/4 transition-all duration-500 rounded-full z-20"
      ></div>
    </div>
  </div>
</template>
