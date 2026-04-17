<script setup lang="ts">
import { hotkeyLabel } from '@/composables/useHotkeys'

interface Props {
  /** "mod+enter" 类的 spec；不填就用 slot 渲染 */
  combo?: string
}
defineProps<Props>()
</script>

<template>
  <kbd
    class="inline-flex items-center gap-1 px-1.5 h-5 rounded-[6px] border border-shore-border bg-shore-elev text-[10px] text-ink-3 font-mono tabular"
  >
    <template v-if="combo">{{ hotkeyLabel(combo) }}</template>
    <slot v-else />
  </kbd>
</template>
