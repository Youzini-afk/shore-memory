<template>
  <div class="app-container h-full w-full">
    <div class="main-content h-full w-full">
      <router-view v-slot="{ Component }">
        <keep-alive>
          <component :is="Component" />
        </keep-alive>
      </router-view>
      <NotificationManager />
    </div>
  </div>
</template>

<script setup>
import { onMounted } from 'vue'
import NotificationManager from './components/ui/NotificationManager.vue'
import { gatewayClient } from './api/gateway'

console.log('[App] App.vue 已初始化')

onMounted(() => {
  // 启动网关连接
  gatewayClient.connect()
})

// 全局 JS 错误捕获
window.addEventListener('error', (event) => {
  if (window.$notify) {
    window.$notify(event.message, 'error', '前端异常')
  } else {
    console.error('通知系统未就绪:', event.message)
  }
})

window.addEventListener('unhandledrejection', (event) => {
  if (window.$notify) {
    // Promise 错误通常在 reason 中
    const msg = event.reason ? event.reason.message || String(event.reason) : '未知 Promise 错误'
    window.$notify(msg, 'error', '未捕获的 Promise 异常')
  }
})

// 监听后端系统错误
if (window.electron && window.electron.on) {
  window.electron.on('system-error', (errorMsg) => {
    console.error('[System Error]', errorMsg)
    if (window.$notify) {
      // 格式化错误信息，使其更易读
      let displayMsg = errorMsg
      if (errorMsg.includes('Traceback')) {
        displayMsg = '后端核心发生崩溃，请检查日志。'
      }
      window.$notify(displayMsg, 'error', '系统核心错误', 10000)
    }
  })
}
</script>

<style>
body,
html {
  margin: 0;
  padding: 0;
  width: 100%;
  height: 100%;
  overflow: hidden;
  background-color: transparent !important;
}

#app {
  width: 100%;
  height: 100%;
  background: transparent !important;
}
</style>
