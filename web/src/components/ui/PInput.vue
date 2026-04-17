<script setup lang="ts">
import { computed } from 'vue'

interface Props {
  modelValue: string | number | null | undefined
  placeholder?: string
  type?: 'text' | 'search' | 'number' | 'url' | 'email' | 'password'
  size?: 'sm' | 'md'
  disabled?: boolean
  /** \u7ed9\u6570\u5b57\u5b57\u4f53\u4f7f\u7528 Geist Mono */
  mono?: boolean
  prefixIcon?: boolean
  suffixSlot?: boolean
}
const props = withDefaults(defineProps<Props>(), {
  type: 'text',
  size: 'md'
})

const emit = defineEmits<{
  (e: 'update:modelValue', value: string): void
  (e: 'enter', evt: KeyboardEvent): void
  (e: 'focus', evt: FocusEvent): void
  (e: 'blur', evt: FocusEvent): void
}>()

const sizeCls = computed(() =>
  props.size === 'sm' ? 'h-8 text-[12px] px-3' : 'h-10 text-[13px] px-3.5'
)
</script>

<template>
  <label
    class="group relative flex items-center rounded-btn bg-[#0F1018] border border-shore-line/80 transition-colors duration-240 ease-shore hover:border-shore-border focus-within:border-accent focus-within:shadow-[0_0_0_3px_rgba(124,92,255,0.18)]"
    :class="[disabled ? 'opacity-50 cursor-not-allowed' : '']"
  >
    <span
      v-if="$slots.prefix"
      class="pl-3 pr-1 text-ink-4 flex items-center"
    >
      <slot name="prefix" />
    </span>
    <input
      :value="modelValue ?? ''"
      :type="type"
      :disabled="disabled"
      :placeholder="placeholder"
      class="flex-1 min-w-0 bg-transparent outline-none border-none placeholder-ink-5 text-ink-1"
      :class="[sizeCls, mono ? 'font-mono tabular' : '']"
      @input="(e) => emit('update:modelValue', (e.target as HTMLInputElement).value)"
      @keydown.enter="(e) => emit('enter', e)"
      @focus="(e) => emit('focus', e)"
      @blur="(e) => emit('blur', e)"
    />
    <span
      v-if="$slots.suffix"
      class="pr-2 pl-1 text-ink-4 flex items-center"
    >
      <slot name="suffix" />
    </span>
  </label>
</template>
