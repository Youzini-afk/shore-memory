<template>
  <div class="notification-container">
    <TransitionGroup name="list" tag="div">
      <div
        v-for="notification in notifications"
        :key="notification.id"
        class="notification-item"
        :class="notification.type"
      >
        <div class="icon">
          <span v-if="notification.type === 'error'">⚠️</span>
          <span v-else-if="notification.type === 'success'">✅</span>
          <span v-else>ℹ️</span>
        </div>
        <div class="content">
          <div v-if="notification.title" class="title">{{ notification.title }}</div>
          <div class="message">{{ notification.message }}</div>
        </div>
        <button class="close-btn" @click="remove(notification.id)">×</button>
      </div>
    </TransitionGroup>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { listen } from '@/utils/ipcAdapter'

const notifications = ref([])
let nextId = 0
let unlistenFn = null

const add = (message, type = 'info', title = '', duration = 5000) => {
  const id = nextId++
  notifications.value.push({ id, message, type, title })

  if (duration > 0) {
    setTimeout(() => {
      remove(id)
    }, duration)
  }
}

const remove = (id) => {
  const index = notifications.value.findIndex((n) => n.id === id)
  if (index !== -1) {
    notifications.value.splice(index, 1)
  }
}

onMounted(async () => {
  // 监听系统级错误
  unlistenFn = await listen('system-error', (event) => {
    // 兼容多种 payload 格式
    // 1. 如果 event 是字符串，直接作为 msg
    // 2. 如果 event 是对象，优先取 payload 或 message，以及 title/type

    let msg = ''
    let title = '系统错误'
    let type = 'error'

    if (typeof event === 'string') {
      msg = event
    } else if (typeof event === 'object' && event !== null) {
      msg = event.payload || event.message || JSON.stringify(event)
      if (event.title) title = event.title
      if (event.type) type = event.type
    } else {
      msg = String(event)
    }

    // 简单的关键词分类 (仅当 title 为默认值时尝试智能推断)
    if (title === '系统错误') {
      if (msg.includes('Python')) title = 'Python 后端异常'
      else if (msg.includes('NapCat')) title = 'NapCat 异常'
      else if (msg.includes('WebView2')) title = 'WebView2 组件异常'
      else if (msg.includes('DLL')) title = '系统组件缺失'
    }

    add(msg, type, title, 10000) // 错误停留 10秒
  })
})

onUnmounted(() => {
  if (unlistenFn) unlistenFn()
})

// 暴露给全局
window.$notify = add
</script>

<style scoped>
.notification-container {
  position: fixed;
  top: 20px;
  right: 20px;
  z-index: 9999;
  display: flex;
  flex-direction: column;
  gap: 10px;
  pointer-events: none; /* 允许点击穿透 */
  max-width: 400px;
  width: 100%;
}

.notification-item {
  background: rgba(30, 30, 30, 0.9);
  backdrop-filter: blur(10px);
  color: white;
  padding: 12px 16px;
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
  display: flex;
  align-items: flex-start;
  gap: 12px;
  pointer-events: auto; /* 恢复点击 */
  border-left: 4px solid #888;
  font-family: 'Segoe UI', sans-serif;
  font-size: 14px;
}

.notification-item.error {
  border-left-color: #ff4d4f;
  background: rgba(40, 10, 10, 0.95);
}

.notification-item.success {
  border-left-color: #52c41a;
  background: rgba(10, 40, 10, 0.95);
}

.icon {
  font-size: 18px;
  flex-shrink: 0;
  margin-top: 2px;
}

.content {
  flex: 1;
  word-break: break-word;
}

.title {
  font-weight: bold;
  margin-bottom: 4px;
  font-size: 15px;
}

.message {
  line-height: 1.4;
  opacity: 0.9;
}

.close-btn {
  background: transparent;
  border: none;
  color: #aaa;
  cursor: pointer;
  font-size: 18px;
  padding: 0;
  line-height: 1;
  margin-top: 2px;
}

.close-btn:hover {
  color: white;
}

/* 过渡动画 */
.list-enter-active,
.list-leave-active {
  transition: all 0.3s ease;
}

.list-enter-from {
  opacity: 0;
  transform: translateX(30px);
}

.list-leave-to {
  opacity: 0;
  transform: translateY(-30px);
}
</style>
