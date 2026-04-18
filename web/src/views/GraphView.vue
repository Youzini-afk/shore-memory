<script setup lang="ts">
import { onMounted, onBeforeUnmount, ref, watch, computed } from 'vue'
import { storeToRefs } from 'pinia'
import { AlertTriangle, Hash, Network } from 'lucide-vue-next'
import PBadge from '@/components/ui/PBadge.vue'
import PCard from '@/components/ui/PCard.vue'
import GraphCanvas from '@/components/graph/GraphCanvas.vue'
import GraphControls from '@/components/graph/GraphControls.vue'
import GraphLegend from '@/components/graph/GraphLegend.vue'
import GraphStats from '@/components/graph/GraphStats.vue'
import DetailPane from '@/components/memories/DetailPane.vue'
import MetaField from '@/components/memories/MetaField.vue'
import { useAppStore } from '@/stores/app'
import { useGraphStore } from '@/stores/graph'
import { useMemoriesStore } from '@/stores/memories'

const app = useAppStore()
const store = useGraphStore()
const memories = useMemoriesStore()
const { response, loading, error, selectedMemoryId, selectedEntityId, stats } =
  storeToRefs(store)

const canvasRef = ref<InstanceType<typeof GraphCanvas> | null>(null)

onMounted(() => {
  store.bindEvents()
  void store.fetch()
})

onBeforeUnmount(() => {
  store.unbindEvents()
  store.dispose()
})

// memory 节点点击 → 联动 memories store 的 detail 获取
watch(selectedMemoryId, (id) => {
  if (id != null) {
    void memories.select(id)
  }
})

// entity 详情
const selectedEntity = computed(() => {
  const id = selectedEntityId.value
  if (id == null || !response.value) return null
  return response.value.entities.find((e) => e.id === id) ?? null
})

const entityLinkedMemories = computed(() => {
  const id = selectedEntityId.value
  if (id == null || !response.value) return []
  const memIds = new Set(
    response.value.memory_entity_edges.filter((l) => l.entity_id === id).map((l) => l.memory_id)
  )
  return response.value.memories.filter((m) => memIds.has(m.id))
})

const showDetailDrawer = computed(
  () => selectedMemoryId.value != null || selectedEntity.value != null
)

function fit() {
  canvasRef.value?.fit()
}
function zoomIn() {
  canvasRef.value?.zoomIn()
}
function zoomOut() {
  canvasRef.value?.zoomOut()
}
</script>

<template>
  <div class="h-full flex flex-col min-h-0">
    <!-- Header -->
    <div class="relative px-8 pt-6 pb-4 overflow-hidden border-b border-shore-line/80">
      <div
        class="pointer-events-none absolute -top-20 -left-20 h-56 w-[560px] blur-[100px] opacity-35"
        style="background: radial-gradient(closest-side, rgba(56,189,248,0.45), transparent 70%)"
      />
      <div class="relative flex items-end justify-between gap-6">
        <div class="min-w-0">
          <h1 class="font-display text-[24px] leading-tight tracking-tight text-ink-1">
            记忆图谱
          </h1>
          <p class="mt-1 text-[12.5px] text-ink-3">
            在 Agent <span class="text-ink-2">{{ app.agentId }}</span> 的记忆与实体子图中观察簇团、脉冲与取代链
          </p>
        </div>
        <div class="flex items-center gap-2 shrink-0">
          <PBadge tone="accent" size="sm" dot>Agent · {{ app.agentId }}</PBadge>
          <PBadge v-if="stats.truncated" tone="amber" size="sm">
            已截断 · {{ stats.memoryCount }}/{{ stats.totalMemoriesForAgent }}
          </PBadge>
          <PBadge v-else tone="active" size="sm">
            完整 · {{ stats.memoryCount }} 条记忆
          </PBadge>
        </div>
      </div>
    </div>

    <!-- Controls -->
    <div class="px-6 py-2.5 border-b border-shore-line/80 bg-shore-surface">
      <GraphControls :on-fit="fit" :on-zoom-in="zoomIn" :on-zoom-out="zoomOut" />
    </div>

    <!-- Body -->
    <div class="flex-1 min-h-0 relative overflow-hidden">
      <GraphCanvas ref="canvasRef" />

      <!-- Floating overlays -->
      <div class="absolute top-4 left-4 z-10">
        <GraphStats />
      </div>
      <div class="absolute top-4 right-4 z-10">
        <GraphLegend />
      </div>

      <!-- Loading overlay -->
      <div
        v-if="loading"
        class="absolute inset-0 flex items-center justify-center bg-shore-bg/55 backdrop-blur-[2px] z-20"
      >
        <div class="flex items-center gap-2 text-[12px] font-display text-ink-2">
          <span class="h-2 w-2 rounded-full bg-accent animate-pulse" />
          正在拉取图谱…
        </div>
      </div>

      <!-- Error overlay -->
      <div
        v-else-if="error"
        class="absolute inset-0 flex items-center justify-center p-8 z-10"
      >
        <div
          class="max-w-md rounded-panel border border-state-invalidated/40 bg-state-invalidated/10 px-4 py-3 text-[12.5px] text-state-invalidated flex items-start gap-2"
        >
          <AlertTriangle class="h-4 w-4 mt-0.5 shrink-0" :stroke-width="1.75" />
          <div>
            <div class="font-display">图谱加载失败</div>
            <div class="mt-1 text-[11.5px] opacity-90">{{ error }}</div>
          </div>
        </div>
      </div>

      <!-- Empty -->
      <div
        v-else-if="response && stats.memoryCount === 0"
        class="absolute inset-0 flex items-center justify-center z-10"
      >
        <div class="text-center text-[12.5px] text-ink-4 max-w-sm">
          <div
            class="mx-auto mb-3 h-12 w-12 rounded-card bg-accent/10 border border-accent/20 flex items-center justify-center text-accent"
          >
            <Network class="h-5 w-5" :stroke-width="1.75" />
          </div>
          <div class="font-display text-ink-1 text-[14px] mb-1">图谱尚空</div>
          该 Agent 还没有任何已索引的记忆，先从记忆库或接入的 Bot 喂点数据再回来看。
        </div>
      </div>

      <!-- Detail drawer -->
      <div
        v-if="showDetailDrawer"
        class="absolute inset-y-0 right-0 z-30 w-full md:w-[460px] xl:w-[520px] min-h-0 bg-shore-surface/96 backdrop-blur-md shadow-[0_24px_64px_rgba(0,0,0,0.38)]"
      >
        <!-- memory selected -->
        <DetailPane v-if="selectedMemoryId != null" />

        <!-- entity selected -->
        <div
          v-else-if="selectedEntity"
          class="flex flex-col min-h-0 h-full border-l border-shore-line/80"
        >
          <div class="px-6 pt-5 pb-4 border-b border-shore-line/80">
            <div class="flex items-center gap-2 text-[11px] font-display tracking-tight">
              <span class="tabular text-ink-4">#{{ selectedEntity.id }}</span>
              <PBadge tone="blue" size="sm">实体</PBadge>
              <PBadge tone="ink" size="sm">{{ selectedEntity.entity_type || '未知类型' }}</PBadge>
              <span class="flex-1" />
            </div>
            <div class="mt-2 font-display text-[20px] leading-tight text-ink-1 break-words">
              {{ selectedEntity.name }}
            </div>
          </div>

          <div class="flex-1 min-h-0 overflow-y-auto p-6 flex flex-col gap-5">
            <PCard compact edge>
              <div class="text-[10.5px] uppercase tracking-[0.2em] font-display text-ink-4 mb-2">
                规模
              </div>
              <MetaField label="视图内">
                <span class="tabular text-ink-1">{{ selectedEntity.local_memory_count }}</span>
                <span class="ml-1 text-ink-4 text-[11px]">条可见记忆</span>
              </MetaField>
              <MetaField label="全局">
                <span class="tabular text-ink-1">{{ selectedEntity.linked_memory_count }}</span>
                <span class="ml-1 text-ink-4 text-[11px]">条历史关联</span>
              </MetaField>
            </PCard>

            <PCard compact edge>
              <div class="text-[10.5px] uppercase tracking-[0.2em] font-display text-ink-4 mb-2 flex items-center gap-1.5">
                <Hash class="h-3 w-3" :stroke-width="1.75" />
                关联记忆 · {{ entityLinkedMemories.length }}
              </div>
              <div v-if="entityLinkedMemories.length" class="flex flex-col divide-y divide-shore-line/50">
                <button
                  v-for="m in entityLinkedMemories"
                  :key="m.id"
                  type="button"
                  class="flex items-start gap-2 py-2 text-left hover:bg-shore-hover transition-colors rounded-btn px-2 -mx-2"
                  @click="store.selectedNodeId = 'm:' + m.id"
                >
                  <span class="mt-1 h-1.5 w-1.5 rounded-full shrink-0" :style="{
                    background:
                      m.state === 'active' ? '#10B981' :
                      m.state === 'superseded' ? '#7C5CFF' :
                      m.state === 'invalidated' ? '#F43F5E' : '#64748B'
                  }" />
                  <div class="min-w-0 flex-1">
                    <div class="flex items-center gap-2 text-[10.5px] font-display text-ink-4">
                      <span class="tabular">#{{ m.id }}</span>
                      <span class="truncate max-w-[100px]">{{ m.memory_type }}</span>
                      <span class="tabular">重要度 {{ m.importance.toFixed(1) }}</span>
                    </div>
                    <div class="text-[12px] text-ink-1 line-clamp-2">
                      {{ m.content_preview }}
                    </div>
                  </div>
                </button>
              </div>
              <div v-else class="text-[11px] text-ink-5">—</div>
            </PCard>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
