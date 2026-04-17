import { defineStore } from 'pinia'
import { computed, reactive, ref } from 'vue'
import { ShoreApiError } from '@/api/http'
import { recall as recallApi } from '@/api/recall'
import type {
  MemoryScopeHint,
  MemorySnippet,
  RecallRecipeId,
  RecallRequest,
  RecallResponse
} from '@/api/types'
import { useAppStore } from './app'

const HISTORY_KEY = 'shore:recall:history'
const TEMPLATES_KEY = 'shore:recall:templates'
const MAX_HISTORY = 20

export interface RecallForm {
  query: string
  recipe: RecallRecipeId
  user_uid: string
  channel_uid: string
  session_uid: string
  scope_hint: MemoryScopeHint
  limit: number
  include_invalid: boolean
  include_state: boolean
  debug: boolean
}

export interface RecallHistoryEntry {
  id: string
  at: number
  agentId: string
  form: RecallForm
  /** snippet \u6570\uff0c\u5feb\u901f\u9884\u89c8 */
  hits: number
  latencyMs: number
  degraded: boolean
}

export interface RecallTemplate {
  id: string
  name: string
  form: RecallForm
  updatedAt: number
}

function defaultForm(): RecallForm {
  return {
    query: '',
    recipe: 'hybrid',
    user_uid: '',
    channel_uid: '',
    session_uid: '',
    scope_hint: 'auto',
    limit: 8,
    include_invalid: false,
    include_state: false,
    debug: true
  }
}

function readJson<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key)
    if (!raw) return fallback
    return JSON.parse(raw) as T
  } catch {
    return fallback
  }
}

function writeJson(key: string, value: unknown): void {
  try {
    localStorage.setItem(key, JSON.stringify(value))
  } catch {
    /* ignore quota */
  }
}

export const useRecallStore = defineStore('recall', () => {
  const form = reactive<RecallForm>(defaultForm())
  const loading = ref(false)
  const error = ref<string | null>(null)
  const response = ref<RecallResponse | null>(null)
  const lastLatencyMs = ref<number | null>(null)
  const lastAt = ref<number | null>(null)
  const history = ref<RecallHistoryEntry[]>(readJson<RecallHistoryEntry[]>(HISTORY_KEY, []))
  const templates = ref<RecallTemplate[]>(readJson<RecallTemplate[]>(TEMPLATES_KEY, []))

  const memories = computed<MemorySnippet[]>(() => response.value?.memory_context ?? [])
  const hits = computed(() => memories.value.length)
  const degraded = computed(() => response.value?.degraded ?? false)

  function reset(): void {
    Object.assign(form, defaultForm())
    response.value = null
    error.value = null
    lastLatencyMs.value = null
    lastAt.value = null
  }

  function loadFromHistory(entry: RecallHistoryEntry): void {
    Object.assign(form, entry.form)
  }

  function loadFromTemplate(tpl: RecallTemplate): void {
    Object.assign(form, tpl.form)
  }

  function saveTemplate(name: string): RecallTemplate {
    const tpl: RecallTemplate = {
      id: Date.now().toString(36),
      name: name.trim() || 'Untitled',
      form: { ...form },
      updatedAt: Date.now()
    }
    templates.value = [tpl, ...templates.value.filter((t) => t.name !== tpl.name)].slice(0, 20)
    writeJson(TEMPLATES_KEY, templates.value)
    return tpl
  }

  function deleteTemplate(id: string): void {
    templates.value = templates.value.filter((t) => t.id !== id)
    writeJson(TEMPLATES_KEY, templates.value)
  }

  function clearHistory(): void {
    history.value = []
    writeJson(HISTORY_KEY, history.value)
  }

  function buildRequest(): RecallRequest {
    const app = useAppStore()
    const trimmed = <T extends string | undefined>(v: T): T => {
      if (v === undefined || v === null) return v
      const s = String(v).trim()
      return (s.length === 0 ? undefined : s) as T
    }
    return {
      agent_id: app.agentId,
      query: form.query,
      recipe: form.recipe,
      user_uid: trimmed(form.user_uid) ?? undefined,
      channel_uid: trimmed(form.channel_uid) ?? undefined,
      session_uid: trimmed(form.session_uid) ?? undefined,
      scope_hint: form.scope_hint,
      limit: form.limit,
      include_invalid: form.include_invalid,
      include_state: form.include_state,
      debug: form.debug
    }
  }

  async function submit(): Promise<RecallResponse | null> {
    if (!form.query.trim()) {
      error.value = '\u8bf7\u8f93\u5165\u67e5\u8be2\u6587\u672c'
      return null
    }
    if (loading.value) return null
    const app = useAppStore()
    loading.value = true
    error.value = null
    const started = performance.now()
    const request = buildRequest()
    try {
      const res = await recallApi(request)
      const elapsed = Math.round(performance.now() - started)
      response.value = res
      lastLatencyMs.value = elapsed
      lastAt.value = Date.now()

      const entry: RecallHistoryEntry = {
        id: `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 6)}`,
        at: Date.now(),
        agentId: app.agentId,
        form: { ...form },
        hits: res.memory_context.length,
        latencyMs: elapsed,
        degraded: res.degraded
      }
      history.value = [entry, ...history.value].slice(0, MAX_HISTORY)
      writeJson(HISTORY_KEY, history.value)
      return res
    } catch (err) {
      const message =
        err instanceof ShoreApiError ? err.message : (err as Error).message || '\u672a\u77e5\u9519\u8bef'
      error.value = message
      return null
    } finally {
      loading.value = false
    }
  }

  return {
    form,
    loading,
    error,
    response,
    lastLatencyMs,
    lastAt,
    history,
    templates,
    memories,
    hits,
    degraded,
    submit,
    reset,
    buildRequest,
    loadFromHistory,
    loadFromTemplate,
    saveTemplate,
    deleteTemplate,
    clearHistory
  }
})
