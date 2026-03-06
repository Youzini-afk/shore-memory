<script setup lang="ts">
import { Calendar } from 'lucide-vue-next'

defineProps<{
  modelValue: string
  placeholder?: string
  disabled?: boolean
}>()

const emit = defineEmits(['update:modelValue'])

/**
 * 处理日期选择事件 📅
 */
const handleInput = (e: Event) => {
  const target = e.target as HTMLInputElement
  emit('update:modelValue', target.value)
}
</script>

<template>
  <div class="relative group/pdatepicker w-full">
    <!-- 选择器容器 🐾 -->
    <div
      class="flex items-center gap-3 px-4 py-2.5 bg-sky-50 border border-sky-100 rounded-xl transition-all hover:bg-sky-100/50 hover:border-sky-200 focus-within:border-sky-400 focus-within:ring-1 focus-within:ring-sky-400/30 focus-within:shadow-[0_0_20px_rgba(14,165,233,0.1)] relative z-10"
      :class="{ 'opacity-50 cursor-not-allowed': disabled }"
    >
      <!-- 日历图标 📅 -->
      <div class="relative shrink-0">
        <PixelIcon
          name="calendar"
          size="sm"
          class="text-slate-400 group-focus-within/pdatepicker:text-sky-500 transition-colors"
        />
        <!-- 装饰性闪烁 ✨ -->
        <span
          class="absolute -top-1 -right-1 text-[8px] opacity-0 group-hover/pdatepicker:opacity-100 transition-opacity animate-pulse select-none"
          >✨</span
        >
      </div>

      <!-- 原生日期输入 🖱️ -->
      <input
        type="date"
        :value="modelValue"
        :disabled="disabled"
        class="bg-transparent border-none text-slate-600 text-sm focus:outline-none w-full placeholder-slate-400 font-sans cursor-pointer [&::-webkit-calendar-picker-indicator]:opacity-0 [&::-webkit-calendar-picker-indicator]:absolute [&::-webkit-calendar-picker-indicator]:inset-0 [&::-webkit-calendar-picker-indicator]:cursor-pointer"
        @input="handleInput"
      />

      <!-- 可爱的小装饰 🐾 -->
      <div
        class="absolute right-3 top-1/2 -translate-y-1/2 opacity-0 group-hover/pdatepicker:opacity-40 group-focus-within/pdatepicker:opacity-100 group-focus-within/pdatepicker:text-sky-500/50 transition-all duration-300 pointer-events-none text-[10px] select-none"
      >
        🐾
      </div>
    </div>

    <!-- 装饰性背景光晕 ✨ -->
    <div
      class="absolute inset-0 bg-sky-500/5 blur-xl rounded-xl opacity-0 group-focus-within/pdatepicker:opacity-100 transition-opacity duration-700 pointer-events-none"
    ></div>
  </div>
</template>

<style scoped>
/* 隐藏原生日期选择器的图标，由我们自定义 🔍 */
input[type='date']::-webkit-inner-spin-button,
input[type='date']::-webkit-clear-button {
  display: none;
}
</style>
