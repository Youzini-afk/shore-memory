/**
 * useLogs.ts
 * 对话日志的数据获取、编辑、删除、重试分析
 */
import { ref, shallowRef, type Ref } from 'vue'
import { API_BASE, fetchWithTimeout, formatLLMError } from './useDashboard'
import type { LogEntry, Agent, DebugSegment, PromptMessage, OpenConfirmFn } from './types'

interface UseLogsOptions {
  activeAgent: Ref<Agent | null>
  currentTab: Ref<string>
  openConfirm: OpenConfirmFn
}

const fetchLogsState = {
  lastRequestId: null as symbol | null
}

export function useLogs({ activeAgent, currentTab, openConfirm }: UseLogsOptions) {
  const logs = shallowRef<LogEntry[]>([])
  const isLogsFetching = ref<boolean>(false)

  // 筛选条件
  const selectedSource = ref<string>('all')
  const selectedSessionId = ref<string>('all')
  const lastSyncedSessionId = ref<string | null>(null)
  const selectedDate = ref<string>('')
  const selectedSort = ref<'asc' | 'desc'>('desc')

  // 编辑状态
  const editingLogId = ref<string | number | null>(null)
  const editingContent = ref<string>('')

  // Debug 对话框
  const showDebugDialog = ref<boolean>(false)
  const currentDebugLog = ref<LogEntry | null>(null)
  const debugSegments = ref<DebugSegment[]>([])
  const debugViewMode = ref<'response' | 'prompt'>('response')
  const currentPromptMessages = ref<PromptMessage[]>([])
  const isLoadingPrompt = ref<boolean>(false)

  const totalPromptLength = (): number =>
    currentPromptMessages.value.reduce((acc, msg) => acc + (msg.content ?? '').length, 0)

  // ─── 辅助函数 ───────────────────────────────────────────────────────────────
  const getLogMetadata = (log: LogEntry): Record<string, unknown> => {
    if (!log) return {}
    try {
      return JSON.parse(log.metadata_json ?? '{}') as Record<string, unknown>
    } catch {
      return {}
    }
  }

  const getSentimentEmoji = (sentiment?: string | null): string => {
    if (!sentiment) return 'mood-neutral'
    const map: Record<string, string> = {
      positive: 'mood-happy',
      negative: 'mood-sad',
      neutral: 'mood-neutral',
      happy: 'mood-happy',
      sad: 'mood-sad',
      angry: 'mood-angry',
      excited: 'mood-excited'
    }
    return map[sentiment.toLowerCase()] ?? 'mood-neutral'
  }

  const getSentimentLabel = (sentiment?: string | null): string => {
    if (!sentiment) return '平静'
    const map: Record<string, string> = {
      positive: '开心',
      negative: '忧郁',
      neutral: '平静',
      happy: '开心',
      sad: '忧郁',
      angry: '愤怒',
      excited: '激动'
    }
    return map[sentiment.toLowerCase()] ?? sentiment
  }

  const formatLogContent = (content?: string): string => {
    if (!content) return ''
    return content.replace(/【(Thinking|Monologue)[\s\S]*?】/gi, '')
  }

  // ─── Session 初始化 ────────────────────────────────────────────────────────
  const initSessionAndFetchLogs = async (): Promise<void> => {
    const storedSessionId = localStorage.getItem('ppc.sessionId')
    if (storedSessionId && !selectedSessionId.value) {
      selectedSessionId.value = storedSessionId
    } else if (!selectedSessionId.value) {
      selectedSessionId.value = 'default'
    }
    await fetchLogs()
  }

  // ─── 获取日志 ──────────────────────────────────────────────────────────────
  const fetchLogs = async (): Promise<void> => {
    if (!selectedSessionId.value || isLogsFetching.value) return
    isLogsFetching.value = true
    const currentRequestId = Symbol('fetchLogs')
    fetchLogsState.lastRequestId = currentRequestId

    try {
      let url = `${API_BASE}/history/${selectedSource.value}/${selectedSessionId.value}?limit=200&sort=${selectedSort.value}`
      if (selectedDate.value) url += `&date=${selectedDate.value}`
      if (activeAgent.value) url += `&agent_id=${activeAgent.value.id}`

      const res = await fetchWithTimeout(url, {}, 5000)
      const rawLogs = (await res.json()) as unknown[]

      if (fetchLogsState.lastRequestId !== currentRequestId) return

      const processedLogs = (Array.isArray(rawLogs) ? rawLogs : [])
        .filter((log): log is Record<string, unknown> => !!log && typeof log === 'object')
        .map((log) => {
          const metadata = getLogMetadata(log as LogEntry)
          const images =
            (metadata?.images as string[] | undefined)?.map(
              (path) => `${API_BASE}/ide/image?path=${encodeURIComponent(path)}`
            ) ?? []
          return Object.freeze<LogEntry>({
            ...(log as LogEntry),
            displayTime: new Date(log.timestamp as string).toLocaleString(),
            metadata: metadata,
            sentiment: (log.sentiment as string | null) ?? (metadata?.sentiment as string) ?? null,
            importance:
              (log.importance as number | null) ?? (metadata?.importance as number) ?? null,
            images
          })
        })

      logs.value = processedLogs

      setTimeout(() => {
        if (currentTab.value !== 'logs') return
        const container = document.querySelector('.chat-scroll-area')
        if (container) {
          ;(container as HTMLElement).scrollTop =
            selectedSort.value === 'desc' ? 0 : container.scrollHeight
        }
      }, 50)
    } catch (e) {
      console.error(e)
      window.$notify('获取日志失败', 'error')
    } finally {
      isLogsFetching.value = false
    }
  }

  // ─── 编辑 ──────────────────────────────────────────────────────────────────
  const startLogEdit = (log: LogEntry): void => {
    editingLogId.value = log.id
    editingContent.value = log.content
  }

  const cancelLogEdit = (): void => {
    editingLogId.value = null
    editingContent.value = ''
  }

  const saveLogEdit = async (logId: string | number): Promise<void> => {
    if (!editingContent.value.trim()) return
    try {
      const res = await fetchWithTimeout(
        `${API_BASE}/history/${logId}`,
        {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ content: editingContent.value })
        },
        5000
      )
      if (res.ok) {
        editingLogId.value = null
        await fetchLogs()
        window.$notify('已修改', 'success')
      } else {
        window.$notify('修改失败', 'error')
      }
    } catch (e) {
      window.$notify('网络错误', 'error')
      console.error(e)
    }
  }

  // ─── 删除 ──────────────────────────────────────────────────────────────────
  const deleteLog = async (logId: string | number): Promise<void> => {
    if (!logId) {
      window.$notify('无效的记录ID', 'error')
      return
    }
    try {
      await openConfirm('提示', '确定删除这条记录？', { type: 'warning' })
      const res = await fetchWithTimeout(`${API_BASE}/history/${logId}`, { method: 'DELETE' }, 5000)
      if (res.ok) {
        window.$notify('已删除', 'success')
        await fetchLogs()
      } else {
        const err = (await res.json()) as { message?: string }
        window.$notify(err.message ?? '删除失败', 'error')
      }
    } catch (e) {
      if ((e as Error).message !== 'User cancelled') {
        console.error('Error in deleteLog:', e)
        window.$notify('系统错误: ' + ((e as Error).message ?? '未知错误'), 'error')
      }
    }
  }

  // ─── 重试分析 ──────────────────────────────────────────────────────────────
  const updateLogStatus = (logId: string | number, status: LogEntry['analysis_status']): void => {
    const index = logs.value.findIndex((l) => l.id === logId)
    if (index !== -1) {
      const newLogs = [...logs.value]
      newLogs[index] = Object.freeze({ ...logs.value[index], analysis_status: status })
      logs.value = newLogs
    }
  }

  const retryLogAnalysis = async (log: LogEntry): Promise<void> => {
    if (!log?.id) {
      window.$notify('无效的日志 ID', 'error')
      return
    }
    try {
      if (log.analysis_status === 'processing') return
      updateLogStatus(log.id, 'processing')
      const res = await fetchWithTimeout(
        `${API_BASE}/history/${log.id}/retry_analysis`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          silent: true
        } as RequestInit,
        10000
      )
      if (res.ok) {
        window.$notify('已提交重试请求', 'success')
        setTimeout(() => fetchLogs(), 2000)
      } else {
        const err = (await res.json()) as { detail?: string }
        throw new Error(err.detail ?? '重试请求失败')
      }
    } catch (e) {
      console.error('Retry failed:', e)
      window.$notify(formatLLMError(e), 'error')
      updateLogStatus(log.id, 'failed')
    }
  }

  // ─── Debug 对话框 ──────────────────────────────────────────────────────────
  const parseDebugContent = (content: string): void => {
    if (!content) {
      debugSegments.value = []
      return
    }
    const patterns = [
      { type: 'nit' as const, regex: /\[\[\[NIT_CALL\]\]\][\s\S]*?\[\[\[NIT_END\]\]\]/gi },
      { type: 'nit' as const, regex: /<(nit(?:-[0-9a-fA-F]{4})?)>[\s\S]*?<\/\1>/gi },
      { type: 'thinking' as const, regex: /【Thinking[\s\S]*?】/gi },
      { type: 'thinking' as const, regex: /<think>[\s\S]*?<\/think>/gi },
      { type: 'monologue' as const, regex: /【Monologue[\s\S]*?】/gi }
    ]

    const matches: Array<{
      type: DebugSegment['type']
      start: number
      end: number
      content: string
    }> = []
    for (const p of patterns) {
      const regex = new RegExp(p.regex)
      let match: RegExpExecArray | null
      while ((match = regex.exec(content)) !== null) {
        matches.push({
          type: p.type,
          start: match.index,
          end: match.index + match[0].length,
          content: match[0]
        })
      }
    }
    matches.sort((a, b) => a.start - b.start)

    const unique: typeof matches = []
    if (matches.length > 0) {
      let cur = matches[0]
      unique.push(cur)
      for (let i = 1; i < matches.length; i++) {
        if (matches[i].start >= cur.end) {
          unique.push(matches[i])
          cur = matches[i]
        }
      }
    }

    const segments: DebugSegment[] = []
    let lastIndex = 0
    for (const m of unique) {
      if (m.start > lastIndex)
        segments.push({ type: 'text', content: content.substring(lastIndex, m.start) })
      segments.push({ type: m.type, content: m.content })
      lastIndex = m.end
    }
    if (lastIndex < content.length)
      segments.push({ type: 'text', content: content.substring(lastIndex) })
    debugSegments.value = segments
  }

  const openDebugDialog = (log: LogEntry): void => {
    currentDebugLog.value = log
    showDebugDialog.value = true
    debugViewMode.value = 'response'
    parseDebugContent(log.raw_content ?? log.content ?? '')
  }

  const handleDebugModeChange = async (val: 'response' | 'prompt'): Promise<void> => {
    if (val === 'prompt' && currentDebugLog.value) {
      isLoadingPrompt.value = true
      currentPromptMessages.value = []
      try {
        const log = currentDebugLog.value
        const res = await fetchWithTimeout(
          `${API_BASE}/agents/preview_prompt`,
          {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              session_id: log.session_id ?? selectedSessionId.value ?? 'default',
              source: log.source ?? selectedSource.value ?? 'desktop',
              log_id: log.id
            }),
            silent: true
          } as RequestInit,
          10000
        )
        if (res.ok) {
          const data = (await res.json()) as { messages: PromptMessage[] }
          currentPromptMessages.value = data.messages
        } else {
          const err = (await res.json()) as { detail?: string }
          throw new Error(err.detail ?? '获取提示词失败')
        }
      } catch (e) {
        window.$notify(formatLLMError(e), 'error')
      } finally {
        isLoadingPrompt.value = false
      }
    }
  }

  const handleLogUpdate = (data: Record<string, unknown>, fetchLogsRef: () => void): void => {
    const payload = (data.params ?? data) as { operation?: string; id?: string | number }
    if (payload.operation === 'delete') {
      logs.value = logs.value.filter((l) => l.id != payload.id)
    } else {
      fetchLogsRef()
    }
  }

  return {
    logs,
    isLogsFetching,
    selectedSource,
    selectedSessionId,
    lastSyncedSessionId,
    selectedDate,
    selectedSort,
    editingLogId,
    editingContent,
    showDebugDialog,
    currentDebugLog,
    debugSegments,
    debugViewMode,
    currentPromptMessages,
    isLoadingPrompt,
    totalPromptLength,
    initSessionAndFetchLogs,
    fetchLogs,
    startLogEdit,
    cancelLogEdit,
    saveLogEdit,
    deleteLog,
    retryLogAnalysis,
    updateLogStatus,
    openDebugDialog,
    handleDebugModeChange,
    handleLogUpdate,
    getLogMetadata,
    getSentimentEmoji,
    getSentimentLabel,
    formatLogContent
  }
}
