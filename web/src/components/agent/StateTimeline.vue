<script setup lang="ts">
import { computed } from 'vue'
import { storeToRefs } from 'pinia'
import PCard from '@/components/ui/PCard.vue'
import PBadge from '@/components/ui/PBadge.vue'
import { useAgentStore, type AgentStateTimelineEntry } from '@/stores/agent'

const agentStore = useAgentStore()
const { timeline } = storeToRefs(agentStore)

const sourceLabel: Record<AgentStateTimelineEntry['source'], string> = {
  remote: '初始快照',
  event: '服务端广播',
  local: '本地保存'
}

function sourceTone(
  source: AgentStateTimelineEntry['source']
): 'accent' | 'blue' | 'ink' {
  switch (source) {
    case 'event':
      return 'blue'
    case 'local':
      return 'accent'
    default:
      return 'ink'
  }
}

function formatTime(iso: string): string {
  const ts = Date.parse(iso)
  if (Number.isNaN(ts)) return iso
  const now = new Date()
  const sameDay = new Date(ts).toDateString() === now.toDateString()
  if (sameDay) {
    return new Date(ts).toLocaleTimeString(undefined, {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    })
  }
  return new Date(ts).toLocaleString(undefined, {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}

function fieldLabel(f: 'mood' | 'vibe' | 'mind'): string {
  return f === 'mood' ? '心情' : f === 'vibe' ? '氛围' : '心绪'
}

function fieldTone(
  f: 'mood' | 'vibe' | 'mind'
): 'accent' | 'blue' | 'amber' {
  return f === 'mood' ? 'accent' : f === 'vibe' ? 'blue' : 'amber'
}

const hasEntries = computed(() => timeline.value.length > 0)
</script>

<template>
  <PCard edge class="flex flex-col gap-4">
    <div class="flex items-center justify-between gap-3">
      <div>
        <div class="font-display text-[14px] text-ink-1">最近状态变更</div>
        <div class="mt-0.5 text-[11.5px] text-ink-4">
          本地缓冲 {{ timeline.length }} 条，会话结束后清空
        </div>
      </div>
      <PBadge tone="ink" size="sm">内存 · 不持久化</PBadge>
    </div>

    <div v-if="!hasEntries" class="py-8 text-center text-[12px] text-ink-4">
      暂无变更。评分 / 反思任务完成，或手动保存后会出现在这里。
    </div>

    <ol v-else class="flex flex-col gap-0">
      <li
        v-for="(entry, idx) in timeline"
        :key="entry.at + '-' + idx"
        class="relative pl-6 py-2 border-l border-shore-line/60"
        :class="idx === 0 ? 'border-l-accent/40' : ''"
      >
        <span
          class="absolute left-[-5px] top-[14px] shore-dot"
          :class="idx === 0 ? 'bg-accent' : 'bg-ink-5'"
        />
        <div class="flex items-center gap-2 flex-wrap">
          <span class="text-[11.5px] text-ink-2 tabular">
            {{ formatTime(entry.at) }}
          </span>
          <PBadge :tone="sourceTone(entry.source)" size="sm">
            {{ sourceLabel[entry.source] }}
          </PBadge>
          <PBadge
            v-for="f in entry.changed"
            :key="f"
            :tone="fieldTone(f)"
            size="sm"
          >
            {{ fieldLabel(f) }}
          </PBadge>
        </div>
        <div class="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-[12px]">
          <span
            v-for="f in (['mood', 'vibe', 'mind'] as const)"
            :key="f"
            class="inline-flex items-baseline gap-1.5"
            :class="
              entry.changed.includes(f) ? 'text-ink-1' : 'text-ink-4'
            "
          >
            <span class="text-[10px] tracking-wide uppercase text-ink-5">{{ f }}</span>
            <span
              class="truncate max-w-[180px]"
              :title="entry[f]"
            >{{ entry[f] || '—' }}</span>
          </span>
        </div>
      </li>
    </ol>
  </PCard>
</template>
