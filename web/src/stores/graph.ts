import { defineStore } from 'pinia'
import { computed, ref, shallowRef, watch } from 'vue'
import Graph from 'graphology'
import FA2Layout from 'graphology-layout-forceatlas2/worker'
import forceAtlas2 from 'graphology-layout-forceatlas2'
import louvain from 'graphology-communities-louvain'
import { fetchGraph } from '@/api/graph'
import type { GraphResponse } from '@/api/types'
import { useAppStore } from './app'
import { ShoreApiError } from '@/api/http'
import { getEventsClient } from '@/api/events'

type NodeKind = 'memory' | 'entity'
type GraphStateFilter = 'active' | 'superseded' | 'invalidated' | 'archived'

interface GraphFetchOptions {
  limit?: number
  includeArchived?: boolean
  state?: GraphStateFilter
}

export interface GraphNodeAttrs {
  kind: NodeKind
  label: string
  memoryId?: number
  entityId?: number
  state?: string
  scope?: string
  memoryType?: string
  entityType?: string
  importance?: number
  localMemoryCount?: number
  archived?: boolean
  community?: number
  x: number
  y: number
  size: number
  color: string
  // sigma 使用 type 字段选择 node program
  type: 'circle' | 'memory' | 'entity'
}

export interface GraphEdgeAttrs {
  kind: 'memory_entity' | 'supersede'
  size: number
  color: string
  type: 'line' | 'arrow'
  weight: number
}

// 节点 ID 命名：memory -> `m:<id>`，entity -> `e:<id>`
export function memoryNodeId(id: number): string {
  return `m:${id}`
}
export function entityNodeId(id: number): string {
  return `e:${id}`
}

/** 状态色：对齐 tokens.css --state-* */
const STATE_COLOR: Record<string, string> = {
  active: '#10B981',
  superseded: '#7C5CFF',
  invalidated: '#F43F5E',
  archived: '#64748B'
}
const ENTITY_COLOR = '#38BDF8'
const EDGE_ME_COLOR = 'rgba(124,92,255,0.22)'
const EDGE_SUP_COLOR = 'rgba(244,63,94,0.45)'

function stateColor(state: string | undefined): string {
  return STATE_COLOR[state ?? 'active'] ?? STATE_COLOR.archived
}

function clamp(v: number, lo: number, hi: number): number {
  return Math.max(lo, Math.min(hi, v))
}

/** 把 GraphResponse 构建成 graphology 的 UndirectedGraph + Louvain 社区 */
export function buildGraphFromResponse(resp: GraphResponse): Graph<GraphNodeAttrs, GraphEdgeAttrs> {
  const g = new Graph<GraphNodeAttrs, GraphEdgeAttrs>({ type: 'undirected', multi: false })

  // 环形初始布局，避免所有节点堆在原点导致 FA2 起步抖动
  const nMem = resp.memories.length
  const nEnt = resp.entities.length
  const ring = (i: number, total: number, r: number): { x: number; y: number } => {
    const theta = (i / Math.max(total, 1)) * Math.PI * 2
    return { x: Math.cos(theta) * r, y: Math.sin(theta) * r }
  }

  resp.memories.forEach((m, idx) => {
    const pos = ring(idx, nMem, 100 + (m.importance ?? 0) * 4)
    g.addNode(memoryNodeId(m.id), {
      kind: 'memory',
      memoryId: m.id,
      label: m.content_preview || `#${m.id}`,
      state: m.state,
      scope: m.scope,
      memoryType: m.memory_type,
      importance: m.importance,
      archived: !!m.archived_at,
      x: pos.x,
      y: pos.y,
      size: clamp(4 + (m.importance ?? 0) * 0.7, 4, 18),
      color: stateColor(m.state),
      type: 'circle'
    })
  })

  resp.entities.forEach((e, idx) => {
    const pos = ring(idx, nEnt, 220)
    g.addNode(entityNodeId(e.id), {
      kind: 'entity',
      entityId: e.id,
      label: e.name,
      entityType: e.entity_type,
      localMemoryCount: e.local_memory_count,
      x: pos.x,
      y: pos.y,
      size: clamp(3 + Math.sqrt(Math.max(1, e.local_memory_count)) * 2.2, 3, 22),
      color: ENTITY_COLOR,
      type: 'circle'
    })
  })

  // memory ↔ entity 边
  for (const edge of resp.memory_entity_edges) {
    const a = memoryNodeId(edge.memory_id)
    const b = entityNodeId(edge.entity_id)
    if (!g.hasNode(a) || !g.hasNode(b)) continue
    if (g.hasEdge(a, b)) continue
    g.addEdge(a, b, {
      kind: 'memory_entity',
      size: clamp(0.5 + (edge.weight ?? 1) * 0.6, 0.3, 2),
      color: EDGE_ME_COLOR,
      type: 'line',
      weight: edge.weight
    })
  }

  // supersede 边（from 新 -> to 旧）
  for (const edge of resp.supersede_edges) {
    const a = memoryNodeId(edge.from_memory_id)
    const b = memoryNodeId(edge.to_memory_id)
    if (!g.hasNode(a) || !g.hasNode(b)) continue
    if (g.hasEdge(a, b)) continue
    g.addEdge(a, b, {
      kind: 'supersede',
      size: 1.5,
      color: EDGE_SUP_COLOR,
      type: 'arrow',
      weight: 1
    })
  }

  // Louvain 社区（为 entity 着色变体或 hull 使用）
  try {
    louvain.assign(g, { nodeCommunityAttribute: 'community' })
  } catch {
    // 稀疏图或其它情况可能抛错，忽略
  }

  return g
}

export const PING_DURATION_MS = 2400

export const useGraphStore = defineStore('graph', () => {
  const app = useAppStore()

  /* ---------------- remote data ---------------- */
  const response = ref<GraphResponse | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)
  const queryLimit = ref(500)
  const queryIncludeArchived = ref(false)
  const queryState = ref<GraphStateFilter | undefined>(undefined)

  /* ---------------- graph instance ---------------- */
  const graph = shallowRef<Graph<GraphNodeAttrs, GraphEdgeAttrs> | null>(null)

  /* ---------------- layout ---------------- */
  let fa2: FA2Layout | null = null
  const layoutRunning = ref(false)

  function stopLayoutInternal() {
    if (fa2) {
      fa2.stop()
    }
    layoutRunning.value = false
  }

  function killLayoutInternal() {
    if (fa2) {
      try {
        fa2.kill()
      } catch {
        /* noop */
      }
      fa2 = null
    }
    layoutRunning.value = false
  }

  function startLayout() {
    const g = graph.value
    if (!g || g.order === 0) return
    if (!fa2) {
      // 预热一次同步 FA2，给 worker 提供更好的初值
      try {
        const settings = forceAtlas2.inferSettings(g)
        forceAtlas2.assign(g, { iterations: 50, settings })
      } catch {
        /* noop */
      }
      fa2 = new FA2Layout(g, {
        settings: {
          gravity: 0.8,
          scalingRatio: 8,
          slowDown: 12,
          barnesHutOptimize: g.order > 500,
          barnesHutTheta: 0.5,
          strongGravityMode: false,
          linLogMode: false
        }
      })
    }
    fa2.start()
    layoutRunning.value = true
  }

  function stopLayout() {
    stopLayoutInternal()
  }

  function toggleLayout() {
    if (layoutRunning.value) stopLayout()
    else startLayout()
  }

  /* ---------------- selection / interaction ---------------- */

  const selectedNodeId = ref<string | null>(null)
  const hoveredNodeId = ref<string | null>(null)
  const searchQuery = ref('')
  const neighborhoodDepth = ref<1 | 2>(1)

  const selectedMemoryId = computed<number | null>(() => {
    const id = selectedNodeId.value
    if (!id || !id.startsWith('m:')) return null
    const n = Number(id.slice(2))
    return Number.isFinite(n) ? n : null
  })

  const selectedEntityId = computed<number | null>(() => {
    const id = selectedNodeId.value
    if (!id || !id.startsWith('e:')) return null
    const n = Number(id.slice(2))
    return Number.isFinite(n) ? n : null
  })

  /* ---------------- ping (cross-view spotlight) ---------------- */
  // Nodes currently rendering a ping ring in the overlay canvas. Populated
  // via `pingMemories()` — typically from the recall view when the user
  // asks "show these hits on the graph". Values follow the `m:<id>` /
  // `e:<id>` node-id convention defined above.
  const pingedNodeIds = ref<Set<string>>(new Set())
  // Timestamp (`Date.now()` basis) at which the current ping animation
  // started. The overlay canvas uses this + `PING_DURATION_MS` to drive
  // the ring expansion / fade.
  const pingStartTs = ref<number>(0)
  // Memory ids requested while the graph was not yet loaded. Flushed into
  // `pingedNodeIds` as soon as `fetch()` resolves, so the recall → graph
  // hand-off works even if the graph view is being mounted cold.
  const pendingPingIds = ref<number[]>([])

  function flushPendingPings(): void {
    const g = graph.value
    if (!g || pendingPingIds.value.length === 0) return
    const resolved = new Set<string>()
    for (const id of pendingPingIds.value) {
      const nid = memoryNodeId(id)
      if (g.hasNode(nid)) resolved.add(nid)
    }
    if (resolved.size) {
      pingedNodeIds.value = resolved
      pingStartTs.value = Date.now()
      selectedNodeId.value = Array.from(resolved)[0] ?? null
    }
    pendingPingIds.value = []
  }

  function pingMemories(memoryIds: number[]): void {
    if (memoryIds.length === 0) return
    const g = graph.value
    if (!g) {
      pendingPingIds.value = Array.from(new Set(memoryIds))
      return
    }
    const resolved = new Set<string>()
    for (const id of memoryIds) {
      const nid = memoryNodeId(id)
      if (g.hasNode(nid)) resolved.add(nid)
    }
    if (resolved.size === 0) {
      // Not in the currently loaded slice — stash for after the next fetch.
      pendingPingIds.value = Array.from(new Set(memoryIds))
      return
    }
    pingedNodeIds.value = resolved
    pingStartTs.value = Date.now()
    selectedNodeId.value = Array.from(resolved)[0] ?? null
  }

  function clearPing(): void {
    if (pingedNodeIds.value.size) pingedNodeIds.value = new Set()
    pingStartTs.value = 0
  }

  /**
   * 计算当前需要高亮的节点集合：
   *   - 若有搜索，匹配节点 + 其邻域
   *   - 若有 selected / hovered，其邻域
   *   - 若两者都无，则返回 null 表示全亮
   */
  const focusedNodes = computed<Set<string> | null>(() => {
    const g = graph.value
    if (!g) return null
    const pivot = new Set<string>()
    const q = searchQuery.value.trim().toLowerCase()
    if (q) {
      g.forEachNode((id, attrs) => {
        if (attrs.label?.toLowerCase().includes(q)) pivot.add(id)
      })
    }
    if (selectedNodeId.value) pivot.add(selectedNodeId.value)
    if (hoveredNodeId.value) pivot.add(hoveredNodeId.value)
    if (!pivot.size) return null

    // 广度扩展 depth 层
    const depth = neighborhoodDepth.value
    let frontier = new Set(pivot)
    const included = new Set(pivot)
    for (let d = 0; d < depth; d += 1) {
      const next = new Set<string>()
      for (const nid of frontier) {
        g.forEachNeighbor(nid, (other) => {
          if (!included.has(other)) {
            next.add(other)
            included.add(other)
          }
        })
      }
      frontier = next
    }
    return included
  })

  /* ---------------- fetching ---------------- */

  async function fetch(options: GraphFetchOptions = {}) {
    if (!app.agentId) return
    if (options.limit !== undefined) {
      queryLimit.value = options.limit
    }
    if (options.includeArchived !== undefined) {
      queryIncludeArchived.value = options.includeArchived
    }
    if ('state' in options) {
      queryState.value = options.state
    }
    loading.value = true
    error.value = null
    killLayoutInternal()
    try {
      const res = await fetchGraph({
        agent_id: app.agentId,
        limit: queryLimit.value,
        include_archived: queryIncludeArchived.value,
        state: queryState.value
      })
      response.value = res
      graph.value = buildGraphFromResponse(res)
      // If anything was queued (recall → graph hand-off before mount), resolve it now.
      if (pendingPingIds.value.length > 0) flushPendingPings()
    } catch (err) {
      response.value = null
      graph.value = null
      error.value = err instanceof ShoreApiError ? err.message : (err as Error).message
    } finally {
      loading.value = false
    }
  }

  /* ---------------- disposal / agent switch ---------------- */

  function dispose() {
    killLayoutInternal()
    if (refreshTimer !== null) {
      window.clearTimeout(refreshTimer)
      refreshTimer = null
    }
    graph.value = null
    response.value = null
    selectedNodeId.value = null
    hoveredNodeId.value = null
    searchQuery.value = ''
    clearPing()
    pendingPingIds.value = []
  }

  watch(
    () => app.agentId,
    () => {
      dispose()
      void fetch()
    }
  )

  /* ---------------- live refresh on memory.updated ---------------- */

  let refreshTimer: number | null = null
  let eventsBound = false
  let unbindMemoryUpdated: (() => void) | null = null

  function bindEvents() {
    if (eventsBound) return
    eventsBound = true
    unbindMemoryUpdated = getEventsClient().onType('memory.updated', (evt) => {
      const payload = evt.payload as { agent_id?: string } | undefined
      if (payload?.agent_id && payload.agent_id !== app.agentId) {
        return
      }
      // 轻量节流：仅在没有进行布局时，防抖后拉一次（让前端保持上下文稳定）
      // 正在跑布局就暂不打扰；用户手动 reload 可得到最新结构
      if (!layoutRunning.value) {
        scheduleRefresh()
      }
    })
  }

  function unbindEvents() {
    if (refreshTimer !== null) {
      window.clearTimeout(refreshTimer)
      refreshTimer = null
    }
    if (unbindMemoryUpdated) {
      unbindMemoryUpdated()
      unbindMemoryUpdated = null
    }
    eventsBound = false
  }

  function scheduleRefresh() {
    if (refreshTimer !== null) window.clearTimeout(refreshTimer)
    refreshTimer = window.setTimeout(() => {
      refreshTimer = null
      void fetch()
    }, 800)
  }

  /* ---------------- derived stats ---------------- */

  const stats = computed(() => {
    const g = graph.value
    const resp = response.value
    if (!g || !resp) {
      return {
        memoryCount: 0,
        entityCount: 0,
        memoryEntityEdges: 0,
        supersedeEdges: 0,
        totalMemoriesForAgent: 0,
        truncated: false,
        communityCount: 0
      }
    }
    let maxCommunity = -1
    g.forEachNode((_id, attrs) => {
      if (attrs.community != null && attrs.community > maxCommunity) {
        maxCommunity = attrs.community
      }
    })
    return {
      memoryCount: resp.stats.memory_count,
      entityCount: resp.stats.entity_count,
      memoryEntityEdges: resp.stats.memory_entity_edges,
      supersedeEdges: resp.stats.supersede_edges,
      totalMemoriesForAgent: resp.stats.total_memories_for_agent,
      truncated: resp.stats.truncated,
      communityCount: maxCommunity + 1
    }
  })

  return {
    // state
    response,
    graph,
    loading,
    error,
    queryLimit,
    queryIncludeArchived,
    queryState,
    layoutRunning,
    selectedNodeId,
    hoveredNodeId,
    searchQuery,
    neighborhoodDepth,
    selectedMemoryId,
    selectedEntityId,
    focusedNodes,
    pingedNodeIds,
    pingStartTs,
    pendingPingIds,
    stats,
    // actions
    fetch,
    startLayout,
    stopLayout,
    toggleLayout,
    pingMemories,
    clearPing,
    flushPendingPings,
    dispose,
    bindEvents,
    unbindEvents,
    scheduleRefresh
  }
})
