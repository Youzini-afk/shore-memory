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

// 全局错误处理
app.config.errorHandler = (err, instance, info) => {
  console.error('[Vue 错误]', err)
  console.error('[Vue 错误信息]', info)
}

app.use(router)
app.mount('#app')
