<script setup lang="ts">
import { onMounted } from 'vue'
import { storeToRefs } from 'pinia'
import PBadge from '@/components/ui/PBadge.vue'
import FilterBar from '@/components/memories/FilterBar.vue'
import MemoryList from '@/components/memories/MemoryList.vue'
import DetailPane from '@/components/memories/DetailPane.vue'
import { useAppStore } from '@/stores/app'
import { useMemoriesStore } from '@/stores/memories'

const app = useAppStore()
const store = useMemoriesStore()
const { total, count } = storeToRefs(store)

onMounted(() => {
  store.bindEvents()
  if (!store.items.length) {
    void store.reload()
  }
})
</script>

<template>
  <div class="h-full flex flex-col min-h-0">
    <!-- Page header -->
    <div class="relative px-8 pt-6 pb-4 overflow-hidden border-b border-shore-line/80">
      <div
        class="pointer-events-none absolute -top-20 -left-20 h-56 w-[520px] blur-[100px] opacity-30"
        style="background: radial-gradient(closest-side, rgba(124,92,255,0.45), transparent 70%)"
      />
      <div class="relative flex items-end justify-between gap-6">
        <div class="min-w-0">
          <h1 class="font-display text-[24px] leading-tight tracking-tight text-ink-1">
            记忆库
          </h1>
          <p class="mt-1 text-[12.5px] text-ink-3">
            浏览、筛选与维护 Agent <span class="text-ink-2">{{ app.agentId }}</span> 的长期记忆
          </p>
        </div>
        <div class="flex items-center gap-2 shrink-0">
          <PBadge tone="accent" size="sm" dot>Agent · {{ app.agentId }}</PBadge>
          <PBadge tone="ink" size="sm">
            <span class="tabular text-ink-1">{{ count }}</span>
            <span class="mx-1 text-ink-5">/</span>
            <span class="tabular">{{ total }}</span>
          </PBadge>
        </div>
      </div>
    </div>

    <!-- Filter bar -->
    <FilterBar />

    <!-- Split -->
    <div class="flex-1 min-h-0 grid grid-cols-12">
      <div class="col-span-12 xl:col-span-7 min-h-0 flex flex-col border-r border-shore-line/80">
        <MemoryList />
      </div>
      <div class="col-span-12 xl:col-span-5 min-h-0 flex flex-col">
        <DetailPane />
      </div>
    </div>
  </div>
</template>
