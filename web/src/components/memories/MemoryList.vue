<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { useVirtualizer } from '@tanstack/vue-virtual'
import { storeToRefs } from 'pinia'
import { Loader2, DatabaseZap } from 'lucide-vue-next'
import { useMemoriesStore } from '@/stores/memories'
import MemoryRow from './MemoryRow.vue'

const store = useMemoriesStore()
const { items, listLoading, listError, hasMore, selectedId, count, total } = storeToRefs(store)

const parentRef = ref<HTMLElement | null>(null)

const rowVirtualizer = useVirtualizer(
  computed(() => ({
    count: items.value.length,
    getScrollElement: () => parentRef.value,
    estimateSize: () => 112,
    overscan: 8
  }))
)

const virtualRows = computed(() => rowVirtualizer.value.getVirtualItems())
const totalSize = computed(() => rowVirtualizer.value.getTotalSize())

// 无限滚动：最后一个渲染项靠近尾部时自动加载
watch(
  virtualRows,
  (rows) => {
    if (!rows.length) return
    const last = rows[rows.length - 1]
    if (!last) return
    if (last.index >= items.value.length - 8 && hasMore.value && !listLoading.value) {
      void store.loadMore()
    }
  },
  { flush: 'post' }
)

function onSelect(id: number) {
  void store.select(id)
}

onMounted(() => {
  if (!items.value.length && !listLoading.value) {
    void store.reload()
  }
})

// 选中时滚动到可见位置
watch(selectedId, (id) => {
  if (id === null) return
  const idx = items.value.findIndex((m) => m.id === id)
  if (idx >= 0) {
    rowVirtualizer.value.scrollToIndex(idx, { align: 'auto' })
  }
})
</script>

<template>
  <div class="flex flex-col min-h-0 flex-1">
    <!-- List body -->
    <div
      ref="parentRef"
      class="flex-1 min-h-0 overflow-y-auto relative"
    >
      <!-- Error -->
      <div
        v-if="listError"
        class="m-6 rounded-btn bg-state-invalidated/10 border border-state-invalidated/30 px-4 py-3 text-[12.5px] text-state-invalidated"
      >
        {{ listError }}
      </div>

      <!-- Empty -->
      <div
        v-else-if="!items.length && !listLoading"
        class="flex flex-col items-center justify-center h-full min-h-[280px] gap-3 px-6 text-center"
      >
        <div
          class="h-12 w-12 rounded-card bg-accent/10 border border-accent/20 flex items-center justify-center text-accent"
        >
          <DatabaseZap class="h-5 w-5" :stroke-width="1.75" />
        </div>
        <div class="font-display text-[14px] text-ink-1">没有匹配的记忆</div>
        <div class="text-[11.5px] text-ink-4 max-w-sm">
          清除筛选条件或切换 Agent 后再试。此列表会随 `memory.updated` 事件自动刷新详情。
        </div>
      </div>

      <!-- Virtual list -->
      <div
        v-else
        class="relative w-full"
        :style="{ height: `${totalSize}px` }"
      >
        <div
          v-for="row in virtualRows"
          :key="items[row.index]?.id ?? row.index"
          class="absolute left-0 right-0"
          :style="{ transform: `translateY(${row.start}px)`, height: `${row.size}px` }"
          @click="onSelect(items[row.index].id)"
        >
          <MemoryRow
            :memory="items[row.index]"
            :selected="selectedId === items[row.index].id"
          />
        </div>
      </div>
    </div>

    <!-- Bottom status bar -->
    <div
      class="shrink-0 border-t border-shore-line/80 px-4 py-2 flex items-center gap-3 text-[10.5px] font-display text-ink-4 bg-shore-surface"
    >
      <span v-if="listLoading" class="flex items-center gap-1.5 text-ink-3">
        <Loader2 class="h-3 w-3 animate-spin" :stroke-width="1.75" />
        loading…
      </span>
      <span v-else-if="hasMore" class="text-ink-4">
        scroll to load more · <span class="tabular text-ink-2">{{ count }}</span>
        / <span class="tabular">{{ total }}</span>
      </span>
      <span v-else>
        end of list ·
        <span class="tabular text-ink-2">{{ count }}</span>
        loaded
      </span>
    </div>
  </div>
</template>
