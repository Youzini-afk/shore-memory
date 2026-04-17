<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
import {
  FileText,
  Hash,
  History as HistoryIcon,
  Save,
  Archive,
  ArchiveRestore,
  Copy,
  Check,
  AlertTriangle,
  Link2
} from 'lucide-vue-next'
import PCard from '@/components/ui/PCard.vue'
import PBadge from '@/components/ui/PBadge.vue'
import PButton from '@/components/ui/PButton.vue'
import PTextarea from '@/components/ui/PTextarea.vue'
import PInput from '@/components/ui/PInput.vue'
import PSegment from '@/components/ui/PSegment.vue'
import PSlider from '@/components/ui/PSlider.vue'
import MetaField from './MetaField.vue'
import { useMemoriesStore } from '@/stores/memories'
import type { MemoryState, UpdateMemoryRequest } from '@/api/types'

const store = useMemoriesStore()
const { detail, entities, history, detailLoading, detailError, patchLoading, patchError, selectedId } =
  storeToRefs(store)

type Tab = 'overview' | 'metadata' | 'history'
const tab = ref<Tab>('overview')

/* ---------------- draft ---------------- */

interface Draft {
  content: string
  importance: number
  sentiment: string
  state: MemoryState
  tags: string
  valid_at: string
  invalid_at: string
  supersedes_memory_id: string
  metadataText: string
}

const draft = ref<Draft>(blankDraft())

function blankDraft(): Draft {
  return {
    content: '',
    importance: 5,
    sentiment: '',
    state: 'active',
    tags: '',
    valid_at: '',
    invalid_at: '',
    supersedes_memory_id: '',
    metadataText: '{}'
  }
}

function resetDraftFromDetail() {
  const m = detail.value
  if (!m) {
    draft.value = blankDraft()
    return
  }
  draft.value = {
    content: m.content ?? '',
    importance: Number.isFinite(m.importance) ? m.importance : 5,
    sentiment: m.sentiment ?? '',
    state: (m.state as MemoryState) ?? 'active',
    tags: (m.tags ?? []).join(', '),
    valid_at: m.valid_at ?? '',
    invalid_at: m.invalid_at ?? '',
    supersedes_memory_id: m.supersedes_memory_id != null ? String(m.supersedes_memory_id) : '',
    metadataText: JSON.stringify(m.metadata ?? {}, null, 2)
  }
  metadataError.value = null
}

watch(detail, () => resetDraftFromDetail(), { immediate: true })

/* ---------------- dirty diff ---------------- */

const metadataError = ref<string | null>(null)

const parsedTags = computed<string[]>(() =>
  draft.value.tags
    .split(',')
    .map((s) => s.trim())
    .filter((s) => s.length > 0)
)

const parsedMetadata = computed<Record<string, unknown> | null>(() => {
  const raw = draft.value.metadataText.trim()
  if (!raw) return {}
  try {
    const v = JSON.parse(raw)
    if (v && typeof v === 'object' && !Array.isArray(v)) {
      metadataError.value = null
      return v as Record<string, unknown>
    }
    metadataError.value = 'metadata 必须是对象'
    return null
  } catch (err) {
    metadataError.value = (err as Error).message
    return null
  }
})

function tagsEqual(a: string[], b: string[]): boolean {
  if (a.length !== b.length) return false
  for (let i = 0; i < a.length; i += 1) if (a[i] !== b[i]) return false
  return true
}

function jsonEqual(a: unknown, b: unknown): boolean {
  try {
    return JSON.stringify(a) === JSON.stringify(b)
  } catch {
    return false
  }
}

const patchBody = computed<UpdateMemoryRequest | null>(() => {
  const m = detail.value
  if (!m) return null
  const body: UpdateMemoryRequest = {}

  if (draft.value.content.trim() && draft.value.content !== m.content) {
    body.content = draft.value.content
  }
  if (
    Number.isFinite(draft.value.importance) &&
    Math.abs(draft.value.importance - m.importance) > 1e-6
  ) {
    body.importance = Math.round(draft.value.importance * 10) / 10
  }
  const nextSent = draft.value.sentiment.trim()
  const curSent = m.sentiment ?? ''
  if (nextSent !== curSent) {
    body.sentiment = nextSent ? nextSent : null
  }
  if (draft.value.state && draft.value.state !== m.state) {
    body.state = draft.value.state
  }
  if (!tagsEqual(parsedTags.value, m.tags ?? [])) {
    body.tags = parsedTags.value
  }
  if (draft.value.valid_at !== (m.valid_at ?? '')) {
    body.valid_at = draft.value.valid_at ? draft.value.valid_at : undefined
  }
  if (draft.value.invalid_at !== (m.invalid_at ?? '')) {
    body.invalid_at = draft.value.invalid_at ? draft.value.invalid_at : null
  }
  const curSup = m.supersedes_memory_id != null ? String(m.supersedes_memory_id) : ''
  if (draft.value.supersedes_memory_id !== curSup) {
    const n = draft.value.supersedes_memory_id.trim()
    if (!n) {
      body.supersedes_memory_id = null
    } else {
      const parsed = Number(n)
      if (Number.isFinite(parsed) && parsed > 0) body.supersedes_memory_id = parsed
    }
  }
  if (parsedMetadata.value !== null && !jsonEqual(parsedMetadata.value, m.metadata)) {
    body.metadata = parsedMetadata.value
  }
  return Object.keys(body).length ? body : null
})

const dirty = computed(() => patchBody.value !== null)
const canSave = computed(
  () =>
    dirty.value &&
    !patchLoading.value &&
    metadataError.value === null &&
    draft.value.content.trim().length > 0
)

async function save() {
  const body = patchBody.value
  if (!body) return
  try {
    await store.patch(body)
  } catch {
    // 错误已落到 store.patchError
  }
}

function discard() {
  resetDraftFromDetail()
}

/* ---------------- archive toggle ---------------- */

async function toggleArchive() {
  if (!detail.value) return
  try {
    if (detail.value.archived_at) {
      await store.unarchive()
    } else {
      await store.archive()
    }
  } catch {
    /* noop */
  }
}

/* ---------------- copy ---------------- */

const copied = ref<string | null>(null)
async function copy(text: string, key: string) {
  try {
    await navigator.clipboard.writeText(text)
    copied.value = key
    setTimeout(() => {
      if (copied.value === key) copied.value = null
    }, 1200)
  } catch {
    /* noop */
  }
}

/* ---------------- display helpers ---------------- */

const stateOptions: { label: string; value: MemoryState }[] = [
  { value: 'active', label: '有效' },
  { value: 'superseded', label: '已取代' },
  { value: 'invalidated', label: '已失效' },
  { value: 'archived', label: '已归档' }
]

function formatTime(s?: string | null): string {
  if (!s) return '—'
  const ts = Date.parse(s)
  if (Number.isNaN(ts)) return s
  const d = new Date(ts)
  return d.toLocaleString()
}

function formatRel(s?: string | null): string {
  if (!s) return ''
  const ts = Date.parse(s)
  if (Number.isNaN(ts)) return ''
  const diff = (Date.now() - ts) / 1000
  if (diff < 60) return `${Math.max(1, Math.floor(diff))} 秒前`
  if (diff < 3600) return `${Math.floor(diff / 60)} 分钟前`
  if (diff < 86400) return `${Math.floor(diff / 3600)} 小时前`
  if (diff < 86400 * 7) return `${Math.floor(diff / 86400)} 天前`
  return ''
}

const archiveBtnLabel = computed(() =>
  detail.value?.archived_at ? '恢复归档' : '归档'
)

const tabOptions = [
  { value: 'overview' as const, label: '概览' },
  { value: 'metadata' as const, label: '元数据' },
  { value: 'history' as const, label: '历史' }
]

const stateLabelMap: Record<MemoryState, string> = {
  active: '有效',
  superseded: '已取代',
  invalidated: '已失效',
  archived: '已归档'
}

function scopeLabel(scope: string | undefined | null): string {
  switch (scope) {
    case 'private':
      return '私有'
    case 'group':
      return '群组'
    case 'shared':
      return '共享'
    case 'system':
      return '系统'
    default:
      return scope || '—'
  }
}

function historyEventLabel(event: string | undefined | null): string {
  switch (event) {
    case 'archive':
      return '归档'
    case 'unarchive':
      return '恢复归档'
    case 'manual':
      return '手动修改'
    case 'supersede':
      return '被取代'
    case 'invalidate':
      return '失效'
    case 'update':
      return '自动更新'
    default:
      return event || '—'
  }
}
</script>

<template>
  <div class="flex flex-col min-h-0 h-full bg-shore-surface border-l border-shore-line/80">
    <!-- Empty -->
    <div
      v-if="selectedId === null"
      class="flex-1 flex flex-col items-center justify-center gap-3 px-6 text-center"
    >
      <div
        class="h-12 w-12 rounded-card bg-accent/10 border border-accent/20 flex items-center justify-center text-accent"
      >
        <FileText class="h-5 w-5" :stroke-width="1.75" />
      </div>
      <div class="font-display text-[14px] text-ink-1">未选中记忆</div>
      <div class="text-[11.5px] text-ink-4 max-w-xs">
        点击左侧列表查看详情，或使用筛选条件定位到具体记忆。
      </div>
    </div>

    <!-- Loading -->
    <div
      v-else-if="detailLoading && !detail"
      class="flex-1 p-6 flex flex-col gap-3"
    >
      <div class="h-6 w-40 rounded-btn bg-shore-elev animate-pulse" />
      <div class="h-20 rounded-panel bg-shore-elev animate-pulse" />
      <div class="h-4 w-full rounded-btn bg-shore-elev animate-pulse" />
      <div class="h-4 w-2/3 rounded-btn bg-shore-elev animate-pulse" />
    </div>

    <!-- Detail error -->
    <div
      v-else-if="detailError"
      class="m-6 rounded-btn bg-state-invalidated/10 border border-state-invalidated/30 px-4 py-3 text-[12.5px] text-state-invalidated flex items-start gap-2"
    >
      <AlertTriangle class="h-4 w-4 mt-0.5" :stroke-width="1.75" />
      <span>{{ detailError }}</span>
    </div>

    <!-- Content -->
    <template v-else-if="detail">
      <!-- Header -->
      <div class="px-6 pt-5 pb-4 border-b border-shore-line/80">
        <div class="flex items-center gap-2 text-[11px] font-display tracking-tight">
          <span class="tabular text-ink-4">#{{ detail.id }}</span>
          <PBadge :tone="detail.state as 'active' | 'superseded' | 'invalidated' | 'archived'" size="sm">
            {{ stateLabelMap[detail.state as MemoryState] ?? detail.state }}
          </PBadge>
          <PBadge tone="accent" size="sm">{{ scopeLabel(detail.scope) }}</PBadge>
          <PBadge tone="ink" size="sm">{{ detail.memory_type }}</PBadge>
          <span class="flex-1" />
          <button
            type="button"
            class="h-7 px-2.5 rounded-btn text-[11px] text-ink-3 hover:text-ink-1 hover:bg-shore-hover transition-colors flex items-center gap-1"
            @click="copy(String(detail.id), 'id')"
          >
            <component
              :is="copied === 'id' ? Check : Copy"
              class="h-3 w-3"
              :stroke-width="1.75"
            />
            复制 ID
          </button>
        </div>
        <div class="mt-2 text-[11.5px] text-ink-4 tabular">
          更新时间 · {{ formatTime(detail.updated_at) }}
          <span v-if="formatRel(detail.updated_at)" class="text-ink-5"
            >· {{ formatRel(detail.updated_at) }}</span
          >
        </div>
      </div>

      <!-- Tabs -->
      <div class="px-6 pt-4 pb-2 border-b border-shore-line/40 flex items-center gap-3">
        <PSegment v-model="tab" :options="tabOptions" size="sm" />
        <span class="flex-1" />
        <span v-if="dirty" class="text-[10.5px] font-display text-sig-amber flex items-center gap-1">
          <span class="h-1.5 w-1.5 rounded-full bg-sig-amber animate-pulse" />
          有未保存更改
        </span>
      </div>

      <!-- Body -->
      <div class="flex-1 min-h-0 overflow-y-auto">
        <!-- Overview tab -->
        <div v-if="tab === 'overview'" class="p-6 flex flex-col gap-5">
          <!-- Content -->
          <div>
            <div class="mb-1.5 text-[10.5px] uppercase tracking-[0.2em] font-display text-ink-5">
              内容
            </div>
            <PTextarea v-model="draft.content" :rows="5" placeholder="记忆内容" />
          </div>

          <!-- State + Importance -->
          <div class="grid grid-cols-2 gap-4">
            <div>
              <div class="mb-1.5 text-[10.5px] uppercase tracking-[0.2em] font-display text-ink-5">
                状态
              </div>
              <PSegment v-model="draft.state" :options="stateOptions" size="sm" block />
            </div>
            <div>
              <div
                class="mb-1.5 text-[10.5px] uppercase tracking-[0.2em] font-display text-ink-5 flex justify-between"
              >
                <span>重要度</span>
                <span class="tabular text-ink-2 normal-case tracking-normal">{{
                  draft.importance.toFixed(1)
                }}</span>
              </div>
              <PSlider v-model="draft.importance" :min="0" :max="10" :step="0.5" />
            </div>
          </div>

          <!-- Sentiment + tags -->
          <div class="grid grid-cols-2 gap-4">
            <div>
              <div class="mb-1.5 text-[10.5px] uppercase tracking-[0.2em] font-display text-ink-5">
                情感向
              </div>
              <PInput v-model="draft.sentiment" size="sm" placeholder="留空表示清除" />
            </div>
            <div>
              <div class="mb-1.5 text-[10.5px] uppercase tracking-[0.2em] font-display text-ink-5">
                标签 · 逗号分隔
              </div>
              <PInput v-model="draft.tags" size="sm" placeholder="例：tag1, tag2" />
            </div>
          </div>

          <!-- Lifecycle dates -->
          <div class="grid grid-cols-3 gap-4">
            <div>
              <div class="mb-1.5 text-[10.5px] uppercase tracking-[0.2em] font-display text-ink-5">
                生效时间
              </div>
              <PInput v-model="draft.valid_at" size="sm" placeholder="RFC 3339" mono />
            </div>
            <div>
              <div class="mb-1.5 text-[10.5px] uppercase tracking-[0.2em] font-display text-ink-5">
                失效时间
              </div>
              <PInput v-model="draft.invalid_at" size="sm" placeholder="留空为 null" mono />
            </div>
            <div>
              <div class="mb-1.5 text-[10.5px] uppercase tracking-[0.2em] font-display text-ink-5">
                取代记忆
              </div>
              <PInput v-model="draft.supersedes_memory_id" size="sm" placeholder="记忆 ID" mono />
            </div>
          </div>

          <!-- Timeline info -->
          <PCard compact edge>
            <div class="text-[10.5px] uppercase tracking-[0.2em] font-display text-ink-4 mb-2">
              时间轴
            </div>
            <MetaField label="创建时间">{{ formatTime(detail.created_at) }}</MetaField>
            <MetaField label="更新时间">{{ formatTime(detail.updated_at) }}</MetaField>
            <MetaField label="生效时间">{{ formatTime(detail.valid_at) }}</MetaField>
            <MetaField label="失效时间">{{ formatTime(detail.invalid_at) }}</MetaField>
            <MetaField label="归档时间">{{ formatTime(detail.archived_at) }}</MetaField>
            <MetaField label="最后访问">{{ formatTime(detail.last_accessed_at) }}</MetaField>
            <MetaField label="访问次数">
              <span class="tabular">{{ detail.access_count }}</span>
            </MetaField>
          </PCard>
        </div>

        <!-- Metadata tab -->
        <div v-else-if="tab === 'metadata'" class="p-6 flex flex-col gap-5">
          <PCard compact edge>
            <div class="text-[10.5px] uppercase tracking-[0.2em] font-display text-ink-4 mb-2">
              身份标识
            </div>
            <MetaField label="Agent" mono>{{ detail.agent_id }}</MetaField>
            <MetaField label="用户" mono>{{ detail.user_uid || '—' }}</MetaField>
            <MetaField label="频道" mono>{{ detail.channel_uid || '—' }}</MetaField>
            <MetaField label="会话" mono>{{ detail.session_uid || '—' }}</MetaField>
            <MetaField label="来源" mono>{{ detail.source }}</MetaField>
            <MetaField label="指纹" mono>
              <span v-if="detail.content_hash">{{ detail.content_hash }}</span>
              <span v-else class="text-ink-5">—</span>
            </MetaField>
          </PCard>

          <!-- Raw metadata JSON editor -->
          <div>
            <div class="mb-1.5 flex items-center justify-between">
              <div class="text-[10.5px] uppercase tracking-[0.2em] font-display text-ink-5">
                原始元数据（JSON）
              </div>
              <button
                type="button"
                class="h-6 px-2 rounded-btn text-[10.5px] text-ink-4 hover:text-ink-1 hover:bg-shore-hover flex items-center gap-1 transition-colors"
                @click="copy(draft.metadataText, 'meta')"
              >
                <component
                  :is="copied === 'meta' ? Check : Copy"
                  class="h-3 w-3"
                  :stroke-width="1.75"
                />
                复制
              </button>
            </div>
            <textarea
              v-model="draft.metadataText"
              rows="10"
              spellcheck="false"
              class="w-full rounded-panel bg-shore-bg border border-shore-line px-3 py-2 font-mono text-[12px] tabular text-ink-1 focus:outline-none focus:border-accent/60 focus:shadow-[0_0_0_3px_var(--accent-soft)] resize-y"
              :class="metadataError ? 'border-state-invalidated/50' : ''"
            />
            <div v-if="metadataError" class="mt-1 text-[11px] text-state-invalidated">
              {{ metadataError }}
            </div>
          </div>

          <!-- Source events / linked memories -->
          <div class="grid grid-cols-2 gap-4">
            <PCard compact edge>
              <div class="text-[10.5px] uppercase tracking-[0.2em] font-display text-ink-4 mb-2 flex items-center gap-1.5">
                <Hash class="h-3 w-3" :stroke-width="1.75" />
                来源事件 ID
              </div>
              <div v-if="detail.source_event_ids?.length" class="flex flex-wrap gap-1">
                <span
                  v-for="id in detail.source_event_ids"
                  :key="id"
                  class="h-6 px-2 rounded-btn bg-shore-elev border border-shore-line/70 text-[11px] tabular text-ink-2 flex items-center"
                >
                  {{ id }}
                </span>
              </div>
              <div v-else class="text-[11px] text-ink-5">—</div>
            </PCard>
            <PCard compact edge>
              <div class="text-[10.5px] uppercase tracking-[0.2em] font-display text-ink-4 mb-2 flex items-center gap-1.5">
                <Link2 class="h-3 w-3" :stroke-width="1.75" />
                关联记忆 ID
              </div>
              <div v-if="detail.linked_memory_ids?.length" class="flex flex-wrap gap-1">
                <button
                  v-for="id in detail.linked_memory_ids"
                  :key="id"
                  type="button"
                  class="h-6 px-2 rounded-btn bg-accent/10 border border-accent/30 text-[11px] tabular text-accent hover:bg-accent/20 transition-colors"
                  @click="store.select(id)"
                >
                  #{{ id }}
                </button>
              </div>
              <div v-else class="text-[11px] text-ink-5">—</div>
            </PCard>
          </div>

          <!-- Entities -->
          <PCard compact edge>
            <div class="text-[10.5px] uppercase tracking-[0.2em] font-display text-ink-4 mb-2">
              实体 · {{ entities.length }}
            </div>
            <div v-if="entities.length" class="flex flex-wrap gap-1.5">
              <span
                v-for="e in entities"
                :key="e.id"
                class="h-6 px-2 rounded-btn bg-shore-elev border border-shore-line/70 text-[11px] text-ink-2 flex items-center gap-1"
              >
                <span class="h-1 w-1 rounded-full bg-sig-blue" />
                {{ e.name }}
                <span v-if="e.entity_type" class="text-ink-5">· {{ e.entity_type }}</span>
              </span>
            </div>
            <div v-else class="text-[11px] text-ink-5">—</div>
          </PCard>
        </div>

        <!-- History tab -->
        <div v-else class="p-6">
          <div
            v-if="!history.length"
            class="py-10 text-center text-[12px] text-ink-4"
          >
            暂无历史记录
          </div>
          <ol v-else class="relative border-l border-shore-line/80 ml-2 pl-5 space-y-5">
            <li
              v-for="entry in history"
              :key="entry.id"
              class="relative"
            >
              <span
                class="absolute -left-[25px] top-1.5 h-2.5 w-2.5 rounded-full border-2 border-shore-surface"
                :class="
                  entry.event === 'archive'
                    ? 'bg-state-archived'
                    : entry.event === 'unarchive'
                      ? 'bg-state-active'
                      : entry.event === 'manual'
                        ? 'bg-accent'
                        : 'bg-sig-blue'
                "
              />
              <div class="flex items-center gap-2 text-[11px] font-display">
                <span class="text-ink-2 tracking-tight">{{ historyEventLabel(entry.event) }}</span>
                <span class="text-ink-5">·</span>
                <span class="tabular text-ink-4">{{ formatTime(entry.created_at) }}</span>
                <span v-if="entry.source_task_id" class="text-ink-5 tabular">
                  任务 #{{ entry.source_task_id }}
                </span>
              </div>
              <div
                v-if="entry.old_content && entry.new_content && entry.old_content !== entry.new_content"
                class="mt-2 grid grid-cols-2 gap-2"
              >
                <div class="rounded-btn bg-state-invalidated/8 border border-state-invalidated/20 p-2 text-[11.5px] text-ink-2 leading-[1.55]">
                  <div class="text-[9.5px] uppercase tracking-widest text-state-invalidated/80 mb-1">
                    修改前
                  </div>
                  {{ entry.old_content }}
                </div>
                <div class="rounded-btn bg-state-active/8 border border-state-active/20 p-2 text-[11.5px] text-ink-2 leading-[1.55]">
                  <div class="text-[9.5px] uppercase tracking-widest text-state-active/80 mb-1">
                    修改后
                  </div>
                  {{ entry.new_content }}
                </div>
              </div>
              <div
                v-else-if="entry.new_content"
                class="mt-2 rounded-btn bg-shore-card border border-shore-line/60 p-2 text-[11.5px] text-ink-2 leading-[1.55]"
              >
                {{ entry.new_content }}
              </div>
            </li>
          </ol>
        </div>
      </div>

      <!-- Footer actions -->
      <div class="shrink-0 border-t border-shore-line/80 px-6 py-3 flex items-center gap-2 bg-shore-surface">
        <PButton size="sm" variant="ghost" @click="toggleArchive" :loading="patchLoading">
          <component
            :is="detail.archived_at ? ArchiveRestore : Archive"
            class="h-3.5 w-3.5"
            :stroke-width="1.75"
          />
          {{ archiveBtnLabel }}
        </PButton>
        <span class="flex-1" />
        <PButton
          v-if="dirty"
          size="sm"
          variant="ghost"
          :disabled="patchLoading"
          @click="discard"
        >
          放弃修改
        </PButton>
        <PButton
          size="sm"
          variant="primary"
          :disabled="!canSave"
          :loading="patchLoading"
          @click="save"
        >
          <Save class="h-3.5 w-3.5" :stroke-width="1.75" />
          保存修改
        </PButton>
      </div>

      <!-- Patch error banner -->
      <div
        v-if="patchError"
        class="shrink-0 px-6 py-2 text-[11.5px] text-state-invalidated bg-state-invalidated/10 border-t border-state-invalidated/30 flex items-center gap-2"
      >
        <AlertTriangle class="h-3.5 w-3.5" :stroke-width="1.75" />
        {{ patchError }}
      </div>

      <!-- Rebuild hint -->
      <div
        v-if="store.lastRebuildTaskId"
        class="shrink-0 px-6 py-2 text-[11.5px] text-sig-amber bg-sig-amber/8 border-t border-sig-amber/25 flex items-center gap-2"
      >
        <HistoryIcon class="h-3.5 w-3.5" :stroke-width="1.75" />
        已排队重建 Trivium · 任务
        <span class="tabular">#{{ store.lastRebuildTaskId }}</span>
      </div>
    </template>
  </div>
</template>
