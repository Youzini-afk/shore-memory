import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'

const routes: RouteRecordRaw[] = [
  { path: '/', redirect: '/recall' },
  {
    path: '/recall',
    name: 'recall',
    component: () => import('@/views/RecallView.vue'),
    meta: { title: 'Recall Playground' }
  },
  {
    path: '/memories',
    name: 'memories',
    component: () => import('@/views/MemoriesView.vue'),
    meta: { title: 'Memories' }
  },
  {
    path: '/graph',
    name: 'graph',
    component: () => import('@/views/GraphView.vue'),
    meta: { title: 'Memory Graph' }
  },
  {
    path: '/agent',
    name: 'agent',
    component: () => import('@/views/AgentView.vue'),
    meta: { title: 'Agent' }
  },
  {
    path: '/maintenance',
    name: 'maintenance',
    component: () => import('@/views/MaintenanceView.vue'),
    meta: { title: 'Maintenance' }
  },
  {
    path: '/settings',
    name: 'settings',
    component: () => import('@/views/SettingsView.vue'),
    meta: { title: 'Settings' }
  },
  {
    path: '/:catchAll(.*)*',
    redirect: '/recall'
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior() {
    return { top: 0 }
  }
})

router.afterEach((to) => {
  const title = (to.meta?.title as string | undefined) ?? 'Shore Memory'
  document.title = `${title} · Shore Memory Console`
})

export default router
