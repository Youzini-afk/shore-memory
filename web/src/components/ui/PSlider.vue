<script setup lang="ts">
import { computed } from 'vue'

interface Props {
  modelValue: number
  min?: number
  max?: number
  step?: number
  disabled?: boolean
}
const props = withDefaults(defineProps<Props>(), { min: 0, max: 10, step: 1 })
const emit = defineEmits<{
  (e: 'update:modelValue', v: number): void
}>()

const percent = computed(() => {
  if (props.max === props.min) return 0
  return Math.max(
    0,
    Math.min(100, ((props.modelValue - props.min) / (props.max - props.min)) * 100)
  )
})
</script>

<template>
  <div class="flex items-center gap-3">
    <div class="relative flex-1 h-8 flex items-center">
      <div class="absolute inset-x-0 h-1 rounded-full bg-shore-line/80" />
      <div
        class="absolute h-1 rounded-full bg-gradient-to-r from-accent-hi to-accent-lo"
        :style="{ width: `${percent}%` }"
      />
      <input
        :value="modelValue"
        :min="min"
        :max="max"
        :step="step"
        :disabled="disabled"
        type="range"
        class="p-slider-range relative w-full h-8 appearance-none bg-transparent focus-visible:outline-none"
        @input="(e) => emit('update:modelValue', Number((e.target as HTMLInputElement).value))"
      />
    </div>
    <span class="font-display tabular text-[12px] text-ink-1 w-10 text-right">{{ modelValue }}</span>
  </div>
</template>

<style scoped>
.p-slider-range {
  --thumb-size: 14px;
  accent-color: var(--accent);
}
.p-slider-range::-webkit-slider-runnable-track {
  height: 4px;
  background: transparent;
}
.p-slider-range::-moz-range-track {
  height: 4px;
  background: transparent;
}
.p-slider-range::-webkit-slider-thumb {
  -webkit-appearance: none;
  appearance: none;
  width: var(--thumb-size);
  height: var(--thumb-size);
  background: #fff;
  border-radius: 999px;
  margin-top: -5px;
  box-shadow: 0 0 0 2px var(--accent), 0 2px 8px rgba(124, 92, 255, 0.35);
  cursor: pointer;
}
.p-slider-range::-moz-range-thumb {
  width: var(--thumb-size);
  height: var(--thumb-size);
  background: #fff;
  border: none;
  border-radius: 999px;
  box-shadow: 0 0 0 2px var(--accent), 0 2px 8px rgba(124, 92, 255, 0.35);
  cursor: pointer;
}
.p-slider-range:focus-visible::-webkit-slider-thumb {
  box-shadow: 0 0 0 3px var(--accent-hi), 0 2px 10px rgba(124, 92, 255, 0.55);
}
</style>
