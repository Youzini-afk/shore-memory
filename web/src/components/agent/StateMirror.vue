<script setup lang="ts">
import { computed } from 'vue'
import { storeToRefs } from 'pinia'
import PCard from '@/components/ui/PCard.vue'
import PBadge from '@/components/ui/PBadge.vue'
import { useAgentStore } from '@/stores/agent'
import { useAppStore } from '@/stores/app'

const agentStore = useAgentStore()
const app = useAppStore()
const { remote, loading, error, flashFields } = storeToRefs(agentStore)

interface FieldMeta {
  key: 'mood' | 'vibe' | 'mind'
  label: string
  hint: string
  tone: 'accent' | 'blue' | 'amber'
}

const FIELDS: FieldMeta[] = [
  { key: 'mood', label: 'MOOD · 心情', hint: '当前情绪色彩', tone: 'accent' },
  { key: 'vibe', label: 'VIBE · 氛围', hint: '会话节奏 / 能量', tone: 'blue' },
  { key: 'mind', label: 'MIND · 心绪', hint: '正在做的内部活动', tone: 'amber' }
]

const updatedAgo = computed(() => {
  const iso = remote.value?.updated_at
  if (!iso) return null
  const ts = Date.parse(iso)
  if (Number.isNaN(ts)) return iso
  const diff = Date.now() - ts
  if (diff < 10_000) return '刚刚'
  if (diff < 60_000) return `${Math.floor(diff / 1000)} 秒前`
  if (diff < 3_600_000) return `${Math.floor(diff / 60_000)} 分钟前`
  if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)} 小时前`
  return new Date(ts).toLocaleString()
})

function valueFor(key: 'mood' | 'vibe' | 'mind'): string {
  return remote.value?.[key] ?? '—'
}

function isFlashing(key: 'mood' | 'vibe' | 'mind') {
  return flashFields.value.includes(key)
}

function toneDotColor(tone: FieldMeta['tone']) {
  switch (tone) {
    case 'accent':
      return 'bg-accent'
    case 'blue':
      return 'bg-sig-blue'
    case 'amber':
      return 'bg-sig-amber'
  }
}
</script>

<template>
  <PCard edge class="flex flex-col gap-4">
    <div class="flex items-center justify-between gap-3">
      <div class="flex items-center gap-2">
        <PBadge tone="accent" size="sm" dot>Agent · {{ app.agentId }}</PBadge>
        <PBadge v-if="loading" tone="ink" size="sm">加载中…</PBadge>
        <PBadge v-else-if="error" tone="invalidated" size="sm">加载失败</PBadge>
      </div>
      <div class="text-[11px] text-ink-4 tabular">
        <template v-if="updatedAgo">更新于 {{ updatedAgo }}</template>
        <template v-else>等待首次同步</template>
      </div>
    </div>

    <div class="flex flex-col divide-y divide-shore-line/60">
      <div
        v-for="field in FIELDS"
        :key="field.key"
        class="relative py-4 first:pt-2 last:pb-2"
      >
        <div class="flex items-baseline gap-3">
          <span
            class="shore-dot transition-all duration-240 ease-shore"
            :class="[
              toneDotColor(field.tone),
              isFlashing(field.key)
                ? 'shadow-[0_0_0_6px_rgba(124,92,255,0.18)] scale-125'
                : 'opacity-80'
            ]"
          />
          <div class="flex-1 min-w-0">
            <div class="text-[10.5px] tracking-[0.16em] uppercase text-ink-4 font-display">
              {{ field.label }}
            </div>
            <div
              class="mt-1.5 font-display text-ink-1 truncate transition-colors duration-240 ease-shore"
              :class="[
                isFlashing(field.key) ? 'text-accent' : 'text-ink-1',
                valueFor(field.key).length > 16 ? 'text-[18px]' : 'text-[22px]'
              ]"
              :title="valueFor(field.key)"
            >
              {{ valueFor(field.key) }}
            </div>
            <div class="mt-1 text-[11px] text-ink-4">{{ field.hint }}</div>
          </div>
        </div>
      </div>
    </div>

    <p v-if="error" class="text-[11.5px] text-state-invalidated">
      {{ error }}
    </p>
  </PCard>
</template>
