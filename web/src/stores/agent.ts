import { defineStore } from 'pinia'
import { computed, reactive, ref, watch } from 'vue'
import { useAppStore } from './app'
import { getAgentState, patchAgentState } from '@/api/agent'
import { getEventsClient } from '@/api/events'
import { ShoreApiError } from '@/api/http'
import type { AgentStatePatch, AgentStateResponse } from '@/api/types'

/**
 * Agent 状态 store：
 *
 * - `remote`：服务端最后一次返回（或 WS 广播回来）的 AgentStateResponse
 *   的不可变镜像。变更 mirror / 三元组仪表盘都读这里。
 * - `draft`：编辑器里用户正在打字的草稿；脏字段才会被 PATCH 发出去。
 * - `timeline`：最近 20 条 `agent.state.updated` 事件的本地环缓冲，
 *   不做持久化，纯调试 / 观感。
 *
 * 切换 `app.agentId` 时会自动丢弃 draft / timeline 并重新拉取。
 */

export interface AgentStateTimelineEntry {
  at: string
  source: 'remote' | 'event' | 'local'
  mood: string
  vibe: string
  mind: string
  /** 相对上一条的变化字段。第一条固定为全量。 */
  changed: Array<'mood' | 'vibe' | 'mind'>
}

export interface AgentStateDraft {
  mood: string
  vibe: string
  mind: string
}

const MAX_TIMELINE = 20

function emptyDraft(): AgentStateDraft {
  return { mood: '', vibe: '', mind: '' }
}

function draftFromRemote(remote: AgentStateResponse): AgentStateDraft {
  return { mood: remote.mood, vibe: remote.vibe, mind: remote.mind }
}

function computeChanged(
  prev: Pick<AgentStateResponse, 'mood' | 'vibe' | 'mind'> | null,
  next: Pick<AgentStateResponse, 'mood' | 'vibe' | 'mind'>
): Array<'mood' | 'vibe' | 'mind'> {
  if (!prev) return ['mood', 'vibe', 'mind']
  const out: Array<'mood' | 'vibe' | 'mind'> = []
  if (prev.mood !== next.mood) out.push('mood')
  if (prev.vibe !== next.vibe) out.push('vibe')
  if (prev.mind !== next.mind) out.push('mind')
  return out
}

export const useAgentStore = defineStore('agent', () => {
  const app = useAppStore()

  const remote = ref<AgentStateResponse | null>(null)
  const draft = reactive<AgentStateDraft>(emptyDraft())
  const timeline = ref<AgentStateTimelineEntry[]>([])

  const loading = ref(false)
  const saving = ref(false)
  const error = ref<string | null>(null)
  const saveError = ref<string | null>(null)
  const lastSavedAt = ref<number | null>(null)
  /** 本地最近一次被刷新的字段，用于 mirror 做 1s 高亮。 */
  const flashFields = ref<Array<'mood' | 'vibe' | 'mind'>>([])
  let flashTimer: number | null = null

  const dirty = computed(() => {
    if (!remote.value) {
      return Boolean(draft.mood.trim() || draft.vibe.trim() || draft.mind.trim())
    }
    return (
      draft.mood !== remote.value.mood ||
      draft.vibe !== remote.value.vibe ||
      draft.mind !== remote.value.mind
    )
  })

  const dirtyFields = computed<Array<'mood' | 'vibe' | 'mind'>>(() => {
    if (!remote.value) return []
    const out: Array<'mood' | 'vibe' | 'mind'> = []
    if (draft.mood !== remote.value.mood) out.push('mood')
    if (draft.vibe !== remote.value.vibe) out.push('vibe')
    if (draft.mind !== remote.value.mind) out.push('mind')
    return out
  })

  function resetDraft() {
    if (remote.value) {
      Object.assign(draft, draftFromRemote(remote.value))
    } else {
      Object.assign(draft, emptyDraft())
    }
    saveError.value = null
  }

  function triggerFlash(fields: Array<'mood' | 'vibe' | 'mind'>) {
    if (!fields.length) return
    flashFields.value = fields
    if (flashTimer !== null) window.clearTimeout(flashTimer)
    flashTimer = window.setTimeout(() => {
      flashFields.value = []
      flashTimer = null
    }, 1200)
  }

  function pushTimeline(
    next: AgentStateResponse,
    source: AgentStateTimelineEntry['source']
  ) {
    const prev = timeline.value[0] ?? null
    const previousState = prev
      ? { mood: prev.mood, vibe: prev.vibe, mind: prev.mind }
      : remote.value
    const changed = computeChanged(previousState, next)
    // 如果没有任何变化（例如重复的 remote 快照），就不 push
    if (prev && changed.length === 0) return
    timeline.value.unshift({
      at: next.updated_at ?? new Date().toISOString(),
      source,
      mood: next.mood,
      vibe: next.vibe,
      mind: next.mind,
      changed: changed.length ? changed : ['mood', 'vibe', 'mind']
    })
    if (timeline.value.length > MAX_TIMELINE) {
      timeline.value.length = MAX_TIMELINE
    }
    triggerFlash(changed.length ? changed : ['mood', 'vibe', 'mind'])
  }

  function applyRemote(
    next: AgentStateResponse,
    source: AgentStateTimelineEntry['source']
  ) {
    // 只在字段确实变化时推 timeline，避免 GET 轮询产生噪音
    const changed = computeChanged(
      remote.value
        ? { mood: remote.value.mood, vibe: remote.value.vibe, mind: remote.value.mind }
        : null,
      next
    )
    remote.value = next
    if (!dirty.value) {
      // 没有脏草稿时把服务端值镜像到编辑器里
      Object.assign(draft, draftFromRemote(next))
    }
    if (changed.length) {
      pushTimeline(next, source)
    }
  }

  async function load(): Promise<AgentStateResponse | null> {
    loading.value = true
    error.value = null
    try {
      const res = await getAgentState(app.agentId)
      applyRemote(res, 'remote')
      return res
    } catch (err) {
      error.value = err instanceof ShoreApiError ? err.message : (err as Error).message
      return null
    } finally {
      loading.value = false
    }
  }

  async function save(): Promise<AgentStateResponse | null> {
    if (!dirty.value) return remote.value
    saving.value = true
    saveError.value = null
    try {
      const payload: AgentStatePatch = {}
      for (const key of dirtyFields.value) {
        payload[key] = draft[key]
      }
      const res = await patchAgentState(app.agentId, payload)
      applyRemote(res, 'local')
      lastSavedAt.value = Date.now()
      // 保存后 draft 自然不脏，applyRemote 已同步
      return res
    } catch (err) {
      saveError.value =
        err instanceof ShoreApiError ? err.message : (err as Error).message
      throw err
    } finally {
      saving.value = false
    }
  }

  let eventsBound = false
  function bindEvents() {
    if (eventsBound) return
    eventsBound = true
    getEventsClient().onType('agent.state.updated', (evt) => {
      const payload = evt.payload as {
        agent_id?: string
        mood?: string
        vibe?: string
        mind?: string
      }
      if (!payload || payload.agent_id !== app.agentId) return
      const next: AgentStateResponse = {
        agent_id: payload.agent_id,
        mood: payload.mood ?? remote.value?.mood ?? '',
        vibe: payload.vibe ?? remote.value?.vibe ?? '',
        mind: payload.mind ?? remote.value?.mind ?? '',
        updated_at: evt.at ?? new Date().toISOString()
      }
      applyRemote(next, 'event')
    })
  }

  // Agent 切换：清状态 + 重拉
  watch(
    () => app.agentId,
    () => {
      remote.value = null
      timeline.value = []
      Object.assign(draft, emptyDraft())
      error.value = null
      saveError.value = null
      void load()
    }
  )

  return {
    remote,
    draft,
    timeline,
    loading,
    saving,
    error,
    saveError,
    lastSavedAt,
    flashFields,
    dirty,
    dirtyFields,
    load,
    save,
    resetDraft,
    bindEvents
  }
})
