<script setup lang="ts" generic="T extends string | number">
interface Option {
  label: string
  value: T
  hint?: string
}
interface Props {
  modelValue: T
  options: Option[]
  size?: 'sm' | 'md'
  block?: boolean
}
const props = withDefaults(defineProps<Props>(), { size: 'md' })
const emit = defineEmits<{
  (e: 'update:modelValue', v: T): void
}>()

function isSelected(v: T) {
  return v === props.modelValue
}
</script>

<template>
  <div
    class="inline-flex bg-[#0F1018] border border-shore-line/80 rounded-btn p-0.5 gap-0.5"
    :class="[block ? 'w-full' : '', size === 'sm' ? 'text-[11.5px]' : 'text-[12.5px]']"
  >
    <button
      v-for="opt in options"
      :key="String(opt.value)"
      type="button"
      class="relative flex-1 px-3 rounded-[8px] font-display transition-all duration-240 ease-shore select-none whitespace-nowrap"
      :class="[
        size === 'sm' ? 'h-[26px]' : 'h-8',
        isSelected(opt.value)
          ? 'bg-accent/15 text-ink-1 shadow-[inset_0_0_0_1px_rgba(124,92,255,0.45)]'
          : 'text-ink-3 hover:text-ink-1 hover:bg-shore-hover'
      ]"
      :title="opt.hint"
      @click="emit('update:modelValue', opt.value)"
    >
      {{ opt.label }}
    </button>
  </div>
</template>
