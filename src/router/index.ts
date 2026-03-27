import { createRouter, createWebHashHistory, type RouteRecordRaw } from 'vue-router'

// 懒加载路由组件 - 只有访问到对应路由时才加载对应组件
const LauncherView = () => import('../views/LauncherView.vue')
const Pet3DView = () => import('../views/Pet3DView.vue')
const DashboardView = () => import('../views/DashboardView.vue')
const MainWindow = () => import('../views/MainWindow.vue')
const StrongholdView = () => import('../views/StrongholdView.vue')
const BedrockAvatar = () => import('../components/avatar/BedrockAvatar.vue')

const routes: RouteRecordRaw[] = [
  { path: '/', redirect: '/launcher' },
  { path: '/launcher', component: LauncherView },
  { path: '/ide', component: MainWindow },
  { path: '/stronghold', component: StrongholdView },
  { path: '/pet-3d', component: Pet3DView },
  { path: '/dashboard', component: DashboardView },
  { path: '/test-3d', component: BedrockAvatar }
]

const router = createRouter({
  history: createWebHashHistory(),
  routes
})

router.beforeEach((to, from, next) => {
  console.log(`[路由] 正在从 ${from.path} 导航到 ${to.path}`)

  // Docker 模式重定向
  if (!window.electron && to.path === '/launcher') {
    next('/dashboard')
    return
  }

  next()
})

// [优化] 后台预取其他路由 chunk，预热 Vite 编译缓存和 Electron HTTP 缓存
// [注意] 开发模式下禁用预取，避免同时加载多个重型组件抢占 Vite 编译线程
router.isReady().then(() => {
  if (import.meta.env.DEV) {
    console.log('[路由预取] 开发模式，跳过预取')
    return
  }

  setTimeout(() => {
    const currentPath = router.currentRoute.value.path
    console.log(`[路由预取] 当前路由: ${currentPath}，开始后台预取其他路由...`)

    const prefetchMap: Record<string, () => Promise<any>> = {
      '/dashboard': DashboardView,
      '/pet-3d': Pet3DView,
      '/ide': MainWindow,
      '/launcher': LauncherView,
      '/stronghold': StrongholdView
    }

    for (const [path, loader] of Object.entries(prefetchMap)) {
      if (path !== currentPath) {
        loader().catch(() => {})
      }
    }
  }, 3000)
})

export default router
