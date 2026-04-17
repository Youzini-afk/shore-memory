<script setup lang="ts">
import { ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { Search, Play, Pause, ZoomIn, ZoomOut, Expand, RefreshCw, X } from 'lucide-vue-next'
import PInput from '@/components/ui/PInput.vue'
import PSegment from '@/components/ui/PSegment.vue'
import { useGraphStore } from '@/stores/graph'

interface Props {
  onFit?: () => void
  onZoomIn?: () => void
  onZoomOut?: () => void
}
const props = defineProps<Props>()

const store = useGraphStore()
const { searchQuery, layoutRunning, neighborhoodDepth, loading, queryLimit } = storeToRefs(store)

const localSearch = ref(searchQuery.value)
let debounceTimer: number | null = null
watch(localSearch, (v) => {
  if (debounceTimer !== null) window.clearTimeout(debounceTimer)
  debounceTimer = window.setTimeout(() => {
    searchQuery.value = v
  }, 180)
})

const limitOptions = [
  { label: '100', value: 100 },
  { label: '500', value: 500 },
  { label: '1k', value: 1000 },
  { label: '3k', value: 3000 }
]

async function reload() {
  await store.fetch({ limit: queryLimit.value })
}

function toggleLayout() {
  store.toggleLayout()
}

function clearSelection() {
  store.selectedNodeId = null
}

watch(queryLimit, () => {
  void reload()
})
</script>

<template>
  <div class="flex items-center gap-2">
    <PInput
      v-model="localSearch"
      size="sm"
      placeholder="search · memory / entity label"
      class="w-[240px]"
    >
      <template #prefix>
        <Search class="h-3.5 w-3.5" :stroke-width="1.75" />
      </template>
      <template v-if="localSearch" #suffix>
        <button
          type="button"
          class="h-4 w-4 flex items-center justify-center text-ink-4 hover:text-ink-1"
          @click="localSearch = ''"
        >
          <X class="h-3 w-3" :stroke-width="1.75" />
        </button>
      </template>
    </PInput>

    <div class="h-6 w-px bg-shore-line/80" />

    <div class="flex items-center gap-1">
      <span class="text-[10.5px] uppercase tracking-[0.2em] font-display text-ink-5">
        depth
      </span>
      <PSegment
        v-model="neighborhoodDepth"
        :options="[
          { value: 1, label: '1' },
          { value: 2, label: '2' }
        ]"
        size="sm"
      />
    </div>

    <div class="h-6 w-px bg-shore-line/80" />

    <div class="flex items-center gap-1">
      <span class="text-[10.5px] uppercase tracking-[0.2em] font-display text-ink-5">
        limit
      </span>
      <PSegment v-model="queryLimit" :options="limitOptions" size="sm" />
    </div>

    <div class="flex-1" />

    <button
      type="button"
      class="h-8 w-8 rounded-btn border border-shore-line bg-shore-card text-ink-2 hover:text-ink-0 hover:border-accent/60 transition-colors flex items-center justify-center"
      :title="layoutRunning ? 'Pause layout' : 'Run force-atlas2'"
      @click="toggleLayout"
    >
      <component
        :is="layoutRunning ? Pause : Play"
        class="h-3.5 w-3.5"
        :stroke-width="1.75"
      />
    </button>
    <button
      type="button"
      class="h-8 w-8 rounded-btn border border-shore-line bg-shore-card text-ink-2 hover:text-ink-0 hover:border-accent/60 transition-colors flex items-center justify-center"
      title="Zoom in"
      @click="props.onZoomIn?.()"
    >
      <ZoomIn class="h-3.5 w-3.5" :stroke-width="1.75" />
    </button>
    <button
      type="button"
      class="h-8 w-8 rounded-btn border border-shore-line bg-shore-card text-ink-2 hover:text-ink-0 hover:border-accent/60 transition-colors flex items-center justify-center"
      title="Zoom out"
      @click="props.onZoomOut?.()"
    >
      <ZoomOut class="h-3.5 w-3.5" :stroke-width="1.75" />
    </button>
    <button
      type="button"
      class="h-8 w-8 rounded-btn border border-shore-line bg-shore-card text-ink-2 hover:text-ink-0 hover:border-accent/60 transition-colors flex items-center justify-center"
      title="Fit to screen"
      @click="props.onFit?.()"
    >
      <Expand class="h-3.5 w-3.5" :stroke-width="1.75" />
    </button>
    <button
      type="button"
      class="h-8 px-2.5 rounded-btn border border-shore-line bg-shore-card text-[11.5px] text-ink-2 hover:text-ink-0 hover:border-accent/60 transition-colors flex items-center gap-1.5 font-display"
      title="Reload graph"
      :disabled="loading"
      @click="reload"
    >
      <RefreshCw class="h-3.5 w-3.5" :class="loading ? 'animate-spin' : ''" :stroke-width="1.75" />
      reload
    </button>
    <button
      v-if="store.selectedNodeId"
      type="button"
      class="h-8 px-2.5 rounded-btn border border-shore-line text-[11.5px] text-ink-3 hover:text-state-invalidated transition-colors flex items-center gap-1 font-display"
      @click="clearSelection"
    >
      <X class="h-3.5 w-3.5" :stroke-width="1.75" />
      unselect
    </button>
  </div>
</template>
