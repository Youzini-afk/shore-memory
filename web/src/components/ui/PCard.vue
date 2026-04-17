<script setup lang="ts">
interface Props {
  /** 轻薄高光顶线 */
  edge?: boolean
  /** 紧凑 padding */
  compact?: boolean
}
defineProps<Props>()
</script>

<template>
  <div
    class="relative rounded-card bg-shore-card border border-shore-line/80"
    :class="compact ? 'p-4' : 'p-6'"
  >
    <div
      v-if="edge"
      class="pointer-events-none absolute inset-x-4 top-0 h-px bg-gradient-to-r from-transparent via-accent/40 to-transparent"
    />
    <slot />
  </div>
</template>
