<script setup lang="ts">
interface Props {
  modelValue: string
  placeholder?: string
  rows?: number
  autosize?: boolean
  disabled?: boolean
}
withDefaults(defineProps<Props>(), { rows: 3 })
const emit = defineEmits<{
  (e: 'update:modelValue', value: string): void
  (e: 'submit', evt: KeyboardEvent): void
}>()

function onKeydown(evt: KeyboardEvent) {
  // \u2318/Ctrl + Enter => submit
  if ((evt.metaKey || evt.ctrlKey) && evt.key === 'Enter') {
    emit('submit', evt)
  }
}
</script>

<template>
  <label
    class="group relative flex flex-col rounded-btn bg-[#0F1018] border border-shore-line/80 transition-colors duration-240 ease-shore hover:border-shore-border focus-within:border-accent focus-within:shadow-[0_0_0_3px_rgba(124,92,255,0.18)]"
    :class="disabled ? 'opacity-50' : ''"
  >
    <textarea
      :value="modelValue"
      :rows="rows"
      :placeholder="placeholder"
      :disabled="disabled"
      class="w-full bg-transparent outline-none border-none resize-y p-3 text-[13px] leading-[1.55] text-ink-1 placeholder-ink-5 font-sans"
      @input="(e) => emit('update:modelValue', (e.target as HTMLTextAreaElement).value)"
      @keydown="onKeydown"
    />
    <div
      v-if="$slots.hint"
      class="px-3 py-1.5 border-t border-shore-line/80 text-[10.5px] text-ink-4 flex items-center gap-3"
    >
      <slot name="hint" />
    </div>
  </label>
</template>
