/**
 * useDashboardData.ts
 * 全局数据获取：stats、petState、nitStatus、背景氛围灯
 */
import { ref, computed, type Ref } from 'vue'
import { API_BASE } from '@/config'
import { fetchWithTimeout } from './useDashboard'

import type { Stats, PetState, NitStatus, Agent } from './types'

interface UseDashboardDataOptions {
  activeAgent: Ref<Agent | null>
  isBackendOnline: Ref<boolean>
  isGlobalRefreshing: Ref<boolean>
  currentTab: Ref<string>
}

const MOOD_COLORS: Record<string, { primary: string; secondary: string }> = {
  happy: { primary: 'rgba(252, 165, 165, 0.2)', secondary: 'rgba(253, 224, 71, 0.15)' },
  sad: { primary: 'rgba(96, 165, 250, 0.2)', secondary: 'rgba(165, 180, 252, 0.15)' },
  angry: { primary: 'rgba(244, 63, 94, 0.2)', secondary: 'rgba(253, 186, 116, 0.15)' },
  surprised: { primary: 'rgba(192, 132, 252, 0.2)', secondary: 'rgba(240, 171, 252, 0.15)' },
  neutral: { primary: 'rgba(125, 211, 252, 0.2)', secondary: 'rgba(153, 246, 228, 0.15)' }
}

export function useDashboardData({ activeAgent, isBackendOnline }: UseDashboardDataOptions) {
  const stats = ref<Stats>({ total_memories: 0, total_logs: 0, total_tasks: 0 })
  const petState = ref<PetState>({})
  const nitStatus = ref<NitStatus | null>(null)

  // 背景氛围灯
  const ambientLightStyle = computed<Record<string, string>>(() => {
    const mood = (petState.value?.mood as string) ?? 'neutral'
    const color = MOOD_COLORS[mood] ?? MOOD_COLORS.neutral
    return {
      background: `radial-gradient(circle at 20% 30%, ${color.primary} 0%, transparent 70%),
                  radial-gradient(circle at 80% 70%, ${color.secondary} 0%, transparent 70%)`,
      filter: 'blur(100px)',
      opacity: '0.8'
    }
  })

  // 使用函数属性避免重复请求
  const fetchPetStateState = { isPolling: false }
  const fetchNitStatusState = { isLoading: false }

  const fetchStats = async (): Promise<void> => {
    try {
      let url = `${API_BASE}/system/stats/overview`

      if (activeAgent.value) url += `?agent_id=${activeAgent.value.id}`
      const res = await fetchWithTimeout(url, {}, 2000)
      stats.value = (await res.json()) as Stats
    } catch {
      console.error('获取统计信息失败')
    }
  }

  const fetchPetState = async (): Promise<void> => {
    if (fetchPetStateState.isPolling) return
    try {
      if (!isBackendOnline.value) return
      fetchPetStateState.isPolling = true
      let url = `${API_BASE}/pet/state`
      if (activeAgent.value) url += `?agent_id=${activeAgent.value.id}`
      const res = await fetchWithTimeout(url, {}, 2000)
      if (res.ok) petState.value = (await res.json()) as PetState
    } catch {
      // 静默失败
    } finally {
      fetchPetStateState.isPolling = false
    }
  }

  const fetchNitStatus = async (): Promise<void> => {
    if (fetchNitStatusState.isLoading) return
    fetchNitStatusState.isLoading = true
    try {
      const res = await fetchWithTimeout(`${API_BASE}/maintenance/nit/status`, {}, 2000)

      nitStatus.value = (await res.json()) as NitStatus
    } catch {
      console.error('NIT 状态获取错误')
    } finally {
      fetchNitStatusState.isLoading = false
    }
  }

  return {
    stats,
    petState,
    nitStatus,
    ambientLightStyle,
    fetchStats,
    fetchPetState,
    fetchNitStatus
  }
}
