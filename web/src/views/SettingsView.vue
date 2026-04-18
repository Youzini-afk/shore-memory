<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import PHero from '@/components/ui/PHero.vue'
import PCard from '@/components/ui/PCard.vue'
import PButton from '@/components/ui/PButton.vue'
import PInput from '@/components/ui/PInput.vue'
import { useAppStore } from '@/stores/app'
import { api, ShoreApiError } from '@/api/http'
import type {
  DefaultPromptsResponse,
  DetectEmbeddingDimensionResponse,
  ListProviderModelsResponse,
  ModelConfigResponse,
  ModelConfigTestResponse,
  ModelPresetResponse,
  PresetKind,
  ProviderKind,
  RoleBindingResponse,
  UpdateModelConfigRequest,
  UpdateModelConfigResponse,
  UpdatePresetRequest,
  UpdateRoleBindingRequest
} from '@/api/types'

type RoleKey = 'scorer' | 'reflector' | 'query_analyzer' | 'query_planner'

type ApiKeyAction = 'keep' | 'clear' | 'set'

type PresetFormState = {
  id: string
  name: string
  kind: PresetKind
  apiBase: string
  model: string
  dimension: string
  temperature: string
  apiKey: string
  apiKeyAction: ApiKeyAction
  apiKeyMasked: string | null
  apiKeyConfigured: boolean
  isNew: boolean
}

type RoleFormState = {
  presetId: string
  temperature: string
}

const ROLE_META: Record<RoleKey, { label: string; description: string; defaultTemperature: number }> = {
  scorer: {
    label: '评分器',
    description: '对话轮次记忆抽取',
    defaultTemperature: 0.3
  },
  reflector: {
    label: '反思器',
    description: '重复 / 矛盾 / 总结整理',
    defaultTemperature: 0.4
  },
  query_analyzer: {
    label: '查询分析器',
    description: '召回时 query 命名实体分析',
    defaultTemperature: 0.1
  },
  query_planner: {
    label: '查询规划器',
    description: '多意图拆分 / 子查询规划',
    defaultTemperature: 0.1
  }
}

const roleKeys = Object.keys(ROLE_META) as RoleKey[]
const roleEntries = roleKeys.map((key) => ({ key, ...ROLE_META[key] }))

const app = useAppStore()

const loadingModelConfig = ref(false)
const savingModelConfig = ref(false)
const restoringModelConfig = ref(false)
const testingModelConfig = ref(false)
const detectingDimensionId = ref<string | null>(null)
const fetchingModelsForId = ref<string | null>(null)

const modelConfig = ref<ModelConfigResponse | null>(null)
const modelConfigTest = ref<ModelConfigTestResponse | null>(null)
const modelConfigError = ref<string | null>(null)
const modelConfigNotice = ref<string | null>(null)

const embeddingPresets = ref<PresetFormState[]>([])
const llmPresets = ref<PresetFormState[]>([])
const defaultEmbeddingId = ref<string>('')
const defaultLlmId = ref<string>('')
const activeEmbeddingId = ref<string>('')
const activeLlmId = ref<string>('')
const modelOptionsByPreset = reactive<Record<string, string[]>>({})

const activeEmbeddingPreset = computed(
  () => embeddingPresets.value.find((p) => p.id === activeEmbeddingId.value) ?? null
)
const activeLlmPreset = computed(
  () => llmPresets.value.find((p) => p.id === activeLlmId.value) ?? null
)

const roleForms = reactive<Record<RoleKey, RoleFormState>>({
  scorer: { presetId: '', temperature: '' },
  reflector: { presetId: '', temperature: '' },
  query_analyzer: { presetId: '', temperature: '' },
  query_planner: { presetId: '', temperature: '' }
})

/**
 * Per-role system prompt override form. Empty string means "use the worker's
 * built-in default"; any non-empty string is sent as an override on save.
 */
const promptForms = reactive<Record<RoleKey, string>>({
  scorer: '',
  reflector: '',
  query_analyzer: '',
  query_planner: ''
})

/**
 * Cached worker defaults, fetched lazily via `/v1/model-config/default-prompts`.
 * Used to power the "view / restore default" actions without forcing the user
 * to remember the exact prompt text.
 */
const defaultPrompts = ref<Record<RoleKey, string> | null>(null)
const loadingDefaultPrompts = ref(false)
const defaultPromptsError = ref<string | null>(null)
const promptPreviewOpen = reactive<Record<RoleKey, boolean>>({
  scorer: false,
  reflector: false,
  query_analyzer: false,
  query_planner: false
})

const modelConfigBusy = computed(
  () =>
    loadingModelConfig.value ||
    savingModelConfig.value ||
    restoringModelConfig.value ||
    testingModelConfig.value ||
    detectingDimensionId.value !== null ||
    fetchingModelsForId.value !== null
)

const eventsStatusLabel = computed(() => {
  switch (app.eventsStatus) {
    case 'open':
      return '实时'
    case 'connecting':
      return '连接中'
    case 'error':
      return '错误'
    case 'lagged':
      return '积压'
    case 'disconnected':
    default:
      return '未连接'
  }
})

const healthStatusLabel = computed(() => {
  const status = app.health?.status
  if (!status) return '–'
  if (status === 'ok') return '正常'
  if (status === 'degraded') return '已降级'
  if (status === 'error') return '异常'
  return status
})

const authStatusLabel = computed(() => {
  switch (app.authStatus) {
    case 'checking':
      return '验证中'
    case 'ready':
      return '已解锁'
    case 'locked':
    default:
      return '已锁定'
  }
})

function formatProviderSource(source: string | null | undefined): string {
  switch (source) {
    case 'file':
      return '覆盖文件'
    case 'mixed':
      return '环境 + 覆盖'
    case 'request':
      return '本次请求'
    case 'inherit':
      return '继承默认'
    case 'env':
    default:
      return '环境变量'
  }
}

function formatKeySource(source: string | null | undefined): string {
  switch (source) {
    case 'file':
      return '覆盖文件'
    case 'cleared':
      return '已清空'
    case 'unset':
      return '未配置'
    case 'request':
      return '本次请求'
    case 'inherit':
      return '继承默认'
    case 'env':
    default:
      return '环境变量'
  }
}

function formatTemperature(value: number | null | undefined): string {
  if (value === null || value === undefined) return '–'
  return Number(value).toFixed(2)
}

function resolveError(err: unknown): string {
  if (err instanceof ShoreApiError) return err.message
  if (err instanceof Error) return err.message
  return '请求失败，请稍后重试。'
}

function newPresetId(prefix: string): string {
  const rand = Math.random().toString(36).slice(2, 8)
  return `${prefix}-${Date.now().toString(36)}-${rand}`
}

function emptyEmbeddingPreset(): PresetFormState {
  return {
    id: newPresetId('embedding'),
    name: '新预设',
    kind: 'embedding',
    apiBase: '',
    model: '',
    dimension: '',
    temperature: '',
    apiKey: '',
    apiKeyAction: 'keep',
    apiKeyMasked: null,
    apiKeyConfigured: false,
    isNew: true
  }
}

function emptyLlmPreset(): PresetFormState {
  return {
    id: newPresetId('llm'),
    name: '新预设',
    kind: 'llm',
    apiBase: '',
    model: '',
    dimension: '',
    temperature: '',
    apiKey: '',
    apiKeyAction: 'keep',
    apiKeyMasked: null,
    apiKeyConfigured: false,
    isNew: true
  }
}

function hydratePresetList(presets: ModelPresetResponse[]): PresetFormState[] {
  return presets.map((preset) => ({
    id: preset.id,
    name: preset.name,
    kind: preset.kind,
    apiBase: preset.api_base ?? '',
    model: preset.model ?? '',
    dimension:
      preset.dimension !== null && preset.dimension !== undefined
        ? String(preset.dimension)
        : '',
    temperature:
      preset.temperature !== null && preset.temperature !== undefined
        ? String(preset.temperature)
        : '',
    apiKey: '',
    apiKeyAction: 'keep' as ApiKeyAction,
    apiKeyMasked: preset.api_key_masked ?? null,
    apiKeyConfigured: preset.api_key_configured,
    isNew: false
  }))
}

function hydrateRoles(config: ModelConfigResponse) {
  for (const role of roleKeys) {
    const binding = config.role_bindings[role]
    roleForms[role] = {
      presetId: binding?.preset_id ?? '',
      temperature:
        binding?.temperature !== null && binding?.temperature !== undefined
          ? String(binding.temperature)
          : ''
    }
  }
}

function hydratePrompts(config: ModelConfigResponse) {
  const overrides = config.prompts ?? {}
  for (const role of roleKeys) {
    const raw = overrides[role]
    promptForms[role] = typeof raw === 'string' ? raw : ''
  }
}

function hydrateForm(config: ModelConfigResponse) {
  const previousEmbeddingActive = activeEmbeddingId.value
  const previousLlmActive = activeLlmId.value
  embeddingPresets.value = hydratePresetList(config.embedding_presets)
  llmPresets.value = hydratePresetList(config.llm_presets)
  defaultEmbeddingId.value = config.default_embedding_preset ?? (config.embedding_presets[0]?.id ?? '')
  defaultLlmId.value = config.default_llm_preset ?? (config.llm_presets[0]?.id ?? '')
  activeEmbeddingId.value =
    (previousEmbeddingActive && embeddingPresets.value.some((p) => p.id === previousEmbeddingActive)
      ? previousEmbeddingActive
      : defaultEmbeddingId.value) || (embeddingPresets.value[0]?.id ?? '')
  activeLlmId.value =
    (previousLlmActive && llmPresets.value.some((p) => p.id === previousLlmActive)
      ? previousLlmActive
      : defaultLlmId.value) || (llmPresets.value[0]?.id ?? '')
  hydrateRoles(config)
  hydratePrompts(config)
  for (const key of Object.keys(modelOptionsByPreset)) {
    delete modelOptionsByPreset[key]
  }
}

async function loadModelConfig() {
  loadingModelConfig.value = true
  modelConfigError.value = null
  try {
    const res = await api.get<ModelConfigResponse>('/v1/model-config')
    modelConfig.value = res
    hydrateForm(res)
  } catch (err) {
    modelConfigError.value = `读取模型配置失败：${resolveError(err)}`
  } finally {
    loadingModelConfig.value = false
  }
}

function parseOptionalNumber(raw: string): number | undefined {
  const value = raw.trim()
  if (!value) return undefined
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : undefined
}

function presetFormToRequest(preset: PresetFormState): UpdatePresetRequest {
  const payload: UpdatePresetRequest = {
    id: preset.id,
    name: preset.name.trim() || '未命名',
    api_base: preset.apiBase.trim() || undefined,
    model: preset.model.trim() || undefined
  }
  if (preset.kind === 'embedding') {
    const dim = Number.parseInt(preset.dimension.trim(), 10)
    if (Number.isFinite(dim) && dim > 0) {
      payload.dimension = dim
    }
  } else {
    const temp = parseOptionalNumber(preset.temperature)
    if (temp !== undefined) {
      payload.temperature = temp
    }
  }
  switch (preset.apiKeyAction) {
    case 'clear':
      payload.clear_api_key = true
      break
    case 'set':
      payload.api_key = preset.apiKey.trim() || undefined
      if (!payload.api_key) {
        // user chose "set" but didn't type; fall back to keep
        payload.api_key_unchanged = true
      }
      break
    case 'keep':
    default:
      payload.api_key_unchanged = true
      break
  }
  return payload
}

function buildUpdatePayload(options?: { autoDetectEmbeddingDimension?: boolean }): UpdateModelConfigRequest {
  const roleBindings: Record<string, UpdateRoleBindingRequest> = {}
  for (const role of roleKeys) {
    const form = roleForms[role]
    const presetId = form.presetId.trim()
    const temperature = parseOptionalNumber(form.temperature)
    roleBindings[role] = {
      preset_id: presetId ? presetId : null,
      temperature: temperature === undefined ? null : temperature
    }
  }
  const prompts: Record<string, string | null> = {}
  for (const role of roleKeys) {
    const trimmed = promptForms[role].trim()
    // Empty form value → explicit `null` so server drops any existing override
    // and the worker falls back to its built-in default for that role.
    prompts[role] = trimmed ? promptForms[role] : null
  }

  return {
    embedding_presets: embeddingPresets.value.map(presetFormToRequest),
    llm_presets: llmPresets.value.map(presetFormToRequest),
    default_embedding_preset: defaultEmbeddingId.value || undefined,
    default_llm_preset: defaultLlmId.value || undefined,
    role_bindings: roleBindings,
    prompts,
    auto_detect_embedding_dimension: options?.autoDetectEmbeddingDimension ?? false
  }
}

async function saveModelConfig() {
  savingModelConfig.value = true
  modelConfigError.value = null
  modelConfigNotice.value = null
  try {
    const payload = buildUpdatePayload({ autoDetectEmbeddingDimension: false })
    const res = await api.put<UpdateModelConfigResponse>('/v1/model-config', payload)
    modelConfig.value = res.config
    hydrateForm(res.config)
    if (!res.embedding_changed) {
      modelConfigNotice.value = '已保存，配置立即生效。'
    } else {
      const reason = res.embedding_dimension_changed ? 'embedding 维度变更' : 'embedding 配置变更'
      modelConfigNotice.value = `已保存配置，检测到 ${reason}，已自动刷新 ${res.memory_embeddings_refreshed} 条记忆 embedding，并重建索引（memories=${res.reindexed_memories}, entities=${res.reindexed_entities}）。`
    }
  } catch (err) {
    modelConfigError.value = `保存模型配置失败：${resolveError(err)}`
  } finally {
    savingModelConfig.value = false
  }
}

async function restoreModelConfig() {
  if (!window.confirm('确认恢复为环境变量默认配置？覆盖文件（含所有预设）将被删除。')) return
  restoringModelConfig.value = true
  modelConfigError.value = null
  modelConfigNotice.value = null
  try {
    const res = await api.delete<UpdateModelConfigResponse>('/v1/model-config')
    modelConfig.value = res.config
    hydrateForm(res.config)
    modelConfigNotice.value = '已恢复为环境变量配置。'
  } catch (err) {
    modelConfigError.value = `恢复默认配置失败：${resolveError(err)}`
  } finally {
    restoringModelConfig.value = false
  }
}

async function testModelConfig() {
  testingModelConfig.value = true
  modelConfigError.value = null
  modelConfigNotice.value = null
  try {
    const res = await api.post<ModelConfigTestResponse>('/v1/model-config/test')
    modelConfigTest.value = res
    const roleFailures = roleKeys.some(
      (role) => Boolean(res.roles?.[role]) && !res.roles[role].ok
    )
    if (res.embedding.ok && res.llm.ok && !roleFailures) {
      modelConfigNotice.value = '模型连通性测试通过。'
    } else {
      modelConfigNotice.value = '模型连通性测试完成，存在失败项，请查看下方结果。'
    }
  } catch (err) {
    modelConfigError.value = `测试模型配置失败：${resolveError(err)}`
  } finally {
    testingModelConfig.value = false
  }
}

function addPreset(kind: PresetKind) {
  if (kind === 'embedding') {
    const preset = emptyEmbeddingPreset()
    embeddingPresets.value.push(preset)
    if (!defaultEmbeddingId.value) defaultEmbeddingId.value = preset.id
    activeEmbeddingId.value = preset.id
  } else {
    const preset = emptyLlmPreset()
    llmPresets.value.push(preset)
    if (!defaultLlmId.value) defaultLlmId.value = preset.id
    activeLlmId.value = preset.id
  }
}

function saveAsPreset(kind: PresetKind) {
  const current =
    kind === 'embedding' ? activeEmbeddingPreset.value : activeLlmPreset.value
  if (!current) {
    addPreset(kind)
    return
  }
  const suggested = `${current.name} 副本`
  const raw = window.prompt('请输入新预设名称：', suggested)
  if (raw === null) return
  const trimmed = raw.trim()
  if (!trimmed) {
    modelConfigError.value = '预设名不能为空。'
    return
  }
  const idPrefix = kind === 'embedding' ? 'embedding' : 'llm'
  const clone: PresetFormState = {
    ...current,
    id: newPresetId(idPrefix),
    name: trimmed,
    apiKey: '',
    apiKeyAction: 'keep',
    apiKeyMasked: current.apiKeyMasked,
    apiKeyConfigured: current.apiKeyConfigured,
    isNew: true
  }
  if (kind === 'embedding') {
    embeddingPresets.value.push(clone)
    activeEmbeddingId.value = clone.id
  } else {
    llmPresets.value.push(clone)
    activeLlmId.value = clone.id
  }
  modelConfigNotice.value = `已添加新预设「${trimmed}」，请点击「保存」写入服务端。`
}

function removeActivePreset(kind: PresetKind) {
  const label = kind === 'embedding' ? 'Embedding' : 'LLM'
  const list = kind === 'embedding' ? embeddingPresets : llmPresets
  const activeRef = kind === 'embedding' ? activeEmbeddingId : activeLlmId
  const id = activeRef.value
  if (!id) return
  if (list.value.length <= 1) {
    modelConfigError.value = `至少需要保留一个 ${label} 预设。`
    return
  }
  const preset = list.value.find((p) => p.id === id)
  if (!preset) return
  if (!window.confirm(`确认删除 ${label} 预设「${preset.name}」？保存后生效。`)) return
  list.value = list.value.filter((p) => p.id !== id)
  if (kind === 'embedding' && defaultEmbeddingId.value === id) {
    defaultEmbeddingId.value = list.value[0]?.id ?? ''
  }
  if (kind === 'llm' && defaultLlmId.value === id) {
    defaultLlmId.value = list.value[0]?.id ?? ''
  }
  if (kind === 'llm') {
    for (const role of roleKeys) {
      if (roleForms[role].presetId === id) roleForms[role].presetId = ''
    }
  }
  delete modelOptionsByPreset[id]
  activeRef.value = list.value[0]?.id ?? ''
}

function setActiveAsDefault(kind: PresetKind) {
  if (kind === 'embedding') {
    if (activeEmbeddingId.value) defaultEmbeddingId.value = activeEmbeddingId.value
  } else {
    if (activeLlmId.value) defaultLlmId.value = activeLlmId.value
  }
}

function presetById(kind: PresetKind, id: string | null | undefined): PresetFormState | undefined {
  if (!id) return undefined
  const list = kind === 'embedding' ? embeddingPresets.value : llmPresets.value
  return list.find((p) => p.id === id)
}

function effectiveLlmForRole(role: RoleKey): PresetFormState | undefined {
  const boundId = roleForms[role].presetId
  if (boundId) return presetById('llm', boundId)
  if (defaultLlmId.value) return presetById('llm', defaultLlmId.value)
  return llmPresets.value[0]
}

function effectiveRoleTemperatureLabel(role: RoleKey): string {
  const explicit = parseOptionalNumber(roleForms[role].temperature)
  if (explicit !== undefined) return explicit.toFixed(2)
  const preset = effectiveLlmForRole(role)
  if (preset) {
    const presetTemp = parseOptionalNumber(preset.temperature)
    if (presetTemp !== undefined) return presetTemp.toFixed(2)
  }
  return ROLE_META[role].defaultTemperature.toFixed(2)
}

async function fetchProviderModels(preset: PresetFormState) {
  fetchingModelsForId.value = preset.id
  modelConfigError.value = null
  modelConfigNotice.value = null
  try {
    const provider: ProviderKind = preset.kind
    const apiKey =
      preset.apiKeyAction === 'set'
        ? preset.apiKey.trim() || undefined
        : undefined
    const clearApiKey = preset.apiKeyAction === 'clear'
    const body: Record<string, unknown> = {
      provider,
      api_base: preset.apiBase.trim(),
      preset_id: preset.isNew ? undefined : preset.id,
      api_key: apiKey,
      clear_api_key: clearApiKey
    }
    const res = await api.post<ListProviderModelsResponse>('/v1/model-config/models', body)
    const unique = Array.from(new Set(res.models.filter((value) => value.trim())))
    unique.sort((a, b) => a.localeCompare(b))
    modelOptionsByPreset[preset.id] = unique
    modelConfigNotice.value = unique.length
      ? `已获取 ${unique.length} 个模型。`
      : '提供方没有返回可用模型。'
  } catch (err) {
    modelConfigError.value = `获取模型失败：${resolveError(err)}`
  } finally {
    fetchingModelsForId.value = null
  }
}

async function detectEmbeddingDimension(preset: PresetFormState) {
  if (!preset.model.trim()) {
    modelConfigError.value = '请先填写模型名再自动识别维度。'
    return
  }
  detectingDimensionId.value = preset.id
  modelConfigError.value = null
  modelConfigNotice.value = null
  try {
    const apiKey =
      preset.apiKeyAction === 'set'
        ? preset.apiKey.trim() || undefined
        : undefined
    const body = {
      api_base: preset.apiBase.trim(),
      model: preset.model.trim(),
      preset_id: preset.isNew ? undefined : preset.id,
      api_key: apiKey,
      clear_api_key: preset.apiKeyAction === 'clear'
    }
    const res = await api.post<DetectEmbeddingDimensionResponse>(
      '/v1/model-config/embedding/dimension',
      body
    )
    preset.dimension = String(res.dimension)
    modelConfigNotice.value = `已自动识别 ${res.model} 的向量维度：${res.dimension}`
  } catch (err) {
    modelConfigError.value = `识别 Embedding 维度失败：${resolveError(err)}`
  } finally {
    detectingDimensionId.value = null
  }
}

function getRoleBinding(role: RoleKey): RoleBindingResponse | undefined {
  return modelConfig.value?.role_bindings[role]
}

function promptIsOverridden(role: RoleKey): boolean {
  return Boolean(promptForms[role].trim())
}

async function ensureDefaultPrompts(): Promise<Record<RoleKey, string> | null> {
  if (defaultPrompts.value) {
    return defaultPrompts.value
  }
  if (loadingDefaultPrompts.value) {
    return null
  }
  loadingDefaultPrompts.value = true
  defaultPromptsError.value = null
  try {
    const res = await api.get<DefaultPromptsResponse>('/v1/model-config/default-prompts')
    const map = (res.prompts ?? {}) as Record<string, string>
    defaultPrompts.value = {
      scorer: map.scorer ?? '',
      reflector: map.reflector ?? '',
      query_analyzer: map.query_analyzer ?? '',
      query_planner: map.query_planner ?? ''
    }
    return defaultPrompts.value
  } catch (err) {
    defaultPromptsError.value = `读取默认提示词失败：${resolveError(err)}`
    return null
  } finally {
    loadingDefaultPrompts.value = false
  }
}

async function togglePromptPreview(role: RoleKey) {
  if (!promptPreviewOpen[role]) {
    const prompts = await ensureDefaultPrompts()
    if (!prompts) return
  }
  promptPreviewOpen[role] = !promptPreviewOpen[role]
}

async function restorePromptDefault(role: RoleKey) {
  const prompts = await ensureDefaultPrompts()
  if (!prompts) return
  promptForms[role] = prompts[role] ?? ''
  modelConfigNotice.value = `已把「${ROLE_META[role].label}」提示词填充为内置默认，记得点「保存」使其生效。`
}

function clearPromptOverride(role: RoleKey) {
  promptForms[role] = ''
  modelConfigNotice.value = `已清空「${ROLE_META[role].label}」的提示词覆盖，保存后该角色会使用内置默认。`
}

onMounted(() => {
  void loadModelConfig()
  void ensureDefaultPrompts()
})
</script>

<template>
  <div class="min-h-full">
    <PHero title="设置" subtitle="API · 事件流 · 主题 · 快捷键" />
    <div class="px-8 pb-10 grid grid-cols-1 xl:grid-cols-2 gap-5">
      <PCard edge>
        <div class="text-[12px] uppercase font-display tracking-wider text-ink-4 mb-3">
          环境
        </div>
        <div class="grid grid-cols-3 gap-y-2 text-[13px]">
          <div class="text-ink-4">API 地址</div>
          <div class="col-span-2 font-mono text-ink-1 truncate">
            {{ app.apiBase || '同源（由 axum 静态托管）' }}
          </div>
          <div class="text-ink-4">Agent</div>
          <div class="col-span-2 font-display text-ink-1">{{ app.agentId }}</div>
          <div class="text-ink-4">事件流</div>
          <div class="col-span-2 font-display text-ink-1">{{ eventsStatusLabel }}</div>
          <div class="text-ink-4">服务健康</div>
          <div
            class="col-span-2 font-display"
            :class="app.isHealthy ? 'text-state-active' : 'text-ink-3'"
          >
            {{ healthStatusLabel }}
          </div>
          <div class="text-ink-4">Worker</div>
          <div class="col-span-2 font-display text-ink-1">
            {{ app.health?.worker_available ? '可用' : '未知' }}
          </div>
          <div class="text-ink-4">待处理任务</div>
          <div class="col-span-2 font-display text-ink-1">{{ app.health?.pending_tasks ?? 0 }}</div>
          <div class="text-ink-4">失败任务</div>
          <div class="col-span-2 font-display text-ink-1">{{ app.health?.failed_tasks ?? 0 }}</div>
        </div>
      </PCard>

      <PCard edge>
        <div class="text-[12px] uppercase font-display tracking-wider text-ink-4 mb-3">
          鉴权
        </div>
        <div class="grid grid-cols-3 gap-y-2 text-[13px]">
          <div class="text-ink-4">是否启用</div>
          <div class="col-span-2 font-display text-ink-1">
            {{ app.authRequired ? '是' : '否' }}
          </div>
          <div class="text-ink-4">状态</div>
          <div class="col-span-2 font-display text-ink-1">{{ authStatusLabel }}</div>
          <div class="text-ink-4">凭据来源</div>
          <div class="col-span-2 font-display text-ink-1">{{ app.authSourceLabel }}</div>
          <div class="text-ink-4">已保存 Key</div>
          <div class="col-span-2 font-display text-ink-1">
            {{ app.hasStoredApiKey ? '存在' : '无' }}
          </div>
          <div class="text-ink-4">最近错误</div>
          <div class="col-span-2 text-ink-2 min-h-[20px]">{{ app.authError ?? '–' }}</div>
        </div>

        <div class="mt-5 flex flex-wrap gap-2">
          <PButton variant="secondary" @click="app.retryAuth">重新验证</PButton>
          <PButton v-if="app.hasStoredApiKey" variant="ghost" @click="app.clearSavedApiKey">
            清除已保存 Key
          </PButton>
        </div>

        <div class="mt-4 text-[12px] text-ink-4 leading-6">
          若服务端启用了 <span class="font-mono text-ink-2">PMS_API_KEY</span>，控制台会在未通过验证时自动回退到解锁页。
        </div>
      </PCard>

      <PCard edge class="xl:col-span-2">
        <div class="flex items-center justify-between gap-3 mb-4 flex-wrap">
          <div>
            <div class="text-[12px] uppercase font-display tracking-wider text-ink-4">模型配置</div>
            <div class="text-[12px] text-ink-4 mt-1">
              预设保存后立即生效；若 embedding 默认预设变更，后端会自动刷新 embedding 并重建索引。
            </div>
          </div>
          <div class="flex flex-wrap items-center gap-2">
            <PButton
              variant="secondary"
              :loading="loadingModelConfig"
              :disabled="modelConfigBusy"
              @click="loadModelConfig"
            >
              刷新
            </PButton>
            <PButton
              variant="secondary"
              :loading="testingModelConfig"
              :disabled="modelConfigBusy"
              @click="testModelConfig"
            >
              测试连接
            </PButton>
            <PButton
              variant="danger"
              :loading="restoringModelConfig"
              :disabled="modelConfigBusy"
              @click="restoreModelConfig"
            >
              恢复默认
            </PButton>
            <PButton
              variant="primary"
              :loading="savingModelConfig"
              :disabled="modelConfigBusy"
              @click="saveModelConfig"
            >
              保存配置
            </PButton>
          </div>
        </div>

        <div class="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-4">
          <div class="rounded-btn border border-shore-line/80 bg-shore-bg/30 px-3 py-2 text-[12px]">
            <div class="text-ink-4 mb-1">当前生效的 Embedding</div>
            <div class="font-mono text-ink-1 truncate">
              {{ modelConfig?.embedding.model || '未配置' }}
              <span class="text-ink-4 ml-1">· {{ modelConfig?.embedding.dimension ?? '–' }}d</span>
            </div>
            <div class="text-ink-4 mt-1">
              来源 {{ formatProviderSource(modelConfig?.embedding.source) }} ·
              Key {{ formatKeySource(modelConfig?.embedding.api_key_source) }}
            </div>
          </div>
          <div class="rounded-btn border border-shore-line/80 bg-shore-bg/30 px-3 py-2 text-[12px]">
            <div class="text-ink-4 mb-1">当前生效的 LLM</div>
            <div class="font-mono text-ink-1 truncate">
              {{ modelConfig?.llm.model || '未配置' }}
              <span class="text-ink-4 ml-1">· T={{ formatTemperature(modelConfig?.llm.temperature) }}</span>
            </div>
            <div class="text-ink-4 mt-1">
              来源 {{ formatProviderSource(modelConfig?.llm.source) }} ·
              Key {{ formatKeySource(modelConfig?.llm.api_key_source) }}
            </div>
          </div>
        </div>

        <!-- Preset editors -->
        <div class="mt-5 grid grid-cols-1 lg:grid-cols-2 gap-4">
          <!-- Embedding preset editor -->
          <div
            class="rounded-card border p-4 bg-shore-bg/30"
            :class="
              activeEmbeddingPreset && activeEmbeddingPreset.id === defaultEmbeddingId
                ? 'border-accent/70 shadow-[0_0_0_2px_rgba(124,92,255,0.15)]'
                : 'border-shore-line/80'
            "
          >
            <div class="flex items-center justify-between gap-3 mb-2">
              <div class="text-[13px] font-display text-ink-1">Embedding 预设</div>
              <div
                v-if="activeEmbeddingPreset && activeEmbeddingPreset.id === defaultEmbeddingId"
                class="text-[11px] text-accent font-display"
              >
                当前默认
              </div>
            </div>

            <div class="mb-3">
              <div class="text-[12px] text-ink-4 mb-1">预设模板</div>
              <select
                v-model="activeEmbeddingId"
                :disabled="!embeddingPresets.length"
                class="h-10 w-full rounded-btn bg-[#0F1018] border border-shore-line/80 px-3.5 text-[13px] text-ink-1 outline-none transition-colors duration-240 ease-shore hover:border-shore-border focus:border-accent focus:shadow-[0_0_0_3px_rgba(124,92,255,0.18)]"
              >
                <option v-if="!embeddingPresets.length" value="">尚无预设，请点击「+ 新建」</option>
                <option v-for="preset in embeddingPresets" :key="preset.id" :value="preset.id">
                  {{ preset.name }}{{ preset.id === defaultEmbeddingId ? '（默认）' : '' }}
                </option>
              </select>
            </div>

            <div class="flex flex-wrap items-center gap-2 mb-4">
              <PButton size="sm" variant="secondary" :loading="savingModelConfig" :disabled="modelConfigBusy" @click="saveModelConfig">
                保存
              </PButton>
              <PButton size="sm" variant="ghost" :disabled="modelConfigBusy || !activeEmbeddingPreset" @click="saveAsPreset('embedding')">
                另存为
              </PButton>
              <PButton size="sm" variant="ghost" :disabled="modelConfigBusy" @click="addPreset('embedding')">
                + 新建
              </PButton>
              <PButton
                size="sm"
                variant="ghost"
                :disabled="modelConfigBusy || embeddingPresets.length <= 1 || !activeEmbeddingPreset"
                @click="removeActivePreset('embedding')"
              >
                删除
              </PButton>
              <PButton
                size="sm"
                variant="ghost"
                :disabled="
                  modelConfigBusy ||
                  !activeEmbeddingPreset ||
                  activeEmbeddingPreset.id === defaultEmbeddingId
                "
                @click="setActiveAsDefault('embedding')"
              >
                设为默认
              </PButton>
            </div>

            <template v-if="activeEmbeddingPreset">
              <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div class="md:col-span-2">
                  <div class="text-[12px] text-ink-4 mb-1">预设名</div>
                  <PInput v-model="activeEmbeddingPreset.name" placeholder="给这份配置起个名字" />
                </div>
                <div>
                  <div class="text-[12px] text-ink-4 mb-1">API Base URL</div>
                  <PInput v-model="activeEmbeddingPreset.apiBase" placeholder="https://api.openai.com/v1" />
                </div>
                <div>
                  <div class="flex items-center justify-between gap-3 mb-1">
                    <div class="text-[12px] text-ink-4">模型名</div>
                    <PButton
                      size="sm"
                      variant="ghost"
                      :loading="fetchingModelsForId === activeEmbeddingPreset.id"
                      :disabled="modelConfigBusy"
                      @click="fetchProviderModels(activeEmbeddingPreset)"
                    >
                      获取模型
                    </PButton>
                  </div>
                  <PInput v-model="activeEmbeddingPreset.model" placeholder="text-embedding-3-large" />
                  <select
                    v-if="modelOptionsByPreset[activeEmbeddingPreset.id]?.length"
                    v-model="activeEmbeddingPreset.model"
                    class="mt-2 h-10 w-full rounded-btn bg-[#0F1018] border border-shore-line/80 px-3.5 text-[13px] text-ink-1 outline-none transition-colors duration-240 ease-shore hover:border-shore-border focus:border-accent focus:shadow-[0_0_0_3px_rgba(124,92,255,0.18)]"
                  >
                    <option value="">从已获取模型中选择</option>
                    <option v-for="model in modelOptionsByPreset[activeEmbeddingPreset.id]" :key="model" :value="model">
                      {{ model }}
                    </option>
                  </select>
                </div>
                <div>
                  <div class="flex items-center justify-between gap-3 mb-1">
                    <div class="text-[12px] text-ink-4">向量维度</div>
                    <PButton
                      size="sm"
                      variant="ghost"
                      :loading="detectingDimensionId === activeEmbeddingPreset.id"
                      :disabled="modelConfigBusy"
                      @click="detectEmbeddingDimension(activeEmbeddingPreset)"
                    >
                      自动识别
                    </PButton>
                  </div>
                  <PInput v-model="activeEmbeddingPreset.dimension" type="number" placeholder="1536" mono />
                </div>
                <div>
                  <div class="text-[12px] text-ink-4 mb-1">Key 模式</div>
                  <select
                    v-model="activeEmbeddingPreset.apiKeyAction"
                    class="h-10 w-full rounded-btn bg-[#0F1018] border border-shore-line/80 px-3.5 text-[13px] text-ink-1 outline-none transition-colors duration-240 ease-shore hover:border-shore-border focus:border-accent focus:shadow-[0_0_0_3px_rgba(124,92,255,0.18)]"
                  >
                    <option value="keep">保留已存 Key</option>
                    <option value="set">设置新 Key</option>
                    <option value="clear">清空 Key</option>
                  </select>
                  <div class="text-[11px] text-ink-4 mt-1">
                    当前：{{ activeEmbeddingPreset.apiKeyMasked ?? (activeEmbeddingPreset.apiKeyConfigured ? '********' : '未配置') }}
                  </div>
                </div>
                <div v-if="activeEmbeddingPreset.apiKeyAction === 'set'" class="md:col-span-2">
                  <div class="text-[12px] text-ink-4 mb-1">新 API Key</div>
                  <PInput v-model="activeEmbeddingPreset.apiKey" type="password" placeholder="sk-..." mono />
                </div>
              </div>
            </template>
            <div v-else class="text-[12px] text-ink-4">尚无预设，请点击上方「+ 新建」。</div>
          </div>

          <!-- LLM preset editor -->
          <div
            class="rounded-card border p-4 bg-shore-bg/30"
            :class="
              activeLlmPreset && activeLlmPreset.id === defaultLlmId
                ? 'border-accent/70 shadow-[0_0_0_2px_rgba(124,92,255,0.15)]'
                : 'border-shore-line/80'
            "
          >
            <div class="flex items-center justify-between gap-3 mb-2">
              <div class="text-[13px] font-display text-ink-1">LLM 预设</div>
              <div
                v-if="activeLlmPreset && activeLlmPreset.id === defaultLlmId"
                class="text-[11px] text-accent font-display"
              >
                当前默认
              </div>
            </div>

            <div class="mb-3">
              <div class="text-[12px] text-ink-4 mb-1">预设模板</div>
              <select
                v-model="activeLlmId"
                :disabled="!llmPresets.length"
                class="h-10 w-full rounded-btn bg-[#0F1018] border border-shore-line/80 px-3.5 text-[13px] text-ink-1 outline-none transition-colors duration-240 ease-shore hover:border-shore-border focus:border-accent focus:shadow-[0_0_0_3px_rgba(124,92,255,0.18)]"
              >
                <option v-if="!llmPresets.length" value="">尚无预设，请点击「+ 新建」</option>
                <option v-for="preset in llmPresets" :key="preset.id" :value="preset.id">
                  {{ preset.name }}{{ preset.id === defaultLlmId ? '（默认）' : '' }}
                </option>
              </select>
            </div>

            <div class="flex flex-wrap items-center gap-2 mb-4">
              <PButton size="sm" variant="secondary" :loading="savingModelConfig" :disabled="modelConfigBusy" @click="saveModelConfig">
                保存
              </PButton>
              <PButton size="sm" variant="ghost" :disabled="modelConfigBusy || !activeLlmPreset" @click="saveAsPreset('llm')">
                另存为
              </PButton>
              <PButton size="sm" variant="ghost" :disabled="modelConfigBusy" @click="addPreset('llm')">
                + 新建
              </PButton>
              <PButton
                size="sm"
                variant="ghost"
                :disabled="modelConfigBusy || llmPresets.length <= 1 || !activeLlmPreset"
                @click="removeActivePreset('llm')"
              >
                删除
              </PButton>
              <PButton
                size="sm"
                variant="ghost"
                :disabled="
                  modelConfigBusy ||
                  !activeLlmPreset ||
                  activeLlmPreset.id === defaultLlmId
                "
                @click="setActiveAsDefault('llm')"
              >
                设为默认
              </PButton>
            </div>

            <template v-if="activeLlmPreset">
              <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div class="md:col-span-2">
                  <div class="text-[12px] text-ink-4 mb-1">预设名</div>
                  <PInput v-model="activeLlmPreset.name" placeholder="给这份配置起个名字" />
                </div>
                <div>
                  <div class="text-[12px] text-ink-4 mb-1">API Base URL</div>
                  <PInput v-model="activeLlmPreset.apiBase" placeholder="https://api.openai.com/v1" />
                </div>
                <div>
                  <div class="flex items-center justify-between gap-3 mb-1">
                    <div class="text-[12px] text-ink-4">模型名</div>
                    <PButton
                      size="sm"
                      variant="ghost"
                      :loading="fetchingModelsForId === activeLlmPreset.id"
                      :disabled="modelConfigBusy"
                      @click="fetchProviderModels(activeLlmPreset)"
                    >
                      获取模型
                    </PButton>
                  </div>
                  <PInput v-model="activeLlmPreset.model" placeholder="gpt-4o-mini" />
                  <select
                    v-if="modelOptionsByPreset[activeLlmPreset.id]?.length"
                    v-model="activeLlmPreset.model"
                    class="mt-2 h-10 w-full rounded-btn bg-[#0F1018] border border-shore-line/80 px-3.5 text-[13px] text-ink-1 outline-none transition-colors duration-240 ease-shore hover:border-shore-border focus:border-accent focus:shadow-[0_0_0_3px_rgba(124,92,255,0.18)]"
                  >
                    <option value="">从已获取模型中选择</option>
                    <option v-for="model in modelOptionsByPreset[activeLlmPreset.id]" :key="model" :value="model">
                      {{ model }}
                    </option>
                  </select>
                </div>
                <div>
                  <div class="text-[12px] text-ink-4 mb-1">默认 Temperature</div>
                  <PInput
                    v-model="activeLlmPreset.temperature"
                    type="number"
                    placeholder="留空使用角色内置默认"
                    mono
                  />
                </div>
                <div>
                  <div class="text-[12px] text-ink-4 mb-1">Key 模式</div>
                  <select
                    v-model="activeLlmPreset.apiKeyAction"
                    class="h-10 w-full rounded-btn bg-[#0F1018] border border-shore-line/80 px-3.5 text-[13px] text-ink-1 outline-none transition-colors duration-240 ease-shore hover:border-shore-border focus:border-accent focus:shadow-[0_0_0_3px_rgba(124,92,255,0.18)]"
                  >
                    <option value="keep">保留已存 Key</option>
                    <option value="set">设置新 Key</option>
                    <option value="clear">清空 Key</option>
                  </select>
                  <div class="text-[11px] text-ink-4 mt-1">
                    当前：{{ activeLlmPreset.apiKeyMasked ?? (activeLlmPreset.apiKeyConfigured ? '********' : '未配置') }}
                  </div>
                </div>
                <div v-if="activeLlmPreset.apiKeyAction === 'set'" class="md:col-span-2">
                  <div class="text-[12px] text-ink-4 mb-1">新 API Key</div>
                  <PInput v-model="activeLlmPreset.apiKey" type="password" placeholder="sk-..." mono />
                </div>
              </div>
            </template>
            <div v-else class="text-[12px] text-ink-4">尚无预设，请点击上方「+ 新建」。</div>
          </div>
        </div>

        <!-- Roles -->
        <div class="mt-6">
          <div class="text-[12px] uppercase font-display tracking-wider text-ink-4 mb-3">
            LLM 角色
          </div>
          <div class="grid grid-cols-1 lg:grid-cols-3 gap-4">
            <div
              v-for="entry in roleEntries"
              :key="entry.key"
              class="rounded-card border border-shore-line/80 p-4 bg-shore-bg/30"
            >
              <div class="text-[13px] font-display text-ink-1">{{ entry.label }}</div>
              <div class="text-[12px] text-ink-4 mt-1 mb-3">{{ entry.description }}</div>

              <div class="space-y-3">
                <div>
                  <div class="text-[12px] text-ink-4 mb-1">使用预设</div>
                  <select
                    v-model="roleForms[entry.key].presetId"
                    class="h-10 w-full rounded-btn bg-[#0F1018] border border-shore-line/80 px-3.5 text-[13px] text-ink-1 outline-none transition-colors duration-240 ease-shore hover:border-shore-border focus:border-accent focus:shadow-[0_0_0_3px_rgba(124,92,255,0.18)]"
                  >
                    <option value="">跟随默认</option>
                    <option v-for="preset in llmPresets" :key="preset.id" :value="preset.id">
                      {{ preset.name }}{{ preset.id === defaultLlmId ? '（默认）' : '' }}
                    </option>
                  </select>
                </div>
                <div>
                  <div class="text-[12px] text-ink-4 mb-1">
                    Temperature（留空继承预设）
                  </div>
                  <PInput
                    v-model="roleForms[entry.key].temperature"
                    type="number"
                    :placeholder="`留空使用 ${entry.defaultTemperature}`"
                    mono
                  />
                </div>
              </div>

              <div class="mt-4 grid grid-cols-3 gap-y-2 text-[12px]">
                <div class="text-ink-4">生效模型</div>
                <div class="col-span-2 font-mono text-ink-2 truncate">
                  {{ getRoleBinding(entry.key)?.resolved.model || effectiveLlmForRole(entry.key)?.model || '未配置' }}
                </div>
                <div class="text-ink-4">生效 Temperature</div>
                <div class="col-span-2 text-ink-2">{{ effectiveRoleTemperatureLabel(entry.key) }}</div>
                <div class="text-ink-4">Key 来源</div>
                <div class="col-span-2 text-ink-2">
                  {{ formatKeySource(getRoleBinding(entry.key)?.resolved.api_key_source) }}
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Prompts -->
        <div class="mt-6">
          <div class="flex items-center justify-between gap-3 mb-3 flex-wrap">
            <div class="text-[12px] uppercase font-display tracking-wider text-ink-4">
              系统提示词
            </div>
            <span v-if="loadingDefaultPrompts" class="text-[11px] text-ink-4">
              加载默认中…
            </span>
          </div>
          <div
            v-if="defaultPromptsError"
            class="rounded-btn border border-state-invalidated/40 bg-state-invalidated/10 px-3 py-2 text-[12px] text-state-invalidated mb-3"
          >
            {{ defaultPromptsError }}
          </div>
          <div class="space-y-3">
            <div
              v-for="entry in roleEntries"
              :key="entry.key"
              class="rounded-card border border-shore-line/80 p-4 bg-shore-bg/30"
            >
              <div class="flex items-start justify-between gap-3 mb-2 flex-wrap">
                <div>
                  <span class="text-[13px] font-display text-ink-1">{{ entry.label }}</span>
                  <span class="text-[11px] text-ink-4 ml-2">{{ entry.description }}</span>
                </div>
                <div class="flex items-center gap-2 flex-wrap">
                  <span
                    :class="promptIsOverridden(entry.key) ? 'text-accent' : 'text-ink-4'"
                    class="text-[11px] font-display"
                  >
                    {{ promptIsOverridden(entry.key) ? '已覆盖' : '使用内置默认' }}
                  </span>
                  <PButton
                    size="sm"
                    variant="ghost"
                    :loading="loadingDefaultPrompts"
                    :disabled="modelConfigBusy"
                    @click="togglePromptPreview(entry.key)"
                  >
                    {{ promptPreviewOpen[entry.key] ? '收起默认' : '查看默认' }}
                  </PButton>
                  <PButton
                    size="sm"
                    variant="ghost"
                    :loading="loadingDefaultPrompts"
                    :disabled="modelConfigBusy"
                    @click="restorePromptDefault(entry.key)"
                  >
                    填充默认
                  </PButton>
                  <PButton
                    size="sm"
                    variant="ghost"
                    :disabled="modelConfigBusy || !promptIsOverridden(entry.key)"
                    @click="clearPromptOverride(entry.key)"
                  >
                    清空覆盖
                  </PButton>
                </div>
              </div>
              <textarea
                v-model="promptForms[entry.key]"
                rows="10"
                placeholder="留空使用 worker 内置默认（点击「查看默认」可预览）"
                class="w-full rounded-btn bg-[#0F1018] border border-shore-line/80 px-3 py-2 text-[12px] text-ink-1 font-mono leading-5 outline-none transition-colors duration-240 ease-shore hover:border-shore-border focus:border-accent focus:shadow-[0_0_0_3px_rgba(124,92,255,0.18)] resize-y"
              />
              <div
                v-if="promptPreviewOpen[entry.key]"
                class="mt-2 rounded-btn border border-shore-line/60 bg-[#0A0B10] px-3 py-2 text-[11px] text-ink-3 font-mono whitespace-pre-wrap max-h-80 overflow-auto"
              >{{ defaultPrompts?.[entry.key] ?? '' }}</div>
            </div>
          </div>
        </div>

        <!-- Storage + test result footer -->
        <div class="mt-4 grid grid-cols-1 md:grid-cols-3 gap-3 text-[12px]">
          <div class="rounded-btn border border-shore-line/80 bg-shore-bg/30 px-3 py-2">
            <div class="text-ink-4">覆盖文件路径</div>
            <div class="font-mono text-ink-2 break-all">{{ modelConfig?.storage.path ?? '–' }}</div>
          </div>
          <div class="rounded-btn border border-shore-line/80 bg-shore-bg/30 px-3 py-2">
            <div class="text-ink-4">覆盖状态</div>
            <div class="text-ink-2">{{ modelConfig?.storage.override_active ? '已启用覆盖' : '仅使用环境变量' }}</div>
          </div>
          <div class="rounded-btn border border-shore-line/80 bg-shore-bg/30 px-3 py-2">
            <div class="text-ink-4">最近保存</div>
            <div class="text-ink-2">{{ modelConfig?.storage.updated_at ?? '未保存' }}</div>
          </div>
        </div>

        <div v-if="modelConfigTest" class="mt-4 grid grid-cols-1 md:grid-cols-2 gap-3 text-[12px]">
          <div class="rounded-btn border border-shore-line/80 bg-shore-bg/30 px-3 py-2">
            <div class="flex items-center justify-between gap-3">
              <span class="text-ink-4">Embedding 测试</span>
              <span :class="modelConfigTest.embedding.ok ? 'text-state-active' : 'text-state-invalidated'">
                {{ modelConfigTest.embedding.ok ? '通过' : '失败' }}
              </span>
            </div>
            <div class="text-ink-2 mt-1">{{ modelConfigTest.embedding.message }}</div>
            <div class="text-ink-4 mt-1">
              来源：{{ formatProviderSource(modelConfigTest.embedding.source) }}
            </div>
          </div>
          <div class="rounded-btn border border-shore-line/80 bg-shore-bg/30 px-3 py-2">
            <div class="flex items-center justify-between gap-3">
              <span class="text-ink-4">LLM 测试</span>
              <span :class="modelConfigTest.llm.ok ? 'text-state-active' : 'text-state-invalidated'">
                {{ modelConfigTest.llm.ok ? '通过' : '失败' }}
              </span>
            </div>
            <div class="text-ink-2 mt-1">{{ modelConfigTest.llm.message }}</div>
            <div class="text-ink-4 mt-1">来源：{{ formatProviderSource(modelConfigTest.llm.source) }}</div>
          </div>
        </div>
        <div v-if="modelConfigTest" class="mt-3 grid grid-cols-1 md:grid-cols-3 gap-3 text-[12px]">
          <div
            v-for="entry in roleEntries"
            :key="entry.key"
            class="rounded-btn border border-shore-line/80 bg-shore-bg/30 px-3 py-2"
          >
            <div class="flex items-center justify-between gap-3">
              <span class="text-ink-4">{{ entry.label }} 测试</span>
              <span
                :class="modelConfigTest.roles?.[entry.key]?.ok ? 'text-state-active' : 'text-state-invalidated'"
              >
                {{ modelConfigTest.roles?.[entry.key]?.ok ? '通过' : '失败' }}
              </span>
            </div>
            <div class="text-ink-2 mt-1">{{ modelConfigTest.roles?.[entry.key]?.message ?? '未执行' }}</div>
            <div class="text-ink-4 mt-1">
              来源：{{ formatProviderSource(modelConfigTest.roles?.[entry.key]?.source) }}
            </div>
          </div>
        </div>

        <div
          v-if="modelConfigNotice"
          class="mt-4 rounded-btn border border-state-active/25 bg-state-active/10 px-3 py-2 text-[12px] text-state-active"
        >
          {{ modelConfigNotice }}
        </div>
        <div
          v-if="modelConfigError"
          class="mt-3 rounded-btn border border-state-invalidated/25 bg-state-invalidated/10 px-3 py-2 text-[12px] text-state-invalidated"
        >
          {{ modelConfigError }}
        </div>
      </PCard>
    </div>
  </div>
</template>
