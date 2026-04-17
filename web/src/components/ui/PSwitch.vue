<script setup lang="ts">
interface Props {
  modelValue: boolean
  disabled?: boolean
}
defineProps<Props>()
const emit = defineEmits<{
  (e: 'update:modelValue', v: boolean): void
}>()
</script>

<template>
  <button
    type="button"
    role="switch"
    :aria-checked="modelValue"
    :disabled="disabled"
    class="relative inline-flex h-5 w-9 items-center rounded-pill transition-all duration-240 ease-shore focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-shore-bg disabled:opacity-40 disabled:cursor-not-allowed"
    :class="modelValue ? 'bg-accent/80 shadow-accent-sm' : 'bg-shore-line'"
    @click="emit('update:modelValue', !modelValue)"
  >
    <span
      class="inline-block h-3.5 w-3.5 bg-white rounded-pill transform transition-transform duration-240 ease-shore shadow"
      :class="modelValue ? 'translate-x-[18px]' : 'translate-x-[2px]'"
    />
  </button>
</template>
