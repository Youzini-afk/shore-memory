import { createApp } from 'vue'
import { loader } from '@guolao/vue-monaco-editor'
import App from './App.vue'
import router from './router'
import './style.css'

// 配置 Monaco Editor 中文支持
loader.config({
  'vs/nls': {
    availableLanguages: {
      '*': 'zh-cn'
    }
  }
})

const app = createApp(App)

import { invoke } from '@/utils/ipcAdapter'

// 全局错误处理
app.config.errorHandler = (err: any, instance, info) => {
  const errMsg = `[Vue 错误] ${err?.message || err} | Info: ${info}`
  console.error(errMsg, err)
  // 转发给主进程诊断
  invoke('system_error_log', errMsg + '\n' + (err?.stack || ''))
    .catch(() => {}) // 忽略 IPC 失败
}

window.addEventListener('error', (event) => {
  const errMsg = `[Window 错误] ${event.message} at ${event.filename}:${event.lineno}`
  console.error(errMsg)
  invoke('system_error_log', errMsg + '\n' + (event.error?.stack || ''))
    .catch(() => {})
})

window.addEventListener('unhandledrejection', (event) => {
  const errMsg = `[Promise 未处理拒绝] ${event.reason}`
  console.error(errMsg)
  invoke('system_error_log', errMsg + '\n' + (event.reason?.stack || ''))
    .catch(() => {})
})

app.use(router)
app.mount('#app')
