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

export type RecallMode = 'single' | 'compare'

/**
 * Fields that can differ between the two A/B variants. Shared fields
 * (query, uids, limit) live on the main `form` so toggling between
 * single and compare modes stays friction-free.
 */
export interface RecallVariantConfig {
  label: string
  recipe: RecallRecipeId
  scope_hint: MemoryScopeHint
  include_invalid: boolean
  include_state: boolean
  debug: boolean
}

export interface RecallVariantState {
  config: RecallVariantConfig
  response: RecallResponse | null
  loading: boolean
  error: string | null
  latencyMs: number | null
  at: number | null
}

export interface CompareDiffSummary {
  aIds: number[]
  bIds: number[]
  intersection: number[]
  aOnly: number[]
  bOnly: number[]
  union: number[]
  jaccard: number
  avgRankDrift: number
  maxRankDrift: number
  /** 每个共同命中在 A/B 的排名，供 UI 画漂移可视化 */
  rankPairs: Array<{ id: number; rankA: number; rankB: number; drift: number }>
}

function defaultVariant(
  label: string,
  recipe: RecallRecipeId,
  scope_hint: MemoryScopeHint = 'auto'
): RecallVariantState {
  return {
    config: {
      label,
      recipe,
      scope_hint,
      include_invalid: false,
      include_state: false,
      debug: true
    },
    response: null,
    loading: false,
    error: null,
    latencyMs: null,
    at: null
  }
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

  /* ---------------- A/B compare ---------------- */

  const mode = ref<RecallMode>('single')
  const variantA = reactive<RecallVariantState>(defaultVariant('A', 'hybrid'))
  const variantB = reactive<RecallVariantState>(defaultVariant('B', 'entity_heavy'))
  const compareSeededFromSingle = ref(false)

  function seedVariantAFromSingleForm(): void {
    variantA.config.recipe = form.recipe
    variantA.config.scope_hint = form.scope_hint
    variantA.config.include_invalid = form.include_invalid
    variantA.config.include_state = form.include_state
    variantA.config.debug = form.debug
  }

  function setMode(next: RecallMode): void {
    if (mode.value === next) return
    mode.value = next
    // Seed variant A from the single-mode form the first time we enter compare,
    // so the user's last setup carries over. Variant B keeps its distinct
    // recipe by default (so the diff is immediately informative).
    if (next === 'compare' && !compareSeededFromSingle.value) {
      seedVariantAFromSingleForm()
      compareSeededFromSingle.value = true
    }
  }

  function swapVariants(): void {
    const snap: RecallVariantState = {
      config: { ...variantA.config },
      response: variantA.response,
      loading: variantA.loading,
      error: variantA.error,
      latencyMs: variantA.latencyMs,
      at: variantA.at
    }
    variantA.config = { ...variantB.config, label: 'A' }
    variantA.response = variantB.response
    variantA.loading = variantB.loading
    variantA.error = variantB.error
    variantA.latencyMs = variantB.latencyMs
    variantA.at = variantB.at
    variantB.config = { ...snap.config, label: 'B' }
    variantB.response = snap.response
    variantB.loading = snap.loading
    variantB.error = snap.error
    variantB.latencyMs = snap.latencyMs
    variantB.at = snap.at
  }

  function buildVariantRequest(variant: RecallVariantState): RecallRequest {
    const app = useAppStore()
    const trimmed = <T extends string | undefined>(v: T): T => {
      if (v === undefined || v === null) return v
      const s = String(v).trim()
      return (s.length === 0 ? undefined : s) as T
    }
    return {
      agent_id: app.agentId,
      query: form.query,
      recipe: variant.config.recipe,
      user_uid: trimmed(form.user_uid) ?? undefined,
      channel_uid: trimmed(form.channel_uid) ?? undefined,
      session_uid: trimmed(form.session_uid) ?? undefined,
      scope_hint: variant.config.scope_hint,
      limit: form.limit,
      include_invalid: variant.config.include_invalid,
      include_state: variant.config.include_state,
      debug: variant.config.debug
    }
  }

  async function runVariant(variant: RecallVariantState): Promise<RecallResponse | null> {
    if (!form.query.trim()) {
      variant.error = '请输入查询文本'
      return null
    }
    if (variant.loading) return variant.response
    variant.loading = true
    variant.error = null
    const started = performance.now()
    try {
      const res = await recallApi(buildVariantRequest(variant))
      variant.response = res
      variant.latencyMs = Math.round(performance.now() - started)
      variant.at = Date.now()
      return res
    } catch (err) {
      variant.error =
        err instanceof ShoreApiError ? err.message : (err as Error).message || '未知错误'
      return null
    } finally {
      variant.loading = false
    }
  }

  async function runCompare(): Promise<void> {
    if (!form.query.trim()) {
      error.value = '请输入查询文本'
      return
    }
    if (variantA.loading || variantB.loading) return
    error.value = null
    await Promise.allSettled([runVariant(variantA), runVariant(variantB)])
  }

  const compareLoading = computed(() => variantA.loading || variantB.loading)

  /** 两次召回结果集合论比较：重合 / Jaccard / 排名漂移 */
  const compareDiff = computed<CompareDiffSummary>(() => {
    const aPairs = (variantA.response?.memory_context ?? []).map(
      (m, i) => [m.id, i] as const
    )
    const bPairs = (variantB.response?.memory_context ?? []).map(
      (m, i) => [m.id, i] as const
    )
    const ranksA = new Map(aPairs.map(([id, rank]) => [id, rank]))
    const ranksB = new Map(bPairs.map(([id, rank]) => [id, rank]))
    const aIds = aPairs.map(([id]) => id)
    const bIds = bPairs.map(([id]) => id)
    const bSet = new Set(bIds)
    const aSet = new Set(aIds)
    const intersection = aIds.filter((id) => bSet.has(id))
    const aOnly = aIds.filter((id) => !bSet.has(id))
    const bOnly = bIds.filter((id) => !aSet.has(id))
    const union = Array.from(new Set([...aIds, ...bIds]))
    const jaccard = union.length ? intersection.length / union.length : 0
    const rankPairs = intersection.map((id) => {
      const ra = ranksA.get(id) ?? 0
      const rb = ranksB.get(id) ?? 0
      return { id, rankA: ra, rankB: rb, drift: Math.abs(ra - rb) }
    })
    const drifts = rankPairs.map((p) => p.drift)
    const avgRankDrift = drifts.length
      ? drifts.reduce((acc, v) => acc + v, 0) / drifts.length
      : 0
    const maxRankDrift = drifts.length ? Math.max(...drifts) : 0
    return {
      aIds,
      bIds,
      intersection,
      aOnly,
      bOnly,
      union,
      jaccard,
      avgRankDrift,
      maxRankDrift,
      rankPairs
    }
  })

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
    // single-mode state
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
    // single-mode actions
    submit,
    reset,
    buildRequest,
    loadFromHistory,
    loadFromTemplate,
    saveTemplate,
    deleteTemplate,
    clearHistory,
    // compare mode
    mode,
    variantA,
    variantB,
    compareLoading,
    compareDiff,
    setMode,
    swapVariants,
    runVariant,
    runCompare
  }
})
