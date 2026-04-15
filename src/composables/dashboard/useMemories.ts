/**
 * useMemories.ts
 * 核心记忆系统：获取、过滤、删除、图谱、梦境/维护/扫描
 */
import { ref, shallowRef, computed, nextTick, type Ref } from 'vue'
import * as echarts from 'echarts'
import { API_BASE } from '@/config'
import { fetchJson, fetchWithTimeout } from './useDashboard'

import type { Memory, Agent, MemoryGraphData, TagCloudItem, OpenConfirmFn } from './types'

interface UseMemoriesOptions {
  activeAgent: Ref<Agent | null>
  currentTab: Ref<string>
  openConfirm: OpenConfirmFn
}

interface FetchWithLoading {
  isLoading: boolean
  lastRequestId: symbol | null
}

export function useMemories({ activeAgent, currentTab, openConfirm }: UseMemoriesOptions) {
  const memories = shallowRef<Memory[]>([])
  const tagCloud = ref<Record<string, number> | TagCloudItem[]>({})
  const memoryFilterTags = ref<string[]>([])
  const memoryFilterDate = ref<string | null>(null)
  const memoryFilterType = ref<string>('')
  const memoryViewMode = ref<'list' | 'graph'>('list')
  const memoryGraphData = shallowRef<MemoryGraphData>({ nodes: [], edges: [] })
  const isLoadingGraph = ref<boolean>(false)

  // ECharts 图谱实例
  const graphRef = ref<HTMLDivElement | null>(null)
  let chartInstance: echarts.ECharts | null = null
  let resizeHandler: (() => void) | null = null

  // 操作状态
  const isClearingEdges = ref<boolean>(false)
  const isScanningLonely = ref<boolean>(false)
  const isRunningMaintenance = ref<boolean>(false)
  const isDreaming = ref<boolean>(false)

  // Story 导入
  const showImportStoryDialog = ref<boolean>(false)
  const importStoryText = ref<string>('')
  const isImportingStory = ref<boolean>(false)

  // 内部状态
  const fetchMemoriesState: FetchWithLoading = { isLoading: false, lastRequestId: null }
  const fetchTagCloudState = { isLoading: false }

  // ─── 计算属性 ──────────────────────────────────────────────────────────────
  const topTags = computed<TagCloudItem[]>(() => {
    if (!tagCloud.value) return []
    if (Array.isArray(tagCloud.value)) return tagCloud.value
    return Object.entries(tagCloud.value)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 15)
      .map(([tag, count]) => ({ tag, count }))
  })

  // ─── 辅助函数 ───────────────────────────────────────────────────────────────
  const getMemoryTypeLabel = (type?: string): string => {
    const map: Record<string, string> = {
      event: '🧩 记忆块',
      preference: '💖 偏好',
      summary: '🧩 记忆块',
      interaction_summary: '🧩 记忆块',
      archived_event: '🗄️ 归档',
      fact: '🧠 事实',
      promise: '🤝 誓言',
      work_log: '📝 工作日志'
    }
    return type ? (map[type] ?? type) : ''
  }

  const getSentimentColor = (sentiment?: string): string => {
    const map: Record<string, string> = {
      positive: '#38bdf8',
      negative: '#fb7185',
      neutral: '#94a3b8',
      happy: '#fbbf24',
      sad: '#818cf8',
      angry: '#f87171',
      excited: '#e879f9'
    }
    return sentiment ? (map[sentiment] ?? '#38bdf8') : '#38bdf8'
  }

  // ─── 获取记忆 ─────────────────────────────────────────────────────────────
  const fetchMemories = async (): Promise<void> => {
    if (fetchMemoriesState.isLoading) return
    fetchMemoriesState.isLoading = true
    const currentRequestId = Symbol('fetchMemories')
    fetchMemoriesState.lastRequestId = currentRequestId

    try {
      let url = `${API_BASE}/memories/list?limit=1000`
      if (memoryFilterDate.value) url += `&date_start=${memoryFilterDate.value}`
      if (memoryFilterType.value) url += `&type=${memoryFilterType.value}`
      if (memoryFilterTags.value.length > 0) url += `&tags=${memoryFilterTags.value.join(',')}`
      if (activeAgent.value) url += `&agent_id=${activeAgent.value.id}`

      const rawMemories = await fetchJson<Record<string, unknown>[]>(url, {}, 5000)
      const processedMemories: Memory[] = []
      const batchSize = 50

      const processBatch = (startIndex: number): void => {
        if (fetchMemoriesState.lastRequestId !== currentRequestId) {
          fetchMemoriesState.isLoading = false
          return
        }
        const endIndex = Math.min(startIndex + batchSize, rawMemories.length)
        for (let i = startIndex; i < endIndex; i++) {
          const m = rawMemories[i]
          processedMemories.push(
            Object.freeze<Memory>({
              ...(m as Memory),
              realTime: new Date(m.timestamp as string).toLocaleDateString()
            })
          )
        }
        memories.value = [...processedMemories]
        if (endIndex < rawMemories.length) {
          setTimeout(() => processBatch(endIndex), 16)
        } else {
          fetchMemoriesState.isLoading = false
        }
      }
      processBatch(0)
      fetchTagCloud()
    } catch (e) {
      console.error(e)
      fetchMemoriesState.isLoading = false
    }
  }

  const fetchTagCloud = async (): Promise<void> => {
    if (fetchTagCloudState.isLoading) return
    fetchTagCloudState.isLoading = true
    try {
      tagCloud.value = await fetchJson<Record<string, number>>(`${API_BASE}/memories/tags`, {}, 3000)
    } catch {
      console.error('标签云获取错误')
    } finally {
      fetchTagCloudState.isLoading = false
    }
  }

  // ─── 删除 ──────────────────────────────────────────────────────────────────
  const deleteMemoryState = { isLoading: false }
  const deleteMemory = async (memoryId: string | number): Promise<void> => {
    if (!memoryId || deleteMemoryState.isLoading) {
      if (!memoryId) window.$notify('无效的记忆ID', 'error')
      return
    }
    try {
      await openConfirm('提示', '确定要遗忘这段记忆吗？', { type: 'warning' })
      deleteMemoryState.isLoading = true
      await fetchWithTimeout(
        `${API_BASE}/memories/${memoryId}`,
        { method: 'DELETE', throwOnError: true },
        5000
      )
      await fetchMemories()
      window.$notify('已遗忘', 'success')
    } catch (e) {
      if ((e as Error).message !== 'User cancelled') {
        console.error('Error in deleteMemory:', e)
        window.$notify('系统错误: ' + ((e as Error).message ?? '未知错误'), 'error')
      }
    } finally {
      deleteMemoryState.isLoading = false
    }
  }

  // ─── 图谱 ──────────────────────────────────────────────────────────────────
  const fetchMemoryGraph = async (): Promise<void> => {
    if (isLoadingGraph.value) return
    try {
      isLoadingGraph.value = true
      let url = `${API_BASE}/memories/graph?limit=100`
      if (activeAgent.value) url += `&agent_id=${activeAgent.value.id}`
      const res = await fetchJson<MemoryGraphData>(url, {}, 8000)
      if (currentTab.value === 'memories') {
        memoryGraphData.value = Object.freeze(res) as MemoryGraphData
        nextTick(() => requestAnimationFrame(() => initGraph()))
      }
    } catch {
      console.error('记忆图谱获取错误')
    } finally {
      isLoadingGraph.value = false
    }
  }

  const initGraph = (): void => {
    if (!graphRef.value) return
    if (chartInstance) chartInstance.dispose()
    chartInstance = echarts.init(graphRef.value, null, { renderer: 'canvas' })

    const nodes = memoryGraphData.value.nodes.map((node) => ({
      ...node,
      name: String(node.id),
      category: getMemoryTypeLabel(node.category),
      symbolSize: Math.min(Math.max(node.value * 5, 15), 40),
      itemStyle: {
        color: getSentimentColor(node.sentiment),
        borderColor: '#fff',
        borderWidth: 2,
        shadowBlur: 15,
        shadowColor: getSentimentColor(node.sentiment)
      },
      label: { show: node.value > 5, fontSize: 10, color: '#64748b' }
    }))

    const links = memoryGraphData.value.edges.map((edge) => ({
      ...edge,
      lineStyle: { width: Math.max(edge.value * 0.5, 1), curveness: 0.2, color: '#e2e8f0' }
    }))

    const categories = [...new Set(nodes.map((n) => n.category))].map((c) => ({ name: c }))

    const option: echarts.EChartsOption = {
      backgroundColor: 'transparent',
      title: {
        text: '✨ 核心记忆星云 ✨',
        subtext: 'Core Memory Nebula',
        top: '5%',
        left: 'center',
        textStyle: { color: '#8b5cf6', fontSize: 20, fontWeight: 'bolder' },
        subtextStyle: { color: '#cbd5e1' }
      },
      tooltip: {
        trigger: 'item',
        backgroundColor: 'rgba(255,255,255,0.9)',
        borderColor: '#e2e8f0',
        borderWidth: 1,
        textStyle: { color: '#334155' },
        extraCssText: 'box-shadow:0 8px 24px rgba(149,157,165,0.2);border-radius:16px;',
        formatter: (params: any) => {
          if (params.dataType === 'node') {
            const d = params.data
            return `<div style="padding:4px;"><div style="font-weight:900;margin-bottom:6px;font-size:14px;color:#475569;">记忆片段 #${d.id}</div><div style="font-size:13px;color:#64748b;margin-bottom:8px;line-height:1.5;">${d.full_content?.substring(0, 60) ?? ''}${(d.full_content?.length ?? 0) > 60 ? '...' : ''}</div></div>`
          }
          return `<div style="padding:4px;"><div style="font-weight:bold;color:#64748b;font-size:12px;">🔗 关联强度: ${params.data.value}</div><div style="font-size:11px;color:#94a3b8;">${params.data.relation_type}</div></div>`
        }
      },
      legend: {
        data: categories.map((a) => a.name),
        bottom: '5%',
        left: 'center',
        icon: 'circle',
        itemWidth: 8,
        itemHeight: 8,
        textStyle: { color: '#64748b', fontSize: 11 }
      },
      series: [
        {
          type: 'graph',
          layout: 'force',
          data: nodes as any,
          links: links as any,
          categories,
          roam: true,
          draggable: true,
          label: {
            show: true,
            position: 'bottom',
            formatter: '{b}',
            color: '#64748b',
            fontSize: 10
          },
          force: {
            repulsion: 250,
            gravity: 0.08,
            edgeLength: [60, 150],
            layoutAnimation: true,
            friction: 0.6
          },
          emphasis: { focus: 'adjacency' as const, scale: true }
        }
      ]
    }

    chartInstance.setOption(option)
    if (resizeHandler) window.removeEventListener('resize', resizeHandler)
    resizeHandler = () => chartInstance?.resize()
    window.addEventListener('resize', resizeHandler)
  }

  const disposeGraph = (): void => {
    if (chartInstance) {
      chartInstance.dispose()
      chartInstance = null
    }
    if (resizeHandler) {
      window.removeEventListener('resize', resizeHandler)
      resizeHandler = null
    }
  }

  // ─── 操作 ──────────────────────────────────────────────────────────────────
  const clearOrphanedEdges = async (): Promise<void> => {
    if (isClearingEdges.value) return
    try {
      await openConfirm(
        '清理确认',
        '确定要清理数据库中所有无效的连线吗？这不会删除任何记忆节点。',
        {
          type: 'warning'
        }
      )
      isClearingEdges.value = true
      const data = await fetchJson<{ deleted_count: number }>(
        `${API_BASE}/maintenance/memory/orphaned_edges`,
        { method: 'DELETE' },
        10000
      )
      window.$notify(`清理完成，共移除 ${data.deleted_count} 条无效连线`, 'success')
      if (memoryViewMode.value === 'graph') fetchMemoryGraph()
    } catch (e) {
      if ((e as Error).message !== 'User cancelled') {
        console.error(e)
        window.$notify('清理失败: ' + (e as Error).message, 'error')
      }
    } finally {
      isClearingEdges.value = false
    }
  }

  const triggerScanLonely = async (): Promise<void> => {
    if (isScanningLonely.value) return
    isScanningLonely.value = true
    try {
      const data = await fetchJson<{
        status: string
        new_relations?: number
        reason?: string
      }>(`${API_BASE}/maintenance/memory/scan_lonely?limit=5`, {
        method: 'POST'
      })
      if (data.status === 'success') {
        window.$notify(
          `扫描完成: 发现了 ${data.new_relations ?? 0} 个新关联`,
          'success'
        )
        fetchMemories()
      } else if (data.status === 'skipped') {
        window.$notify(`扫描跳过: ${data.reason}`, 'warning')
      } else {
        window.$notify('扫描失败', 'error')
      }

    } catch (e) {
      console.error(e)
      window.$notify('请求出错: ' + (e as Error).message, 'error')
    } finally {
      isScanningLonely.value = false
    }
  }

  const triggerMaintenance = async (): Promise<void> => {
    if (isRunningMaintenance.value) return
    try {
      await openConfirm(
        '执行确认',
        '深度维护可能需要较长时间，且会消耗一定的 Tokens。确定要立即执行吗？',
        { type: 'info' }
      )
      isRunningMaintenance.value = true
      const data = await fetchJson<{
        status: string
        important_tagged?: number
        consolidated?: number
        cleaned_count?: number
        error?: string
      }>(
        `${API_BASE}/maintenance/memory/legacy_maintenance`,
        { method: 'POST' },
        120000
      )
      if (data.status === 'success') {
        window.$notify(
          `维护完成: 标记重要性 ${data.important_tagged}, 记忆合并 ${data.consolidated}, 清理 ${data.cleaned_count}`,
          'success'
        )
        fetchMemories()
      } else {
        window.$notify(data.error ?? '维护失败', 'error')
      }
    } catch (e) {
      if ((e as Error).message !== 'User cancelled') {
        console.error(e)
        window.$notify('请求出错: ' + (e as Error).message, 'error')
      }
    } finally {
      isRunningMaintenance.value = false
    }
  }

  const triggerDream = async (): Promise<void> => {
    if (isDreaming.value) return
    try {
      await openConfirm('执行确认', '梦境联想将扫描近期记忆并尝试建立新的关联。确定要执行吗？', {
        type: 'info'
      })
      isDreaming.value = true
      const data = await fetchJson<{
        status: string
        anchors_processed?: number
        new_relations?: number
        reason?: string
      }>(
        `${API_BASE}/maintenance/memory/dream?limit=10`,
        { method: 'POST' },
        60000
      )
      if (data.status === 'success') {
        window.$notify(
          `梦境完成: 扫描 ${data.anchors_processed} 个锚点，发现 ${data.new_relations} 个新关联`,
          'success'
        )
        if (memoryViewMode.value === 'graph') fetchMemoryGraph()
      } else if (data.status === 'skipped') {
        window.$notify(`梦境跳过: ${data.reason}`, 'warning')
      } else {
        window.$notify('联想失败', 'error')
      }
    } catch (e) {
      if ((e as Error).message !== 'User cancelled') {
        console.error(e)
        window.$notify('请求出错: ' + (e as Error).message, 'error')
      }
    } finally {
      isDreaming.value = false
    }
  }

  // ─── Story 导入 ────────────────────────────────────────────────────────────
  const handleImportStory = async (): Promise<void> => {
    if (!importStoryText.value.trim()) {
      window.$notify('请输入内容', 'warning')
      return
    }
    isImportingStory.value = true
    try {
      const result = await fetchJson<{ count: number }>(`${API_BASE}/maintenance/memory/import`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          story: importStoryText.value,
          agent_id: activeAgent.value?.id ?? 'pero'
        })
      })
      window.$notify(`导入成功！共生成 ${result.count} 条记忆。`, 'success')
      showImportStoryDialog.value = false
      importStoryText.value = ''
      fetchMemories()
    } catch (error) {
      window.$notify(`导入失败: ${(error as Error).message}`, 'error')
    } finally {
      isImportingStory.value = false
    }
  }

  return {
    memories,
    tagCloud,
    memoryFilterTags,
    memoryFilterDate,
    memoryFilterType,
    memoryViewMode,
    memoryGraphData,
    isLoadingGraph,
    graphRef,
    topTags,
    isClearingEdges,
    isScanningLonely,
    isRunningMaintenance,
    isDreaming,
    showImportStoryDialog,
    importStoryText,
    isImportingStory,
    fetchMemories,
    fetchTagCloud,
    fetchMemoryGraph,
    initGraph,
    disposeGraph,
    deleteMemory,
    clearOrphanedEdges,
    triggerScanLonely,
    triggerMaintenance,
    triggerDream,
    handleImportStory,
    getMemoryTypeLabel,
    getSentimentColor
  }
}
