<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import PHero from '@/components/ui/PHero.vue'
import PCard from '@/components/ui/PCard.vue'
import PButton from '@/components/ui/PButton.vue'
import PInput from '@/components/ui/PInput.vue'
import { useAppStore } from '@/stores/app'
import { api, ShoreApiError } from '@/api/http'
import type {
  DetectEmbeddingDimensionResponse,
  ListProviderModelsResponse,
  ModelConfigResponse,
  ModelConfigTestResponse,
  ProviderKind,
  UpdateModelConfigRequest,
  UpdateModelConfigResponse
} from '@/api/types'

type RoleKey = 'scorer' | 'reflector' | 'query_analyzer'

type RoleFormState = {
  enabled: boolean
  apiBase: string
  model: string
  temperature: string
  apiKeyMode: 'inherit' | 'clear' | 'set'
  apiKey: string
}

const ROLE_META: Record<RoleKey, { label: string; description: string; defaultTemperature: number }> = {
  scorer: {
    label: 'Scorer',
    description: '对话轮次记忆抽取',
    defaultTemperature: 0.3
  },
  reflector: {
    label: 'Reflector',
    description: '重复 / 矛盾 / 总结整理',
    defaultTemperature: 0.4
  },
  query_analyzer: {
    label: 'Query Analyzer',
    description: '召回时 query 命名实体分析',
    defaultTemperature: 0.1
  }
}

const roleKeys = Object.keys(ROLE_META) as RoleKey[]
const roleEntries = roleKeys.map((key) => ({ key, ...ROLE_META[key] }))
const app = useAppStore()

const loadingModelConfig = ref(false)
const loadingEmbeddingModels = ref(false)
const loadingLlmModels = ref(false)
const loadingRoleModels = reactive<Record<RoleKey, boolean>>({
  scorer: false,
  reflector: false,
  query_analyzer: false
})
const savingModelConfig = ref(false)
const restoringModelConfig = ref(false)
const testingModelConfig = ref(false)
const detectingEmbeddingDimension = ref(false)
const modelConfig = ref<ModelConfigResponse | null>(null)
const modelConfigError = ref<string | null>(null)
const modelConfigNotice = ref<string | null>(null)
const modelConfigTest = ref<ModelConfigTestResponse | null>(null)
const embeddingModelOptions = ref<string[]>([])
const llmModelOptions = ref<string[]>([])
const roleModelOptions = reactive<Record<RoleKey, string[]>>({
  scorer: [],
  reflector: [],
  query_analyzer: []
})

function emptyRoleForm(): RoleFormState {
  return {
    enabled: false,
    apiBase: '',
    model: '',
    temperature: '',
    apiKeyMode: 'inherit',
    apiKey: ''
  }
}

function createRoleForms(): Record<RoleKey, RoleFormState> {
  return {
    scorer: emptyRoleForm(),
    reflector: emptyRoleForm(),
    query_analyzer: emptyRoleForm()
  }
}

const form = reactive({
  embeddingApiBase: '',
  embeddingModel: '',
  embeddingDimension: '1536',
  embeddingApiKey: '',
  embeddingClearKey: false,
  llmApiBase: '',
  llmModel: '',
  llmTemperature: '',
  llmApiKey: '',
  llmClearKey: false,
  roles: createRoleForms()
})

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

const modelConfigBusy = computed(
  () =>
    loadingModelConfig.value ||
    loadingEmbeddingModels.value ||
    loadingLlmModels.value ||
    roleKeys.some((role) => loadingRoleModels[role]) ||
    savingModelConfig.value ||
    restoringModelConfig.value ||
    testingModelConfig.value ||
    detectingEmbeddingDimension.value
)

function formatProviderSource(source: string): string {
  switch (source) {
    case 'inherit':
      return '继承通用 LLM'
    case 'file':
      return '覆盖文件'
    case 'mixed':
      return '环境 + 覆盖'
    case 'env':
    default:
      return '环境变量'
  }
}

function providerLabel(kind: ProviderKind, role?: RoleKey): string {
  if (role) return ROLE_META[role].label
  return kind === 'embedding' ? 'Embedding' : 'LLM'
}

function sortedModels(models: string[]): string[] {
  return Array.from(new Set(models.filter((value) => value.trim()))).sort((a, b) =>
    a.localeCompare(b)
  )
}

function parseOptionalNumber(raw: string): number | undefined {
  const value = raw.trim()
  if (!value) return undefined
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : undefined
}

function rolePlaceholder(role: RoleKey, field: 'apiBase' | 'model' | 'temperature'): string {
  if (field === 'apiBase') return form.llmApiBase.trim() || 'https://api.openai.com/v1'
  if (field === 'model') return form.llmModel.trim() || '继承通用 LLM 模型'
  return form.llmTemperature.trim() || String(ROLE_META[role].defaultTemperature)
}

function buildModelsRequest(provider: ProviderKind, role?: RoleKey) {
  if (provider === 'embedding') {
    const apiKey = form.embeddingApiKey.trim()
    return {
      provider,
      api_base: form.embeddingApiBase.trim(),
      api_key: apiKey || undefined,
      clear_api_key: form.embeddingClearKey
    }
  }

  const roleState = role ? form.roles[role] : null
  const apiKey = roleState
    ? roleState.enabled
      ? roleState.apiKeyMode === 'set'
        ? roleState.apiKey.trim()
        : ''
      : form.llmApiKey.trim()
    : form.llmApiKey.trim()
  const apiBase = roleState
    ? roleState.enabled
      ? roleState.apiBase.trim() || form.llmApiBase.trim()
      : form.llmApiBase.trim()
    : form.llmApiBase.trim()

  return {
    provider,
    api_base: apiBase,
    role: role || undefined,
    api_key: apiKey || undefined,
    clear_api_key: roleState
      ? roleState.enabled
        ? roleState.apiKeyMode === 'clear'
        : form.llmClearKey
      : form.llmClearKey
  }
}

async function fetchProviderModels(provider: ProviderKind, role?: RoleKey) {
  if (provider === 'embedding') {
    loadingEmbeddingModels.value = true
  } else if (role) {
    loadingRoleModels[role] = true
  } else {
    loadingLlmModels.value = true
  }

  modelConfigError.value = null
  modelConfigNotice.value = null
  try {
    const res = await api.post<ListProviderModelsResponse>(
      '/v1/model-config/models',
      buildModelsRequest(provider, role)
    )
    const models = sortedModels(res.models)
    if (provider === 'embedding') {
      embeddingModelOptions.value = models
    } else if (role) {
      roleModelOptions[role] = models
    } else {
      llmModelOptions.value = models
    }
    modelConfigNotice.value = models.length
      ? `已获取 ${models.length} 个 ${providerLabel(provider, role)} 模型。`
      : `${providerLabel(provider, role)} 提供方没有返回可用模型。`
  } catch (err) {
    modelConfigError.value = `获取 ${providerLabel(provider, role)} 模型失败：${resolveError(err)}`
  } finally {
    if (provider === 'embedding') {
      loadingEmbeddingModels.value = false
    } else if (role) {
      loadingRoleModels[role] = false
    } else {
      loadingLlmModels.value = false
    }
  }
}

async function detectEmbeddingDimension(options?: { silent?: boolean }) {
  const model = form.embeddingModel.trim()
  if (!model) {
    modelConfigError.value = '请先填写 Embedding 模型名。'
    return null
  }
  detectingEmbeddingDimension.value = true
  if (!options?.silent) {
    modelConfigError.value = null
    modelConfigNotice.value = null
  }
  try {
    const apiKey = form.embeddingApiKey.trim()
    const res = await api.post<DetectEmbeddingDimensionResponse>(
      '/v1/model-config/embedding/dimension',
      {
        api_base: form.embeddingApiBase.trim(),
        model,
        api_key: apiKey || undefined,
        clear_api_key: form.embeddingClearKey
      }
    )
    form.embeddingDimension = String(res.dimension)
    if (!options?.silent) {
      modelConfigNotice.value = `已自动识别 ${res.model} 的向量维度：${res.dimension}`
    }
    return res.dimension
  } catch (err) {
    if (!options?.silent) {
      modelConfigError.value = `识别 Embedding 维度失败：${resolveError(err)}`
    }
    return null
  } finally {
    detectingEmbeddingDimension.value = false
  }
}

async function onEmbeddingModelSelect() {
  if (!form.embeddingModel.trim()) return
  await detectEmbeddingDimension()
}

function formatKeySource(source: string): string {
  switch (source) {
    case 'inherit':
      return '继承通用 LLM'
    case 'file':
      return '覆盖文件'
    case 'cleared':
      return '已清空（覆盖）'
    case 'unset':
      return '未配置'
    case 'env':
    default:
      return '环境变量'
  }
}

function resolveError(err: unknown): string {
  if (err instanceof ShoreApiError) return err.message
  if (err instanceof Error) return err.message
  return '请求失败，请稍后重试。'
}

function hydrateForm(config: ModelConfigResponse) {
  form.embeddingApiBase = config.embedding.api_base ?? ''
  form.embeddingModel = config.embedding.model ?? ''
  form.embeddingDimension = String(config.embedding.dimension ?? 1536)
  form.embeddingApiKey = ''
  form.embeddingClearKey = false
  embeddingModelOptions.value = []

  form.llmApiBase = config.llm.api_base ?? ''
  form.llmModel = config.llm.model ?? ''
  form.llmTemperature =
    config.overrides.llm.temperature !== null && config.overrides.llm.temperature !== undefined
      ? String(config.overrides.llm.temperature)
      : ''
  form.llmApiKey = ''
  form.llmClearKey = false
  llmModelOptions.value = []

  for (const role of roleKeys) {
    const override = config.overrides.roles[role]
    form.roles[role].enabled = Boolean(config.roles[role]?.override_active)
    form.roles[role].apiBase = override?.api_base ?? ''
    form.roles[role].model = override?.model ?? ''
    form.roles[role].temperature =
      override?.temperature !== null && override?.temperature !== undefined
        ? String(override.temperature)
        : ''
    form.roles[role].apiKeyMode = override?.api_key_mode ?? 'inherit'
    form.roles[role].apiKey = ''
    roleModelOptions[role] = []
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

function buildUpdatePayload(): UpdateModelConfigRequest {
  const parsedDim = Number.parseInt(form.embeddingDimension.trim(), 10)
  const dimension = Number.isFinite(parsedDim) && parsedDim > 0 ? parsedDim : 1536
  const embeddingApiKey = form.embeddingApiKey.trim()
  const llmApiKey = form.llmApiKey.trim()

  return {
    embedding: {
      api_base: form.embeddingApiBase.trim(),
      model: form.embeddingModel.trim(),
      dimension,
      api_key: embeddingApiKey || undefined,
      clear_api_key: form.embeddingClearKey,
      auto_detect_dimension: true
    },
    llm: {
      api_base: form.llmApiBase.trim(),
      model: form.llmModel.trim(),
      temperature: parseOptionalNumber(form.llmTemperature),
      api_key: llmApiKey || undefined,
      clear_api_key: form.llmClearKey
    },
    roles: roleKeys.reduce<NonNullable<UpdateModelConfigRequest['roles']>>((acc, role) => {
      const roleState = form.roles[role]
      acc[role] = {
        enabled: roleState.enabled,
        api_base: roleState.enabled ? roleState.apiBase.trim() || undefined : undefined,
        model: roleState.enabled ? roleState.model.trim() || undefined : undefined,
        temperature: roleState.enabled ? parseOptionalNumber(roleState.temperature) : undefined,
        api_key_mode: roleState.enabled ? roleState.apiKeyMode : undefined,
        api_key:
          roleState.enabled && roleState.apiKeyMode === 'set'
            ? roleState.apiKey.trim() || undefined
            : undefined,
        clear_api_key: roleState.enabled ? roleState.apiKeyMode === 'clear' : false
      }
      return acc
    }, {})
  }
}

function updateNoticeFromResponse(res: UpdateModelConfigResponse, mode: 'save' | 'restore') {
  if (!res.embedding_changed) {
    modelConfigNotice.value = mode === 'restore' ? '已恢复为环境变量配置。' : '已保存，配置立即生效。'
    return
  }
  const reason = res.embedding_dimension_changed ? 'embedding 维度变更' : 'embedding 配置变更'
  modelConfigNotice.value = `${mode === 'restore' ? '已恢复环境配置' : '已保存配置'}，检测到 ${reason}，已自动刷新 ${res.memory_embeddings_refreshed} 条记忆 embedding，并重建索引（memories=${res.reindexed_memories}, entities=${res.reindexed_entities}）。`
}

async function saveModelConfig() {
  savingModelConfig.value = true
  modelConfigError.value = null
  modelConfigNotice.value = null
  try {
    if (form.embeddingModel.trim()) {
      await detectEmbeddingDimension({ silent: true })
    }
    const payload = buildUpdatePayload()
    const res = await api.put<UpdateModelConfigResponse>('/v1/model-config', payload)
    modelConfig.value = res.config
    hydrateForm(res.config)
    updateNoticeFromResponse(res, 'save')
  } catch (err) {
    modelConfigError.value = `保存模型配置失败：${resolveError(err)}`
  } finally {
    savingModelConfig.value = false
  }
}

async function restoreModelConfig() {
  if (!window.confirm('确认恢复为环境变量默认配置？覆盖文件将被删除。')) return
  restoringModelConfig.value = true
  modelConfigError.value = null
  modelConfigNotice.value = null
  try {
    const res = await api.delete<UpdateModelConfigResponse>('/v1/model-config')
    modelConfig.value = res.config
    hydrateForm(res.config)
    updateNoticeFromResponse(res, 'restore')
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
    if (res.embedding.dimension && res.embedding.dimension > 0) {
      form.embeddingDimension = String(res.embedding.dimension)
    }
    const roleFailures = roleKeys.some((role) => Boolean(res.roles?.[role]) && !res.roles[role].ok)
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

onMounted(() => {
  void loadModelConfig()
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
        <div class="flex items-center justify-between gap-3 mb-4">
          <div>
            <div class="text-[12px] uppercase font-display tracking-wider text-ink-4">模型配置</div>
            <div class="text-[12px] text-ink-4 mt-1">
              保存后立即生效；若 embedding 配置变更，后端会自动刷新 embedding 并重建索引。
            </div>
          </div>
          <div class="flex flex-wrap items-center gap-2">
            <PButton variant="secondary" :loading="loadingModelConfig" :disabled="modelConfigBusy" @click="loadModelConfig">
              刷新
            </PButton>
            <PButton variant="secondary" :loading="testingModelConfig" :disabled="modelConfigBusy" @click="testModelConfig">
              测试连接
            </PButton>
            <PButton variant="danger" :loading="restoringModelConfig" :disabled="modelConfigBusy" @click="restoreModelConfig">
              恢复默认
            </PButton>
            <PButton variant="primary" :loading="savingModelConfig" :disabled="modelConfigBusy" @click="saveModelConfig">
              保存配置
            </PButton>
          </div>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-5">
          <div class="rounded-card border border-shore-line/80 p-4 bg-shore-bg/30">
            <div class="flex items-center justify-between gap-3 mb-3">
              <div class="text-[13px] font-display text-ink-1">Embedding 提供方</div>
              <PButton
                size="sm"
                variant="ghost"
                :loading="loadingEmbeddingModels"
                :disabled="modelConfigBusy"
                @click="fetchProviderModels('embedding')"
              >
                获取模型
              </PButton>
            </div>
            <div class="grid grid-cols-3 gap-y-2 text-[12px] mb-4">
              <div class="text-ink-4">配置来源</div>
              <div class="col-span-2 text-ink-2">{{ modelConfig ? formatProviderSource(modelConfig.embedding.source) : '–' }}</div>
              <div class="text-ink-4">Key 来源</div>
              <div class="col-span-2 text-ink-2">{{ modelConfig ? formatKeySource(modelConfig.embedding.api_key_source) : '–' }}</div>
              <div class="text-ink-4">当前 Key</div>
              <div class="col-span-2 font-mono text-ink-2">{{ modelConfig?.embedding.api_key_masked ?? '未设置' }}</div>
            </div>

            <div class="space-y-3">
              <div>
                <div class="text-[12px] text-ink-4 mb-1">API Base URL</div>
                <PInput v-model="form.embeddingApiBase" placeholder="https://api.openai.com/v1" />
              </div>
              <div>
                <div class="text-[12px] text-ink-4 mb-1">模型名</div>
                <PInput v-model="form.embeddingModel" placeholder="text-embedding-3-large" />
                <select
                  v-if="embeddingModelOptions.length"
                  v-model="form.embeddingModel"
                  class="mt-2 h-10 w-full rounded-btn bg-[#0F1018] border border-shore-line/80 px-3.5 text-[13px] text-ink-1 outline-none transition-colors duration-240 ease-shore hover:border-shore-border focus:border-accent focus:shadow-[0_0_0_3px_rgba(124,92,255,0.18)]"
                  @change="onEmbeddingModelSelect"
                >
                  <option value="">从已获取模型中选择</option>
                  <option v-for="model in embeddingModelOptions" :key="model" :value="model">
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
                    :loading="detectingEmbeddingDimension"
                    :disabled="modelConfigBusy"
                    @click="detectEmbeddingDimension()"
                  >
                    自动识别
                  </PButton>
                </div>
                <PInput v-model="form.embeddingDimension" type="number" placeholder="1536" mono />
              </div>
              <div>
                <div class="text-[12px] text-ink-4 mb-1">API Key（留空表示不改）</div>
                <PInput v-model="form.embeddingApiKey" type="password" placeholder="输入新 Key 进行覆盖" mono />
              </div>
              <label class="flex items-center gap-2 text-[12px] text-ink-3 select-none">
                <input v-model="form.embeddingClearKey" type="checkbox" class="accent-accent" />
                清空 Embedding Key（强制移除覆盖 key）
              </label>
            </div>
          </div>

          <div class="rounded-card border border-shore-line/80 p-4 bg-shore-bg/30">
            <div class="flex items-center justify-between gap-3 mb-3">
              <div class="text-[13px] font-display text-ink-1">LLM 提供方</div>
              <PButton
                size="sm"
                variant="ghost"
                :loading="loadingLlmModels"
                :disabled="modelConfigBusy"
                @click="fetchProviderModels('llm')"
              >
                获取模型
              </PButton>
            </div>
            <div class="grid grid-cols-3 gap-y-2 text-[12px] mb-4">
              <div class="text-ink-4">配置来源</div>
              <div class="col-span-2 text-ink-2">{{ modelConfig ? formatProviderSource(modelConfig.llm.source) : '–' }}</div>
              <div class="text-ink-4">Key 来源</div>
              <div class="col-span-2 text-ink-2">{{ modelConfig ? formatKeySource(modelConfig.llm.api_key_source) : '–' }}</div>
              <div class="text-ink-4">当前 Key</div>
              <div class="col-span-2 font-mono text-ink-2">{{ modelConfig?.llm.api_key_masked ?? '未设置' }}</div>
            </div>

            <div class="space-y-3">
              <div>
                <div class="text-[12px] text-ink-4 mb-1">API Base URL</div>
                <PInput v-model="form.llmApiBase" placeholder="https://api.openai.com/v1" />
              </div>
              <div>
                <div class="text-[12px] text-ink-4 mb-1">模型名</div>
                <PInput v-model="form.llmModel" placeholder="gpt-4o-mini" />
                <select
                  v-if="llmModelOptions.length"
                  v-model="form.llmModel"
                  class="mt-2 h-10 w-full rounded-btn bg-[#0F1018] border border-shore-line/80 px-3.5 text-[13px] text-ink-1 outline-none transition-colors duration-240 ease-shore hover:border-shore-border focus:border-accent focus:shadow-[0_0_0_3px_rgba(124,92,255,0.18)]"
                >
                  <option value="">从已获取模型中选择</option>
                  <option v-for="model in llmModelOptions" :key="model" :value="model">
                    {{ model }}
                  </option>
                </select>
              </div>
              <div>
                <div class="text-[12px] text-ink-4 mb-1">默认 Temperature</div>
                <PInput
                  v-model="form.llmTemperature"
                  type="number"
                  placeholder="留空则由角色默认值决定"
                  mono
                />
              </div>
              <div>
                <div class="text-[12px] text-ink-4 mb-1">API Key（留空表示不改）</div>
                <PInput v-model="form.llmApiKey" type="password" placeholder="输入新 Key 进行覆盖" mono />
              </div>
              <label class="flex items-center gap-2 text-[12px] text-ink-3 select-none">
                <input v-model="form.llmClearKey" type="checkbox" class="accent-accent" />
                清空 LLM Key（强制移除覆盖 key）
              </label>
            </div>
          </div>
        </div>

        <div class="mt-5">
          <div class="text-[12px] uppercase font-display tracking-wider text-ink-4 mb-3">LLM 角色</div>
          <div class="grid grid-cols-1 lg:grid-cols-3 gap-5">
            <div
              v-for="entry in roleEntries"
              :key="entry.key"
              class="rounded-card border border-shore-line/80 p-4 bg-shore-bg/30"
            >
              <div class="flex items-start justify-between gap-3 mb-3">
                <div>
                  <div class="text-[13px] font-display text-ink-1">{{ entry.label }}</div>
                  <div class="text-[12px] text-ink-4 mt-1">{{ entry.description }}</div>
                </div>
                <PButton
                  size="sm"
                  variant="ghost"
                  :loading="loadingRoleModels[entry.key]"
                  :disabled="modelConfigBusy"
                  @click="fetchProviderModels('llm', entry.key)"
                >
                  获取模型
                </PButton>
              </div>

              <div class="grid grid-cols-3 gap-y-2 text-[12px] mb-4">
                <div class="text-ink-4">配置来源</div>
                <div class="col-span-2 text-ink-2">
                  {{ modelConfig ? formatProviderSource(modelConfig.roles[entry.key]?.source ?? 'inherit') : '–' }}
                </div>
                <div class="text-ink-4">Key 来源</div>
                <div class="col-span-2 text-ink-2">
                  {{ modelConfig ? formatKeySource(modelConfig.roles[entry.key]?.api_key_source ?? 'inherit') : '–' }}
                </div>
                <div class="text-ink-4">当前 Key</div>
                <div class="col-span-2 font-mono text-ink-2">
                  {{ modelConfig?.roles[entry.key]?.api_key_masked ?? '继承通用 LLM' }}
                </div>
                <div class="text-ink-4">生效 Temperature</div>
                <div class="col-span-2 text-ink-2">
                  {{ modelConfig?.roles[entry.key]?.temperature ?? entry.defaultTemperature }}
                </div>
              </div>

              <label class="flex items-center gap-2 text-[12px] text-ink-3 select-none">
                <input v-model="form.roles[entry.key].enabled" type="checkbox" class="accent-accent" />
                启用独立配置（关闭则完全继承通用 LLM）
              </label>

              <div class="space-y-3 mt-3" :class="form.roles[entry.key].enabled ? '' : 'opacity-60'">
                <div>
                  <div class="text-[12px] text-ink-4 mb-1">API Base URL</div>
                  <PInput
                    v-model="form.roles[entry.key].apiBase"
                    :disabled="!form.roles[entry.key].enabled"
                    :placeholder="rolePlaceholder(entry.key, 'apiBase')"
                  />
                </div>
                <div>
                  <div class="text-[12px] text-ink-4 mb-1">模型名</div>
                  <PInput
                    v-model="form.roles[entry.key].model"
                    :disabled="!form.roles[entry.key].enabled"
                    :placeholder="rolePlaceholder(entry.key, 'model')"
                  />
                  <select
                    v-if="roleModelOptions[entry.key].length"
                    v-model="form.roles[entry.key].model"
                    :disabled="!form.roles[entry.key].enabled"
                    class="mt-2 h-10 w-full rounded-btn bg-[#0F1018] border border-shore-line/80 px-3.5 text-[13px] text-ink-1 outline-none transition-colors duration-240 ease-shore hover:border-shore-border focus:border-accent focus:shadow-[0_0_0_3px_rgba(124,92,255,0.18)]"
                  >
                    <option value="">从已获取模型中选择</option>
                    <option v-for="model in roleModelOptions[entry.key]" :key="model" :value="model">
                      {{ model }}
                    </option>
                  </select>
                </div>
                <div>
                  <div class="text-[12px] text-ink-4 mb-1">Temperature</div>
                  <PInput
                    v-model="form.roles[entry.key].temperature"
                    type="number"
                    :disabled="!form.roles[entry.key].enabled"
                    :placeholder="rolePlaceholder(entry.key, 'temperature')"
                    mono
                  />
                </div>
                <div>
                  <div class="text-[12px] text-ink-4 mb-1">API Key（留空表示不改）</div>
                  <PInput
                    v-model="form.roles[entry.key].apiKey"
                    type="password"
                    :disabled="!form.roles[entry.key].enabled || form.roles[entry.key].apiKeyMode !== 'set'"
                    placeholder="输入新 Key 进行覆盖"
                    mono
                  />
                </div>
                <div>
                  <div class="text-[12px] text-ink-4 mb-1">Key 模式</div>
                  <select
                    v-model="form.roles[entry.key].apiKeyMode"
                    :disabled="!form.roles[entry.key].enabled"
                    class="h-10 w-full rounded-btn bg-[#0F1018] border border-shore-line/80 px-3.5 text-[13px] text-ink-1 outline-none transition-colors duration-240 ease-shore hover:border-shore-border focus:border-accent focus:shadow-[0_0_0_3px_rgba(124,92,255,0.18)]"
                  >
                    <option value="inherit">继承通用 LLM Key</option>
                    <option value="clear">显式清空 Key</option>
                    <option value="set">使用独立 Key</option>
                  </select>
                </div>
              </div>

              <div class="mt-3 text-[11px] text-ink-4">
                默认 Temperature 为 {{ entry.defaultTemperature }}；启用后留空字段会继承通用 LLM。
              </div>
            </div>
          </div>
        </div>

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
            <div class="text-ink-4">最近更新时间</div>
            <div class="text-ink-2">{{ modelConfig?.storage.updated_at ?? '–' }}</div>
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
            <div class="text-ink-4 mt-1">维度：{{ modelConfigTest.embedding.dimension ?? '–' }}</div>
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
              来源：{{ formatProviderSource(modelConfigTest.roles?.[entry.key]?.source ?? 'inherit') }}
            </div>
          </div>
        </div>

        <div v-if="modelConfigNotice" class="mt-4 rounded-btn border border-state-active/25 bg-state-active/10 px-3 py-2 text-[12px] text-state-active">
          {{ modelConfigNotice }}
        </div>
        <div v-if="modelConfigError" class="mt-3 rounded-btn border border-state-invalidated/25 bg-state-invalidated/10 px-3 py-2 text-[12px] text-state-invalidated">
          {{ modelConfigError }}
        </div>
      </PCard>
    </div>
  </div>
</template>
