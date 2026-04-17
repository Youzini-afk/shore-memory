<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { Search, Sliders, RefreshCw, Download, X } from 'lucide-vue-next'
import PInput from '@/components/ui/PInput.vue'
import PSegment from '@/components/ui/PSegment.vue'
import PSwitch from '@/components/ui/PSwitch.vue'
import PButton from '@/components/ui/PButton.vue'
import { useMemoriesStore } from '@/stores/memories'
import type { MemoryScope, MemoryState } from '@/api/types'

const store = useMemoriesStore()
const { filter, listLoading, total, count } = storeToRefs(store)

const stateOptions: { label: string; value: MemoryState | '' }[] = [
  { value: '', label: '全部' },
  { value: 'active', label: '有效' },
  { value: 'superseded', label: '已取代' },
  { value: 'invalidated', label: '已失效' },
  { value: 'archived', label: '已归档' }
]

const scopeOptions: { label: string; value: MemoryScope | '' }[] = [
  { value: '', label: '全部' },
  { value: 'private', label: '私有' },
  { value: 'group', label: '群组' },
  { value: 'shared', label: '共享' },
  { value: 'system', label: '系统' }
]

const advanced = ref(false)

// 搜索框 debounce
const queryInput = ref(filter.value.content_query)
let debounceTimer: number | null = null
watch(queryInput, (v) => {
  if (debounceTimer !== null) window.clearTimeout(debounceTimer)
  debounceTimer = window.setTimeout(() => {
    filter.value.content_query = v.trim() || ''
    void store.reload()
  }, 300)
})

watch(
  () => [
    filter.value.state,
    filter.value.scope,
    filter.value.memory_type,
    filter.value.user_uid,
    filter.value.channel_uid,
    filter.value.session_uid,
    filter.value.include_archived
  ],
  () => {
    void store.reload()
  },
  { deep: false }
)

const hasFilters = computed(() => {
  const f = filter.value
  return !!(
    f.state ||
    f.scope ||
    f.memory_type ||
    f.content_query ||
    f.user_uid ||
    f.channel_uid ||
    f.session_uid ||
    f.include_archived
  )
})

function reset() {
  queryInput.value = ''
  store.resetFilter()
}

async function reload() {
  await store.reload()
}

async function exportJson() {
  try {
    await store.exportAll(true)
  } catch (err) {
    console.warn('[memories] export failed', err)
  }
}
</script>

<template>
  <div class="border-b border-shore-line/80 bg-shore-surface">
    <!-- Row 1 -->
    <div class="flex items-center gap-3 px-6 py-3">
      <PInput
        v-model="queryInput"
        size="sm"
        placeholder="搜索内容 · 正文全文检索"
        class="flex-1 max-w-md"
      >
        <template #prefix>
          <Search class="h-3.5 w-3.5" :stroke-width="1.75" />
        </template>
      </PInput>

      <div class="h-6 w-px bg-shore-line/80 shrink-0" />

      <label class="flex items-center gap-2 cursor-pointer select-none">
        <PSwitch v-model="filter.include_archived" />
        <span class="text-[12px] text-ink-2 font-display">含已归档</span>
      </label>

      <div class="flex-1" />

      <button
        type="button"
        class="h-8 px-3 rounded-btn text-[12px] font-display text-ink-3 hover:text-ink-1 hover:bg-shore-hover border border-transparent hover:border-shore-line transition-colors flex items-center gap-1.5"
        :class="advanced ? 'bg-shore-hover text-ink-1 border-shore-line' : ''"
        @click="advanced = !advanced"
      >
        <Sliders class="h-3.5 w-3.5" :stroke-width="1.75" />
        高级筛选
      </button>

      <button
        type="button"
        class="h-8 w-8 rounded-btn text-ink-3 hover:text-ink-1 hover:bg-shore-hover transition-colors flex items-center justify-center"
        title="刷新列表"
        :disabled="listLoading"
        @click="reload"
      >
        <RefreshCw
          class="h-3.5 w-3.5 transition-transform"
          :class="listLoading ? 'animate-spin' : ''"
          :stroke-width="1.75"
        />
      </button>

      <PButton size="sm" variant="ghost" @click="exportJson">
        <Download class="h-3.5 w-3.5" :stroke-width="1.75" />
        导出
      </PButton>

      <button
        v-if="hasFilters"
        type="button"
        class="h-8 px-2.5 rounded-btn text-[11.5px] font-display text-ink-4 hover:text-state-invalidated transition-colors flex items-center gap-1"
        @click="reset"
      >
        <X class="h-3 w-3" :stroke-width="1.75" />
        清除筛选
      </button>
    </div>

    <!-- Row 2: segment chips -->
    <div class="flex items-center gap-3 px-6 pb-3">
      <div class="flex items-center gap-2">
        <span class="text-[10.5px] uppercase tracking-[0.2em] font-display text-ink-5">状态</span>
        <PSegment v-model="filter.state" :options="stateOptions" size="sm" />
      </div>
      <div class="h-5 w-px bg-shore-line/80 shrink-0" />
      <div class="flex items-center gap-2">
        <span class="text-[10.5px] uppercase tracking-[0.2em] font-display text-ink-5">作用域</span>
        <PSegment v-model="filter.scope" :options="scopeOptions" size="sm" />
      </div>
      <div class="flex-1" />
      <div class="text-[11px] font-display text-ink-4 tabular">
        <span class="text-ink-1">{{ count }}</span>
        <span class="mx-1 text-ink-5">/</span>
        <span>{{ total }}</span>
        <span class="ml-1 text-ink-5">条已加载</span>
      </div>
    </div>

    <!-- Row 3: advanced -->
    <div
      v-if="advanced"
      class="grid grid-cols-4 gap-3 px-6 pb-4 pt-2 border-t border-shore-line/60 bg-shore-bg/30"
    >
      <div>
        <div class="mb-1 text-[10.5px] uppercase tracking-[0.2em] font-display text-ink-5">
          记忆类型
        </div>
        <PInput v-model="filter.memory_type" size="sm" placeholder="event / fact / promise ..." mono />
      </div>
      <div>
        <div class="mb-1 text-[10.5px] uppercase tracking-[0.2em] font-display text-ink-5">
          用户 UID
        </div>
        <PInput v-model="filter.user_uid" size="sm" placeholder="" mono />
      </div>
      <div>
        <div class="mb-1 text-[10.5px] uppercase tracking-[0.2em] font-display text-ink-5">
          频道 UID
        </div>
        <PInput v-model="filter.channel_uid" size="sm" placeholder="" mono />
      </div>
      <div>
        <div class="mb-1 text-[10.5px] uppercase tracking-[0.2em] font-display text-ink-5">
          会话 UID
        </div>
        <PInput v-model="filter.session_uid" size="sm" placeholder="" mono />
      </div>
    </div>
  </div>
</template>
