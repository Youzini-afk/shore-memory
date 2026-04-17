<script setup lang="ts">
interface Props {
  /** state = \u751f\u547d\u5468\u671f\u72b6\u6001\u8272\uff1badvisory = \u8f85\u52a9\u989c\u8272 */
  tone?:
    | 'active'
    | 'superseded'
    | 'invalidated'
    | 'archived'
    | 'accent'
    | 'blue'
    | 'amber'
    | 'ink'
  size?: 'sm' | 'md'
  dot?: boolean
}
withDefaults(defineProps<Props>(), { tone: 'ink', size: 'sm', dot: false })
</script>

<template>
  <span
    class="inline-flex items-center gap-1.5 rounded-pill border font-display tracking-wide uppercase select-none"
    :class="[
      size === 'sm' ? 'text-[10px] px-2 h-5' : 'text-[11px] px-2.5 h-6',
      tone === 'active' && 'text-state-active border-state-active/35 bg-state-active/10',
      tone === 'superseded' && 'text-state-superseded border-state-superseded/35 bg-state-superseded/10',
      tone === 'invalidated' && 'text-state-invalidated border-state-invalidated/35 bg-state-invalidated/10',
      tone === 'archived' && 'text-state-archived border-state-archived/35 bg-state-archived/10',
      tone === 'accent' && 'text-accent border-accent/35 bg-accent/10',
      tone === 'blue' && 'text-sig-blue border-sig-blue/35 bg-sig-blue/10',
      tone === 'amber' && 'text-sig-amber border-sig-amber/35 bg-sig-amber/10',
      tone === 'ink' && 'text-ink-3 border-shore-border bg-shore-card'
    ]"
  >
    <span v-if="dot" class="shore-dot" />
    <slot />
  </span>
</template>
