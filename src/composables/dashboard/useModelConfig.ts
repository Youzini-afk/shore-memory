/**
 * useModelConfig.ts
 * 模型配置、全局配置、MCP、向量/重排模型配置
 */
import { ref, type Ref, type ShallowRef } from 'vue'
import { API_BASE } from '@/config'
import { fetchWithTimeout, formatLLMError } from './useDashboard'

import type {
  Model,
  Mcp,
  GlobalConfig,
  UserSettings,
  ProviderOption,
  McpTypeOption,
  Memory,
  OpenConfirmFn
} from './types'

export const providerOptions: ProviderOption[] = [
  { label: 'OpenAI (兼容)', value: 'openai' },
  { label: 'Gemini (原生)', value: 'gemini' },
  { label: 'Claude (Anthropic)', value: 'anthropic' },
  { label: 'SiliconFlow (硅基流动)', value: 'siliconflow' },
  { label: 'DeepSeek (深度求索)', value: 'deepseek' },
  { label: 'Moonshot (Kimi)', value: 'moonshot' },
  { label: 'DashScope (阿里百炼)', value: 'dashscope' },
  { label: 'Volcengine (火山引擎)', value: 'volcengine' },
  { label: 'Groq', value: 'groq' },
  { label: 'Zhipu (智谱GLM)', value: 'zhipu' },
  { label: 'MiniMax', value: 'minimax' },
  { label: 'Mistral', value: 'mistral' },
  { label: '01.AI (零一万物)', value: 'yi' },
  { label: 'xAI (Grok)', value: 'xai' },
  { label: 'StepFun (阶跃星辰)', value: 'stepfun' },
  { label: 'Hunyuan (腾讯混元)', value: 'hunyuan' }
]

export const mcpTypeOptions: McpTypeOption[] = [
  { label: 'Stdio (本地)', value: 'stdio' },
  { label: 'SSE (远程)', value: 'sse' }
]

export const providerDefaults: Record<string, string> = {
  siliconflow: 'https://api.siliconflow.cn/v1',
  deepseek: 'https://api.deepseek.com',
  moonshot: 'https://api.moonshot.cn/v1',
  dashscope: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
  volcengine: 'https://ark.cn-beijing.volces.com/api/v3',
  groq: 'https://api.groq.com/openai/v1',
  zhipu: 'https://open.bigmodel.cn/api/paas/v4',
  minimax: 'https://api.minimax.chat/v1',
  mistral: 'https://api.mistral.ai/v1',
  yi: 'https://api.lingyiwanwu.com/v1',
  xai: 'https://api.x.ai/v1',
  stepfun: 'https://api.stepfun.com/v1',
  hunyuan: 'https://api.hunyuan.cloud.tencent.com/v1'
}

// 内部状态标记（避免 ref 上手动附加属性）
const fetchModelsState = { isLoading: false }
const fetchMcpsState = { isLoading: false }
const deleteModelState = { isLoading: false }
const deleteMcpState = { isLoading: false }

interface UseModelConfigOptions {
  memories: ShallowRef<Memory[]>
  isSaving: Ref<boolean>
  openConfirm: OpenConfirmFn
}

interface ApiConfig {
  global_llm_api_key?: string
  global_llm_api_base?: string
  current_model_id?: string | number
  scorer_model_id?: string | number
  reflection_model_id?: string | number
  aux_model_id?: string | number
  embedding_provider?: string
  embedding_model_id?: string
  embedding_api_base?: string
  embedding_api_key?: string
  reranker_enabled?: string
  reranker_provider?: string
  reranker_model_id?: string
  reranker_api_base?: string
  reranker_api_key?: string
  embedding_dimension?: string
  owner_name?: string
  user_persona?: string
  owner_qq?: string
  current_session_id?: string
}

export function useModelConfig({ memories, isSaving, openConfirm }: UseModelConfigOptions) {
  // --- 全局配置 ---
  const globalConfig = ref<GlobalConfig>({
    global_llm_api_key: '',
    global_llm_api_base: '',
    provider: ''
  })
  const showGlobalSettings = ref<boolean>(false)
  const currentModelTab = ref<'llm' | 'vector'>('llm')

  // --- 模型列表 ---
  const models = ref<Model[]>([])
  const showModelEditor = ref<boolean>(false)
  const remoteModels = ref<string[]>([])
  const isFetchingRemote = ref<boolean>(false)
  const currentEditingModel = ref<Partial<Model>>({})
  const currentActiveModelId = ref<number | null>(null)
  const secretaryModelId = ref<number | null>(null)
  const reflectionModelId = ref<number | null>(null)
  const auxModelId = ref<number | null>(null)

  // --- 向量模型 ---
  const embeddingProvider = ref<string>('local')
  const embeddingModelId = ref<string>('')
  const embeddingApiBase = ref<string>('')
  const embeddingApiKey = ref<string>('')
  const rerankerEnabled = ref<boolean>(true)
  const rerankerProvider = ref<string>('api')
  const rerankerModelId = ref<string>('')
  const rerankerApiBase = ref<string>('')
  const rerankerApiKey = ref<string>('')
  const embeddingDimension = ref<string>('512')
  const isReindexing = ref<boolean>(false)
  const availableEmbeddingModels = ref<string[]>([])
  const isFetchingEmbeddingModels = ref<boolean>(false)
  const availableRerankerModels = ref<string[]>([])
  const isFetchingRerankerModels = ref<boolean>(false)

  // --- MCP 配置 ---
  const mcps = ref<Mcp[]>([])
  const showMcpEditor = ref<boolean>(false)
  const currentEditingMcp = ref<Partial<Mcp>>({})

  // --- 用户设定 ---
  const userSettings = ref<UserSettings>({
    owner_name: '主人',
    user_persona: '未设定',
    owner_qq: ''
  })

  // ─── 获取配置 ─────────────────────────────────────────────────────────────
  const fetchConfig = async (opts?: {
    selectedSessionId?: Ref<string>
    lastSyncedSessionId?: Ref<string | null>
  }): Promise<void> => {
    try {
      const res = await fetchWithTimeout(
        `${API_BASE}/configs`,
        { silent: true } as RequestInit,
        5000
      )
      if (!res.ok) throw new Error(`Status ${res.status}: ${res.statusText}`)
      const data = (await res.json()) as ApiConfig

      globalConfig.value.global_llm_api_key = data.global_llm_api_key ?? ''
      globalConfig.value.global_llm_api_base = data.global_llm_api_base ?? 'https://api.openai.com'

      const foundProvider = Object.keys(providerDefaults).find(
        (key) => providerDefaults[key] === globalConfig.value.global_llm_api_base
      )
      if (foundProvider) globalConfig.value.provider = foundProvider
      else if (globalConfig.value.global_llm_api_base.includes('api.openai.com'))
        globalConfig.value.provider = 'openai'
      else globalConfig.value.provider = ''

      currentActiveModelId.value = data.current_model_id
        ? parseInt(String(data.current_model_id))
        : null
      secretaryModelId.value = data.scorer_model_id ? parseInt(String(data.scorer_model_id)) : null
      reflectionModelId.value = data.reflection_model_id
        ? parseInt(String(data.reflection_model_id))
        : null
      auxModelId.value = data.aux_model_id ? parseInt(String(data.aux_model_id)) : null

      embeddingProvider.value = data.embedding_provider ?? 'local'
      embeddingModelId.value = data.embedding_model_id ?? ''
      embeddingApiBase.value = data.embedding_api_base ?? ''
      embeddingApiKey.value = data.embedding_api_key ?? ''
      rerankerEnabled.value = data.reranker_enabled !== 'false'
      rerankerProvider.value = 'api' // 强制转为 api
      rerankerModelId.value = data.reranker_model_id ?? ''
      rerankerApiBase.value = data.reranker_api_base ?? ''
      rerankerApiKey.value = data.reranker_api_key ?? ''
      embeddingDimension.value = data.embedding_dimension ?? '512'

      userSettings.value.owner_name = data.owner_name ?? '主人'
      userSettings.value.user_persona = data.user_persona ?? '未设定'
      userSettings.value.owner_qq = data.owner_qq ?? ''

      if (opts?.selectedSessionId && opts?.lastSyncedSessionId) {
        if (data.current_session_id && data.current_session_id !== 'default') {
          if (data.current_session_id !== opts.lastSyncedSessionId.value) {
            opts.selectedSessionId.value = data.current_session_id
            opts.lastSyncedSessionId.value = data.current_session_id
          }
        } else {
          opts.lastSyncedSessionId.value = null
        }
      }
    } catch (e) {
      console.error(e)
      window.$notify('获取配置失败: ' + formatLLMError(e), 'error')
    }
  }

  const fetchModels = async (): Promise<void> => {
    if (fetchModelsState.isLoading) return
    fetchModelsState.isLoading = true
    try {
      const res = await fetchWithTimeout(
        `${API_BASE}/models`,
        { silent: true } as RequestInit,
        5000
      )
      if (!res.ok) throw new Error(`Status ${res.status}: ${res.statusText}`)
      models.value = (await res.json()) as Model[]
    } catch (e) {
      console.error(e)
      window.$notify('获取模型列表失败: ' + formatLLMError(e), 'error')
    } finally {
      fetchModelsState.isLoading = false
    }
  }

  // ─── 模型角色设置 ─────────────────────────────────────────────────────────
  const _setModelRole = async (
    key: string,
    id: number,
    idRef: Ref<number | null>,
    successMsg: string,
    failMsg: string
  ): Promise<void> => {
    const isCurrentlyActive = idRef.value === id
    const targetId = isCurrentlyActive ? '' : String(id)
    try {
      const res = await fetchWithTimeout(
        `${API_BASE}/configs`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ [key]: targetId }),
          silent: true
        } as RequestInit,
        5000
      )
      if (!res.ok) throw new Error(isCurrentlyActive ? `取消${failMsg}失败` : `设置${failMsg}失败`)
      idRef.value = isCurrentlyActive ? null : id
      window.$notify(isCurrentlyActive ? `${successMsg}已取消` : `${successMsg}已更新`, 'success')
    } catch (e) {
      window.$notify(formatLLMError(e), 'error')
    }
  }

  const setActiveModel = (id: number) =>
    _setModelRole('current_model_id', id, currentActiveModelId, '主模型', '主模型')
  const setSecretaryModel = (id: number) =>
    _setModelRole('scorer_model_id', id, secretaryModelId, '秘书模型', '秘书模型')
  const setReflectionModel = (id: number) =>
    _setModelRole('reflection_model_id', id, reflectionModelId, '反思模型', '反思模型')
  const setAuxModel = (id: number) =>
    _setModelRole('aux_model_id', id, auxModelId, '辅助模型', '辅助模型')

  const openGlobalSettings = (): void => {
    showGlobalSettings.value = true
  }

  const saveGlobalSettings = async (): Promise<void> => {
    if (isSaving.value) return
    try {
      isSaving.value = true
      const res = await fetchWithTimeout(
        `${API_BASE}/configs`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(globalConfig.value),
          silent: true
        } as RequestInit,
        5000
      )
      if (!res.ok) throw new Error('保存配置失败')
      showGlobalSettings.value = false
      window.$notify('全局配置已保存', 'success')
      await fetchConfig()
    } catch (e) {
      window.$notify(formatLLMError(e), 'error')
    } finally {
      isSaving.value = false
    }
  }

  const openModelEditor = (model?: Model): void => {
    remoteModels.value = []
    if (model) {
      currentEditingModel.value = {
        enable_vision: false,
        enable_voice: false,
        enable_video: false,
        stream: true,
        temperature: 0.7,
        provider: 'openai',
        ...JSON.parse(JSON.stringify(model))
      }
    } else {
      currentEditingModel.value = {
        name: '',
        model_id: '',
        provider_type: 'custom',
        provider: 'openai',
        api_key: '',
        api_base: '',
        temperature: 0.7,
        stream: true,
        enable_vision: false,
        enable_voice: false,
        enable_video: false
      }
    }
    showModelEditor.value = true
  }

  const handleProviderChange = (val: string): void => {
    if (providerDefaults[val]) {
      currentEditingModel.value.api_base = providerDefaults[val]
    } else if (val === 'openai' && !currentEditingModel.value.api_base) {
      currentEditingModel.value.api_base = 'https://api.openai.com'
    }
  }

  const handleGlobalProviderChange = (val: string): void => {
    if (val === 'deepseek') {
      globalConfig.value.global_llm_api_base = providerDefaults[val]
    } else if (
      providerDefaults[val] &&
      (!globalConfig.value.global_llm_api_base ||
        globalConfig.value.global_llm_api_base.includes('api.openai.com'))
    ) {
      globalConfig.value.global_llm_api_base = providerDefaults[val]
    } else if (val === 'openai' && !globalConfig.value.global_llm_api_base) {
      globalConfig.value.global_llm_api_base = 'https://api.openai.com'
    }
  }

  const fetchRemoteModels = async (): Promise<void> => {
    if (isFetchingRemote.value) return
    try {
      isFetchingRemote.value = true
      let apiKey = '',
        apiBase = ''
      if (currentEditingModel.value.provider_type === 'global') {
        apiKey = globalConfig.value.global_llm_api_key
        apiBase = globalConfig.value.global_llm_api_base
      } else {
        apiKey = currentEditingModel.value.api_key ?? ''
        apiBase = currentEditingModel.value.api_base ?? ''
      }
      const res = await fetchWithTimeout(
        `${API_BASE}/models/remote`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            api_key: apiKey,
            api_base: apiBase,
            provider: currentEditingModel.value.provider ?? 'openai'
          }),
          silent: true
        } as RequestInit,
        10000
      )
      if (!res.ok) {
        const errData = (await res.json().catch(() => ({}))) as {
          detail?: string
          message?: string
        }
        throw new Error(errData.detail ?? errData.message ?? `Status ${res.status}`)
      }
      const data = (await res.json()) as { models?: string[] }
      if (data.models?.length) {
        remoteModels.value = data.models
        window.$notify(`获取到 ${data.models.length} 个模型`, 'success')
      } else {
        window.$notify('未找到模型或 API 不支持', 'warning')
      }
    } catch (e) {
      window.$notify(formatLLMError(e), 'error')
    } finally {
      isFetchingRemote.value = false
    }
  }

  const saveModel = async (): Promise<void> => {
    if (isSaving.value) return
    try {
      isSaving.value = true
      const model = currentEditingModel.value
      const url = model.id ? `${API_BASE}/models/${model.id}` : `${API_BASE}/models`
      const method = model.id ? 'PUT' : 'POST'
      const res = await fetchWithTimeout(
        url,
        {
          method,
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(model),
          silent: true
        } as RequestInit,
        5000
      )
      if (!res.ok) throw new Error('保存失败')
      showModelEditor.value = false
      await fetchModels()
      window.$notify('模型已保存', 'success')
    } catch (e) {
      window.$notify(formatLLMError(e), 'error')
    } finally {
      isSaving.value = false
    }
  }

  const deleteModel = async (id: number): Promise<void> => {
    if (!id || deleteModelState.isLoading) {
      if (!id) window.$notify('无效的模型ID', 'error')
      return
    }
    try {
      await openConfirm('警告', '确定删除此模型配置吗？', { type: 'warning' })
      deleteModelState.isLoading = true
      const res = await fetchWithTimeout(`${API_BASE}/models/${id}`, { method: 'DELETE' }, 5000)
      if (!res.ok) {
        const err = (await res.json()) as { message?: string }
        throw new Error(err.message ?? '删除失败')
      }
      await fetchModels()
      window.$notify('已删除', 'success')
    } catch (e) {
      if ((e as Error).message !== 'User cancelled') {
        console.error(e)
        window.$notify('系统错误: ' + ((e as Error).message ?? '未知错误'), 'error')
      }
    } finally {
      deleteModelState.isLoading = false
    }
  }

  // ─── 向量模型 ─────────────────────────────────────────────────────────────
  const handleEmbeddingProviderChange = (val: string): void => {
    embeddingDimension.value = val === 'local' ? '512' : '1536'
  }

  const fetchRemoteVectorModels = async (type: 'embedding' | 'reranker'): Promise<void> => {
    const isEmb = type === 'embedding'
    const provider = isEmb ? embeddingProvider.value : rerankerProvider.value
    if (provider === 'local') return
    const apiBase =
      (isEmb ? embeddingApiBase.value : rerankerApiBase.value) ||
      globalConfig.value.global_llm_api_base
    const apiKey =
      (isEmb ? embeddingApiKey.value : rerankerApiKey.value) ||
      globalConfig.value.global_llm_api_key
    if (!apiKey) {
      window.$notify('请先配置 API Key 喵~ 🔑', 'warning')
      return
    }
    if (isEmb) isFetchingEmbeddingModels.value = true
    else isFetchingRerankerModels.value = true
    try {
      const res = await fetch(`${API_BASE}/models/remote`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ api_key: apiKey, api_base: apiBase, provider: 'openai' })
      })
      if (res.ok) {
        const data = (await res.json()) as { models?: string[] }
        const modelList = data.models ?? []
        if (isEmb) availableEmbeddingModels.value = modelList
        else availableRerankerModels.value = modelList
        if (!modelList.length) window.$notify('未获取到模型列表，请检查配置喵~ 😿', 'warning')
        else window.$notify(`已获取 ${modelList.length} 个可用模型喵！✨`, 'success')
      } else throw new Error('获取失败')
    } catch (e) {
      window.$notify('获取远程模型失败: ' + (e as Error).message, 'error')
    } finally {
      if (isEmb) isFetchingEmbeddingModels.value = false
      else isFetchingRerankerModels.value = false
    }
  }

  const triggerReindex = async (): Promise<void> => {
    if (isReindexing.value) return
    try {
      isReindexing.value = true
      const res = await fetch(`${API_BASE}/maintenance/memory/reindex`, { method: 'POST' })

      if (res.ok) window.$notify('重索引任务已在后台启动喵~ ✨', 'success')
      else throw new Error('启动失败')
    } catch (e) {
      window.$notify('重索引失败: ' + (e as Error).message, 'error')
    } finally {
      isReindexing.value = false
    }
  }

  const saveVectorConfig = async (): Promise<void> => {
    if (isSaving.value) return
    const needsReindex = memories.value.length > 0
    if (needsReindex) {
      const { action } = await openConfirm(
        '模型切换确认',
        '<div class="text-slate-600 mb-2">检测到您正在切换向量模型，且当前已有存储的记忆。</div><div class="text-amber-600 font-bold">由于不同模型的向量维度不兼容，必须重建索引才能继续使用记忆系统。</div>',
        { type: 'warning' }
      )
      if (action !== 'confirm') return
    }
    try {
      isSaving.value = true
      await fetchWithTimeout(
        `${API_BASE}/configs`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            embedding_provider: embeddingProvider.value,
            embedding_model_id: embeddingModelId.value,
            embedding_api_base: embeddingApiBase.value,
            embedding_api_key: embeddingApiKey.value,
            reranker_enabled: rerankerEnabled.value ? 'true' : 'false',
            reranker_provider: rerankerEnabled.value ? rerankerProvider.value : '',
            reranker_model_id: rerankerEnabled.value ? rerankerModelId.value : '',
            reranker_api_base: rerankerEnabled.value ? rerankerApiBase.value : '',
            reranker_api_key: rerankerEnabled.value ? rerankerApiKey.value : '',
            embedding_dimension: embeddingDimension.value,
            global_llm_api_key: globalConfig.value.global_llm_api_key,
            global_llm_api_base: globalConfig.value.global_llm_api_base
          })
        },
        5000
      )
      window.$notify('向量模型配置已更新', 'success')
      if (needsReindex) triggerReindex()
      await fetchConfig()
    } catch (e) {
      window.$notify('保存失败: ' + (e as Error).message, 'error')
    } finally {
      isSaving.value = false
    }
  }

  // ─── MCP 管理 ─────────────────────────────────────────────────────────────
  const fetchMcps = async (): Promise<void> => {
    if (fetchMcpsState.isLoading) return
    fetchMcpsState.isLoading = true
    try {
      const res = await fetchWithTimeout(`${API_BASE}/mcp`, {}, 5000)
      mcps.value = (await res.json()) as Mcp[]
    } catch {
      console.error('Failed to fetch MCPs')
    } finally {
      fetchMcpsState.isLoading = false
    }
  }

  const openMcpEditor = (mcp?: Mcp): void => {
    currentEditingMcp.value = mcp
      ? (JSON.parse(JSON.stringify(mcp)) as Mcp)
      : { name: '', type: 'stdio', command: '', args: '[]', env: '{}', url: '', enabled: true }
    showMcpEditor.value = true
  }

  const saveMcp = async (): Promise<void> => {
    if (isSaving.value) return
    try {
      isSaving.value = true
      const mcp = currentEditingMcp.value
      const url = mcp.id ? `${API_BASE}/mcp/${mcp.id}` : `${API_BASE}/mcp`
      if (mcp.type === 'stdio') {
        JSON.parse(mcp.args ?? '[]')
        JSON.parse(mcp.env ?? '{}')
      }
      const res = await fetchWithTimeout(
        url,
        {
          method: mcp.id ? 'PUT' : 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(mcp)
        },
        5000
      )
      if (!res.ok) throw new Error('保存失败')
      showMcpEditor.value = false
      await fetchMcps()
      window.$notify('MCP 配置已保存', 'success')
    } catch (e) {
      window.$notify((e as Error).message, 'error')
    } finally {
      isSaving.value = false
    }
  }

  const deleteMcp = async (id: number): Promise<void> => {
    if (!id || deleteMcpState.isLoading) {
      if (!id) window.$notify('无效的MCP ID', 'error')
      return
    }
    try {
      await openConfirm('警告', '确定删除此 MCP 配置吗？', { type: 'warning' })
      deleteMcpState.isLoading = true
      const res = await fetchWithTimeout(`${API_BASE}/mcp/${id}`, { method: 'DELETE' }, 5000)
      if (!res.ok) {
        const err = (await res.json()) as { message?: string }
        throw new Error(err.message ?? '删除失败')
      }
      await fetchMcps()
      window.$notify('已删除', 'success')
    } catch (e) {
      if ((e as Error).message !== 'User cancelled') {
        console.error(e)
        window.$notify('系统错误: ' + ((e as Error).message ?? '未知错误'), 'error')
      }
    } finally {
      deleteMcpState.isLoading = false
    }
  }

  const toggleMcpEnabled = async (mcp: Mcp): Promise<void> => {
    try {
      const res = await fetchWithTimeout(
        `${API_BASE}/mcp/${mcp.id}`,
        {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ ...mcp, enabled: mcp.enabled })
        },
        5000
      )
      if (!res.ok) throw new Error('更新失败')
      await fetchMcps()
    } catch (e) {
      window.$notify((e as Error).message, 'error')
      mcp.enabled = !mcp.enabled
    }
  }

  // ─── 用户设定 / 系统重置 ──────────────────────────────────────────────────
  const saveUserSettings = async (): Promise<void> => {
    if (isSaving.value) return
    try {
      isSaving.value = true
      await fetchWithTimeout(
        `${API_BASE}/configs`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            owner_name: userSettings.value.owner_name,
            user_persona: userSettings.value.user_persona,
            owner_qq: userSettings.value.owner_qq
          })
        },
        5000
      )
      window.$notify('用户设定已保存', 'success')
      await fetchConfig()
    } catch (e) {
      window.$notify('保存失败: ' + (e as Error).message, 'error')
    } finally {
      isSaving.value = false
    }
  }

  const handleSystemReset = async (
    activeAgent: Ref<{ name?: string } | null>,
    fetchAllData: ((silent?: boolean) => Promise<void>) | undefined,
    currentTab: Ref<string>
  ): Promise<void> => {
    if (isSaving.value) return
    try {
      const { value, action } = await openConfirm(
        '终极警告',
        '<div class="danger-main-text">主人，真的要让 ' +
          (activeAgent.value?.name ?? 'Pero') +
          ' 忘掉你吗？o(╥﹏╥)o</div><div class="danger-sub-text">（此操作将执行深度清理，如需继续，请在文本框中输入"我们还会再见的..."）</div>',
        {
          type: 'error',
          isPrompt: true,
          inputValue: '',
          inputPlaceholder: '请输入：我们还会再见的...'
        }
      )
      if (action === 'confirm') {
        if (String(value ?? '').trim() !== '我们还会再见的...') {
          window.$notify('输入不匹配，已取消', 'error')
          return
        }
        isSaving.value = true
        const res = await fetchWithTimeout(`${API_BASE}/system/reset`, { method: 'POST' }, 10000)
        if (res.ok) {
          window.$notify('系统已恢复出厂设置', 'success')
          await fetchAllData?.(true)
          currentTab.value = 'overview'
        } else {
          const err = (await res.json()) as { detail?: string }
          throw new Error(err.detail ?? '重置失败')
        }
      }
    } catch (e) {
      if ((e as Error).message !== 'User cancelled') {
        window.$notify((e as Error).message ?? '重置过程中发生错误', 'error')
      }
    } finally {
      isSaving.value = false
    }
  }

  return {
    globalConfig,
    showGlobalSettings,
    currentModelTab,
    fetchConfig,
    openGlobalSettings,
    saveGlobalSettings,
    handleGlobalProviderChange,
    models,
    showModelEditor,
    remoteModels,
    isFetchingRemote,
    currentEditingModel,
    currentActiveModelId,
    secretaryModelId,
    reflectionModelId,
    auxModelId,
    fetchModels,
    openModelEditor,
    handleProviderChange,
    fetchRemoteModels,
    saveModel,
    deleteModel,
    setActiveModel,
    setSecretaryModel,
    setReflectionModel,
    setAuxModel,
    embeddingProvider,
    embeddingModelId,
    embeddingApiBase,
    embeddingApiKey,
    rerankerEnabled,
    rerankerProvider,
    rerankerModelId,
    rerankerApiBase,
    rerankerApiKey,
    embeddingDimension,
    isReindexing,
    availableEmbeddingModels,
    isFetchingEmbeddingModels,
    availableRerankerModels,
    isFetchingRerankerModels,
    handleEmbeddingProviderChange,
    fetchRemoteVectorModels,
    saveVectorConfig,
    triggerReindex,
    mcps,
    showMcpEditor,
    currentEditingMcp,
    fetchMcps,
    openMcpEditor,
    saveMcp,
    deleteMcp,
    toggleMcpEnabled,
    userSettings,
    saveUserSettings,
    handleSystemReset
  }
}
