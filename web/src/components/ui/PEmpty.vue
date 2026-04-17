<script setup lang="ts">
import { Sparkles } from 'lucide-vue-next'
interface Props {
  title?: string
  hint?: string
  milestone?: string
}
defineProps<Props>()
</script>

<template>
  <div class="flex flex-col items-center justify-center py-20 px-6 text-center gap-3">
    <div
      class="h-12 w-12 rounded-card bg-accent/10 border border-accent/20 flex items-center justify-center text-accent"
    >
      <Sparkles class="h-5 w-5" :stroke-width="1.75" />
    </div>
    <div class="font-display text-[15px] text-ink-1">{{ title ?? '功能待落地' }}</div>
    <div class="max-w-md text-[12px] text-ink-4 leading-relaxed">
      {{ hint ?? '该页将在下一个里程碑接入真实数据。' }}
    </div>
    <div
      v-if="milestone"
      class="mt-1 text-[10px] font-display tracking-wider uppercase text-accent/80 px-2 py-0.5 rounded-pill border border-accent/30"
    >
      {{ milestone }}
    </div>
  </div>
</template>
