<script setup lang="ts">
import { computed } from 'vue'
import PixelIcon from './PixelIcon.vue'

const props = defineProps<{
  modelValue?: boolean
  label?: string
  disabled?: boolean
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
  (e: 'change', value: boolean): void
}>()

/**
 * 双向绑定勾选状态 🐾
 */
const isChecked = computed({
  get: () => props.modelValue || false,
  set: (val) => {
    emit('update:modelValue', val)
    emit('change', val)
  }
})

/**
 * 切换勾选状态 🐾
 */
const toggle = () => {
  if (props.disabled) return
  isChecked.value = !isChecked.value
}
</script>

<template>
  <div
    class="flex items-center gap-2.5 cursor-pointer select-none group/pcheckbox"
    :class="{ 'opacity-50 cursor-not-allowed': disabled }"
    @click="toggle"
  >
    <!-- 复选框主体 🐾 -->
    <div
      class="w-5 h-5 rounded-lg border-2 flex items-center justify-center transition-all duration-300 group-active/pcheckbox:scale-90 relative overflow-hidden"
      :class="[
        isChecked
          ? 'bg-sky-400 border-sky-400 text-white shadow-lg shadow-sky-400/20'
          : 'bg-white/70 border-sky-100 group-hover/pcheckbox:border-sky-300 group-hover/pcheckbox:bg-sky-50'
      ]"
    >
      <PixelIcon v-if="isChecked" name="check" size="xs" class="animate-in zoom-in duration-300" />

      <!-- 勾选时的闪烁装饰 ✨ -->
      <div v-if="isChecked" class="absolute -top-1 -right-1 text-[8px] animate-bounce select-none">
        <PixelIcon name="sparkle" size="xs" />
      </div>

      <!-- 未勾选时的悬浮提示 🐾 -->
      <div
        v-if="!isChecked"
        class="absolute inset-0 flex items-center justify-center opacity-0 group-hover/pcheckbox:opacity-30 transition-opacity text-[8px] select-none text-sky-400"
      >
        <PixelIcon name="paw" size="xs" />
      </div>
    </div>

    <!-- 标签文本 🐱 -->
    <span
      v-if="label || $slots.default"
      class="text-sm text-slate-600 group-hover/pcheckbox:text-sky-500 transition-colors"
    >
      <slot>{{ label }}</slot>
    </span>
  </div>
</template>
