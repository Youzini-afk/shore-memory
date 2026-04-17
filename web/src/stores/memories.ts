import { defineStore } from 'pinia'
import { ref, computed, watch } from 'vue'
import { useAppStore } from './app'
import { listMemories, getMemory, updateMemory, exportMemories } from '@/api/memories'
import { getEventsClient } from '@/api/events'
import { ShoreApiError } from '@/api/http'
import type {
  ListMemoriesRequest,
  MemoryRecord,
  MemoryHistoryRecord,
  EntityRecord,
  UpdateMemoryRequest,
  MemoryState,
  MemoryScope
} from '@/api/types'

export interface MemoryFilter {
  state: MemoryState | ''
  scope: MemoryScope | ''
  memory_type: string
  content_query: string
  user_uid: string
  channel_uid: string
  session_uid: string
  include_archived: boolean
}

const PAGE_SIZE = 80

export const useMemoriesStore = defineStore('memories', () => {
  const app = useAppStore()

  /* ---------------- list ---------------- */

  const items = ref<MemoryRecord[]>([])
  const total = ref(0)
  const offset = ref(0)
  const listLoading = ref(false)
  const listError = ref<string | null>(null)
  const filter = ref<MemoryFilter>({
    state: '',
    scope: '',
    memory_type: '',
    content_query: '',
    user_uid: '',
    channel_uid: '',
    session_uid: '',
    include_archived: false
  })

  const hasMore = computed(() => items.value.length < total.value)
  const count = computed(() => items.value.length)

  function buildListReq(nextOffset: number): ListMemoriesRequest {
    const f = filter.value
    return {
      agent_id: app.agentId,
      scope: f.scope || undefined,
      state: f.state || undefined,
      memory_type: f.memory_type.trim() || undefined,
      content_query: f.content_query.trim() || undefined,
      user_uid: f.user_uid.trim() || undefined,
      channel_uid: f.channel_uid.trim() || undefined,
      session_uid: f.session_uid.trim() || undefined,
      include_archived: f.include_archived || undefined,
      limit: PAGE_SIZE,
      offset: nextOffset
    }
  }

  async function reload() {
    listLoading.value = true
    listError.value = null
    offset.value = 0
    try {
      const res = await listMemories(buildListReq(0))
      items.value = res.items
      total.value = res.total
      offset.value = res.items.length
    } catch (err) {
      listError.value = err instanceof ShoreApiError ? err.message : (err as Error).message
      items.value = []
      total.value = 0
    } finally {
      listLoading.value = false
    }
  }

  async function loadMore() {
    if (listLoading.value || !hasMore.value) return
    listLoading.value = true
    try {
      const res = await listMemories(buildListReq(offset.value))
      // 去重追加
      const seen = new Set(items.value.map((m) => m.id))
      for (const m of res.items) {
        if (!seen.has(m.id)) items.value.push(m)
      }
      total.value = res.total
      offset.value = items.value.length
    } catch (err) {
      listError.value = err instanceof ShoreApiError ? err.message : (err as Error).message
    } finally {
      listLoading.value = false
    }
  }

  /* ---------------- selection ---------------- */

  const selectedId = ref<number | null>(null)
  const detail = ref<MemoryRecord | null>(null)
  const entities = ref<EntityRecord[]>([])
  const history = ref<MemoryHistoryRecord[]>([])
  const detailLoading = ref(false)
  const detailError = ref<string | null>(null)

  async function select(id: number | null) {
    selectedId.value = id
    if (id === null) {
      detail.value = null
      entities.value = []
      history.value = []
      return
    }
    detailLoading.value = true
    detailError.value = null
    try {
      const res = await getMemory(id)
      detail.value = res.memory
      entities.value = res.entities
      history.value = res.history
    } catch (err) {
      detailError.value = err instanceof ShoreApiError ? err.message : (err as Error).message
      detail.value = null
      entities.value = []
      history.value = []
    } finally {
      detailLoading.value = false
    }
  }

  /* ---------------- patch ---------------- */

  const patchLoading = ref(false)
  const patchError = ref<string | null>(null)
  const lastRebuildTaskId = ref<number | null>(null)

  async function patch(patchBody: UpdateMemoryRequest) {
    if (selectedId.value === null) return
    patchLoading.value = true
    patchError.value = null
    lastRebuildTaskId.value = null
    try {
      const res = await updateMemory(selectedId.value, patchBody)
      // 用新记录替换列表中对应项
      replaceRecord(res.memory)
      detail.value = res.memory
      lastRebuildTaskId.value = res.rebuild_task_id ?? null
      // 记一条本地 history 占位，WS 回来后会被后端覆盖
      if (res.memory) {
        history.value = [
          {
            id: Date.now(),
            memory_id: res.memory.id,
            agent_id: res.memory.agent_id,
            event: patchBody.archived === true ? 'archive' : patchBody.archived === false ? 'unarchive' : 'update',
            old_content: null,
            new_content: res.memory.content,
            old_metadata: null,
            new_metadata: res.memory.metadata,
            source_task_id: res.rebuild_task_id ?? null,
            created_at: res.memory.updated_at
          },
          ...history.value
        ]
      }
    } catch (err) {
      patchError.value = err instanceof ShoreApiError ? err.message : (err as Error).message
      throw err
    } finally {
      patchLoading.value = false
    }
  }

  function replaceRecord(rec: MemoryRecord) {
    const idx = items.value.findIndex((m) => m.id === rec.id)
    if (idx >= 0) {
      items.value[idx] = rec
    }
  }

  async function archive() {
    await patch({ archived: true })
  }

  async function unarchive() {
    await patch({ archived: false })
  }

  /* ---------------- export ---------------- */

  async function exportAll(includeArchived = true) {
    const res = await exportMemories({
      agent_id: app.agentId,
      include_archived: includeArchived
    })
    const blob = new Blob([JSON.stringify(res, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `shore-memory-${res.agent_id}-${new Date()
      .toISOString()
      .replace(/[:.]/g, '-')}.json`
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
    return res
  }

  /* ---------------- live events ---------------- */

  let eventsBound = false
  function bindEvents() {
    if (eventsBound) return
    eventsBound = true
    getEventsClient().onType('memory.updated', (evt) => {
      const p = evt.payload as { memory_id?: number; agent_id?: string }
      if (!p || p.agent_id !== app.agentId) return
      // 如果当前选中的是这一条，刷新详情（后端经历异步 rebuild，更新后的状态要拉一次）
      if (selectedId.value === p.memory_id) {
        void select(p.memory_id)
      }
    })
  }

  // Agent 切换时清空 + 重拉
  watch(
    () => app.agentId,
    () => {
      selectedId.value = null
      detail.value = null
      entities.value = []
      history.value = []
      void reload()
    }
  )

  /* ---------------- reset filter ---------------- */

  function resetFilter() {
    filter.value = {
      state: '',
      scope: '',
      memory_type: '',
      content_query: '',
      user_uid: '',
      channel_uid: '',
      session_uid: '',
      include_archived: false
    }
  }

  return {
    // list
    items,
    total,
    offset,
    listLoading,
    listError,
    filter,
    hasMore,
    count,
    reload,
    loadMore,
    resetFilter,
    // selection
    selectedId,
    detail,
    entities,
    history,
    detailLoading,
    detailError,
    select,
    // patch
    patchLoading,
    patchError,
    lastRebuildTaskId,
    patch,
    archive,
    unarchive,
    // misc
    exportAll,
    bindEvents
  }
})
