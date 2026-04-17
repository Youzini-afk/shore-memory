<script setup lang="ts">
import { RouterLink } from 'vue-router'
import {
  Search,
  Database,
  Share2,
  UserRound,
  Wrench,
  Settings as SettingsIcon
} from 'lucide-vue-next'
import { useAppStore } from '@/stores/app'
import { computed } from 'vue'

const app = useAppStore()

const items = [
  { name: 'recall', label: 'Recall', to: '/recall', icon: Search, hint: 'Playground' },
  { name: 'memories', label: 'Memories', to: '/memories', icon: Database },
  { name: 'graph', label: 'Graph', to: '/graph', icon: Share2 },
  { name: 'agent', label: 'Agent', to: '/agent', icon: UserRound },
  { name: 'maintenance', label: 'Maintenance', to: '/maintenance', icon: Wrench },
  { name: 'settings', label: 'Settings', to: '/settings', icon: SettingsIcon }
]

const statusLabel = computed(() => {
  const s = app.eventsStatus
  if (s === 'open') return 'Events · Live'
  if (s === 'connecting') return 'Events · 连接中'
  if (s === 'error') return 'Events · 错误'
  if (s === 'lagged') return 'Events · Lagged'
  return 'Events · 未连接'
})

const statusDot = computed(() => {
  const s = app.eventsStatus
  if (s === 'open') return 'bg-state-active'
  if (s === 'lagged') return 'bg-sig-amber'
  if (s === 'connecting') return 'bg-sig-blue animate-pulse'
  if (s === 'error') return 'bg-state-invalidated'
  return 'bg-ink-5'
})
</script>

<template>
  <aside
    class="w-[240px] h-full flex flex-col bg-shore-bg border-r border-shore-line/80 select-none"
  >
    <!-- Logo / Product -->
    <div class="h-14 flex items-center px-5">
      <div class="flex items-center gap-2.5">
        <div
          class="h-7 w-7 rounded-[8px] bg-gradient-to-br from-accent-hi to-accent-lo shadow-accent"
        />
        <div class="leading-tight">
          <div class="text-[13px] font-display font-semibold tracking-tight">
            Shore Memory
          </div>
          <div class="text-[10px] uppercase tracking-[0.18em] text-ink-4 font-display">
            Console
          </div>
        </div>
      </div>
    </div>

    <!-- Nav -->
    <nav class="flex-1 overflow-y-auto px-3 pt-2 pb-4">
      <ul class="flex flex-col gap-0.5">
        <li v-for="item in items" :key="item.name">
          <RouterLink
            :to="item.to"
            class="group relative flex items-center gap-3 rounded-btn px-3 py-2 text-[13px] text-ink-3 hover:text-ink-1 hover:bg-shore-hover transition-colors duration-240 ease-shore"
            active-class="shore-nav-active"
          >
            <span
              class="absolute left-0 top-1/2 -translate-y-1/2 w-[2px] h-5 rounded-full bg-accent opacity-0 group-[.shore-nav-active]:opacity-100 transition-opacity"
            />
            <component
              :is="item.icon"
              class="h-4 w-4 shrink-0 text-ink-4 group-hover:text-ink-2 group-[.shore-nav-active]:text-accent"
              :stroke-width="1.75"
            />
            <span class="truncate">{{ item.label }}</span>
            <span
              v-if="item.hint"
              class="ml-auto text-[10px] font-display uppercase tracking-wider text-ink-5"
              >{{ item.hint }}</span
            >
          </RouterLink>
        </li>
      </ul>
    </nav>

    <!-- Footer -->
    <div class="px-4 py-3 border-t border-shore-line/70 text-[11px] text-ink-4 flex flex-col gap-1.5">
      <div class="flex items-center gap-2">
        <span class="shore-dot" :class="statusDot" />
        <span class="truncate">{{ statusLabel }}</span>
      </div>
      <div class="flex items-center justify-between">
        <span class="tabular">v0.1.0</span>
        <span
          class="tabular"
          :class="app.isHealthy ? 'text-state-active' : 'text-ink-5'"
        >{{ app.isHealthy ? 'OK' : '–' }}</span>
      </div>
    </div>
  </aside>
</template>

<style scoped>
.shore-nav-active {
  color: var(--ink-1);
  background: rgba(124, 92, 255, 0.08);
}
.shore-nav-active :deep(svg) {
  color: var(--accent);
}
</style>
