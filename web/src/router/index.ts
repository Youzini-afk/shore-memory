import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'

const routes: RouteRecordRaw[] = [
  { path: '/', redirect: '/recall' },
  {
    path: '/recall',
    name: 'recall',
    component: () => import('@/views/RecallView.vue'),
    meta: { title: '召回实验台' }
  },
  {
    path: '/memories',
    name: 'memories',
    component: () => import('@/views/MemoriesView.vue'),
    meta: { title: '记忆库' }
  },
  {
    path: '/graph',
    name: 'graph',
    component: () => import('@/views/GraphView.vue'),
    meta: { title: '记忆图谱' }
  },
  {
    path: '/agent',
    name: 'agent',
    component: () => import('@/views/AgentView.vue'),
    meta: { title: 'Agent 状态' }
  },
  {
    path: '/maintenance',
    name: 'maintenance',
    component: () => import('@/views/MaintenanceView.vue'),
    meta: { title: '运维' }
  },
  {
    path: '/settings',
    name: 'settings',
    component: () => import('@/views/SettingsView.vue'),
    meta: { title: '设置' }
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
  document.title = `${title} · Shore Memory 控制台`
})

export default router
