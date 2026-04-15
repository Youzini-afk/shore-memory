/**
 * useAgentConfig.ts
 * Agent 管理、功能开关（轻量/AuraVision/Companion）、记忆配置
 */
import { ref } from 'vue'
import { invoke } from '@/utils/ipcAdapter'
import { API_BASE } from '@/config'
import { fetchJson, fetchWithTimeout } from './useDashboard'

import type { Agent, NapCatStatus, MemoryConfig } from './types'

export function useAgentConfig() {
  // --- Agent 状态 ---
  const availableAgents = ref<Agent[]>([])
  const activeAgent = ref<Agent | null>(null)
  const isSwitchingAgent = ref<boolean>(false)

  const fetchAgents = async (): Promise<void> => {
    try {
      const agents = await fetchJson<Agent[]>(`${API_BASE}/agents`, {}, 2000)
      availableAgents.value = agents.map((a) => ({
        ...a,
        avatarUrl: a.avatar
          ? a.avatar.startsWith('http')
            ? a.avatar
            : `${API_BASE.replace('/api', '')}${a.avatar}`
          : null
      }))
      const active = availableAgents.value.find((a) => a.is_active)
      if (active) activeAgent.value = active
    } catch (e) {
      console.error('获取助手列表失败:', e)
    }
  }

  const switchAgent = async (agentId: string): Promise<void> => {
    if (isSwitchingAgent.value || agentId === activeAgent.value?.id) return
    isSwitchingAgent.value = true
    try {
      const res = await fetchWithTimeout(
        `${API_BASE}/agents/active`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ agent_id: agentId })
        },
        5000
      )
      if (!res.ok) throw new Error('Failed to switch agent')
      await fetchAgents()
      window.$notify(`已切换到角色: ${activeAgent.value?.name}`, 'success')
      const enabled = availableAgents.value.filter((a) => a.is_enabled).map((a) => a.id)
      invoke('save_global_launch_config', { enabledAgents: enabled, activeAgent: agentId }).catch(
        (e) => console.error('保存启动配置失败:', e)
      )
    } catch (e) {
      window.$notify((e as Error).message, 'error')
    } finally {
      isSwitchingAgent.value = false
    }
  }

  // --- NapCat 状态 ---
  const napCatStatus = ref<NapCatStatus>({
    ws_connected: false,
    api_responsive: false,
    latency_ms: -1,
    disabled: false
  })

  // --- 功能开关 ---
  const isCompanionEnabled = ref<boolean>(false)
  const isTogglingCompanion = ref<boolean>(false)
  const isSocialEnabled = ref<boolean>(false)
  const isLightweightEnabled = ref<boolean>(false)
  const isTogglingLightweight = ref<boolean>(false)
  const isAuraVisionEnabled = ref<boolean>(false)
  const isTogglingAuraVision = ref<boolean>(false)

  const fetchCompanionStatus = async (): Promise<void> => {
    try {
      const data = await fetchJson<{ enabled: boolean }>(`${API_BASE}/companion/status`, {}, 2000)
      isCompanionEnabled.value = data.enabled
    } catch (e) {
      console.error('Failed to fetch companion status', e)
    }
  }

  const toggleCompanion = async (val: boolean): Promise<void> => {
    try {
      isTogglingCompanion.value = true
      const data = await fetchJson<{ enabled: boolean }>(
        `${API_BASE}/companion/toggle`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ enabled: val })
        },
        5000
      )
      isCompanionEnabled.value = data.enabled
      window.$notify(data.enabled ? '已开启陪伴模式' : '已关闭陪伴模式', 'success')
    } catch {
      isCompanionEnabled.value = !val
    } finally {
      isTogglingCompanion.value = false
    }
  }

  const fetchSocialStatus = async (): Promise<void> => {
    try {
      const data = await fetchJson<{ enabled: boolean }>(`${API_BASE}/social/status`, {}, 2000)
      isSocialEnabled.value = data.enabled
    } catch {
      console.error('Failed to fetch social status')
    }
  }

  const fetchLightweightStatus = async (): Promise<void> => {
    try {
      const data = await fetchJson<{ enabled: boolean }>(`${API_BASE}/configs/lightweight_mode`, {}, 2000)
      isLightweightEnabled.value = data.enabled
    } catch {
      console.error('Failed to fetch lightweight status')
    }
  }

  const toggleLightweight = async (val: boolean): Promise<void> => {
    try {
      isTogglingLightweight.value = true
      const data = await fetchJson<{ enabled: boolean }>(
        `${API_BASE}/configs/lightweight_mode`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ enabled: val })
        },
        5000
      )
      isLightweightEnabled.value = data.enabled
      window.$notify(data.enabled ? '已开启轻量聊天模式' : '已关闭轻量聊天模式', 'success')
    } catch {
      isLightweightEnabled.value = !val
    } finally {
      isTogglingLightweight.value = false
    }
  }

  const fetchAuraVisionStatus = async (): Promise<void> => {
    try {
      const data = await fetchJson<{ enabled: boolean }>(`${API_BASE}/configs/aura_vision`, {}, 3000)
      isAuraVisionEnabled.value = data.enabled
    } catch (e) {
      console.error('Failed to fetch AuraVision status', e)
    }
  }

  const toggleAuraVision = async (val: boolean): Promise<void> => {
    try {
      isTogglingAuraVision.value = true
      const data = await fetchJson<{ enabled: boolean }>(
        `${API_BASE}/configs/aura_vision`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ enabled: val })
        },
        5000
      )
      isAuraVisionEnabled.value = data.enabled
      window.$notify(
        data.enabled ? '已开启主动视觉感应 (AuraVision)' : '已关闭主动视觉感应 (AuraVision)',
        'success'
      )
    } catch {
      isAuraVisionEnabled.value = !val
    } finally {
      isTogglingAuraVision.value = false
    }
  }

  // --- 记忆系统配置 ---
  const activeMemoryTab = ref<string>('desktop')
  const isSavingMemoryConfig = ref<boolean>(false)
  const memoryConfig = ref<MemoryConfig>({
    modes: {
      desktop: { context_limit: 20, rag_limit: 10 },
      work: { context_limit: 50, rag_limit: 15 },
      social: {
        context_limit: 100,
        rag_limit: 10,
        advanced: { image_limit: 2, cross_context_users: 3, cross_context_history: 10 }
      }
    }
  })

  const fetchMemoryConfig = async (): Promise<void> => {
    try {
      const data = await fetchJson<MemoryConfig>(`${API_BASE}/configs/memory`, {}, 3000)
      if (data?.modes) memoryConfig.value = data
    } catch (e) {
      console.error('Failed to fetch memory config:', e)
    }
  }

  const saveMemoryConfig = async (): Promise<void> => {
    isSavingMemoryConfig.value = true
    try {
      await fetchWithTimeout(
        `${API_BASE}/configs/memory`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ config: memoryConfig.value }),
          throwOnError: true
        },
        5000
      )
      window.$notify('记忆配置已保存', 'success')
    } catch (e) {
      window.$notify('保存失败: ' + (e as Error).message, 'error')
    } finally {
      isSavingMemoryConfig.value = false
    }
  }

  return {
    availableAgents,
    activeAgent,
    isSwitchingAgent,
    fetchAgents,
    switchAgent,
    napCatStatus,
    isCompanionEnabled,
    isTogglingCompanion,
    toggleCompanion,
    fetchCompanionStatus,
    isSocialEnabled,
    fetchSocialStatus,
    isLightweightEnabled,
    isTogglingLightweight,
    toggleLightweight,
    fetchLightweightStatus,
    isAuraVisionEnabled,
    isTogglingAuraVision,
    toggleAuraVision,
    fetchAuraVisionStatus,
    activeMemoryTab,
    isSavingMemoryConfig,
    memoryConfig,
    fetchMemoryConfig,
    saveMemoryConfig
  }
}
