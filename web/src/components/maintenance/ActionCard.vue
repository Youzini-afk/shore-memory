<script setup lang="ts">
import { computed, ref } from 'vue'
import PButton from '@/components/ui/PButton.vue'
import PBadge from '@/components/ui/PBadge.vue'
import type { MaintenanceActionRun } from '@/stores/maintenance'

interface Props {
  title: string
  description: string
  /** 左上角小标签，例如"同步·安全"或"异步·耗 LLM" */
  tag: string
  tagTone?: 'ink' | 'amber' | 'blue' | 'invalidated'
  /** 主按钮文案 */
  buttonLabel: string
  buttonVariant?: 'primary' | 'secondary' | 'danger'
  /** 如果需要二次确认（内联） */
  requireConfirm?: boolean
  confirmLabel?: string
  run: MaintenanceActionRun
  disabled?: boolean
}
const props = withDefaults(defineProps<Props>(), {
  tagTone: 'ink',
  buttonVariant: 'secondary',
  requireConfirm: false,
  confirmLabel: '再点一次确认'
})

const emit = defineEmits<{
  (e: 'trigger'): void
}>()

const confirming = ref(false)
let confirmTimer: number | null = null

function armConfirm() {
  confirming.value = true
  if (confirmTimer !== null) window.clearTimeout(confirmTimer)
  confirmTimer = window.setTimeout(() => {
    confirming.value = false
    confirmTimer = null
  }, 4000)
}

function handleClick() {
  if (props.disabled) return
  if (props.requireConfirm && !confirming.value) {
    armConfirm()
    return
  }
  confirming.value = false
  if (confirmTimer !== null) {
    window.clearTimeout(confirmTimer)
    confirmTimer = null
  }
  emit('trigger')
}

const statusBadge = computed<{
  tone: 'ink' | 'active' | 'amber' | 'accent' | 'invalidated'
  label: string
} | null>(() => {
  switch (props.run.status) {
    case 'pending':
      return { tone: 'accent', label: '发送中…' }
    case 'queued':
      return { tone: 'amber', label: '已入队' }
    case 'success':
      return { tone: 'active', label: '已完成' }
    case 'error':
      return { tone: 'invalidated', label: '失败' }
    default:
      return null
  }
})

const lastMessage = computed(() => {
  if (props.run.error) return props.run.error
  if (props.run.message) return props.run.message
  return null
})

const settledAgo = computed(() => {
  const ts = props.run.settledAt ?? props.run.startedAt
  if (!ts) return null
  const diff = Date.now() - ts
  if (diff < 1000) return '刚刚'
  if (diff < 60_000) return `${Math.floor(diff / 1000)} 秒前`
  if (diff < 3_600_000) return `${Math.floor(diff / 60_000)} 分钟前`
  return new Date(ts).toLocaleTimeString()
})

const busy = computed(
  () => props.run.status === 'pending' || props.run.status === 'queued'
)
</script>

<template>
  <div class="rounded-card bg-shore-card border border-shore-line/80 p-4 flex flex-col gap-3">
    <div class="flex items-start justify-between gap-3">
      <div class="min-w-0">
        <div class="flex items-center gap-2">
          <PBadge :tone="tagTone" size="sm">{{ tag }}</PBadge>
          <PBadge v-if="statusBadge" :tone="statusBadge.tone" size="sm" dot>
            {{ statusBadge.label }}
          </PBadge>
        </div>
        <div class="mt-2 font-display text-[14px] text-ink-1">{{ title }}</div>
        <div class="mt-1 text-[11.5px] text-ink-4">{{ description }}</div>
      </div>
    </div>

    <div class="flex items-center justify-between gap-2">
      <div class="text-[11px] text-ink-5 min-h-[14px]">
        <template v-if="run.taskId !== null && run.taskId !== undefined">
          task #<span class="tabular text-ink-3">{{ run.taskId }}</span>
          <span v-if="settledAgo" class="ml-2">· {{ settledAgo }}</span>
        </template>
        <template v-else-if="settledAgo">· {{ settledAgo }}</template>
      </div>
      <PButton
        size="sm"
        :variant="confirming ? 'danger' : buttonVariant"
        :loading="busy"
        :disabled="disabled"
        @click="handleClick"
      >
        {{ confirming ? confirmLabel : buttonLabel }}
      </PButton>
    </div>

    <div
      v-if="lastMessage"
      class="rounded-btn px-3 py-2 text-[11.5px] border"
      :class="
        run.error
          ? 'border-state-invalidated/30 bg-state-invalidated/10 text-state-invalidated'
          : 'border-shore-line/70 bg-[#0F1018] text-ink-3'
      "
    >
      <pre class="whitespace-pre-wrap break-words font-mono text-[11.5px]">{{ lastMessage }}</pre>
    </div>
  </div>
</template>
