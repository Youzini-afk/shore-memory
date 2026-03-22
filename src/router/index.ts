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
// 这样后续打开 Dashboard / Pet3DView 等窗口时可以秒开
router.isReady().then(() => {
  setTimeout(() => {
    const currentPath = router.currentRoute.value.path
    console.log(`[路由预取] 当前路由: ${currentPath}，开始后台预取其他路由...`)

    // 预取当前路由以外的重型组件
    const prefetchMap: Record<string, () => Promise<any>> = {
      '/dashboard': DashboardView,
      '/pet-3d': Pet3DView,
      '/ide': MainWindow,
      '/launcher': LauncherView,
      '/stronghold': StrongholdView
    }

    for (const [path, loader] of Object.entries(prefetchMap)) {
      if (path !== currentPath) {
        loader().catch(() => {
          // 静默忽略预取失败（可能是网络问题或模块不存在）
        })
      }
    }
  }, 3000) // 延迟 3 秒，避免与初始加载抢资源
})

export default router
