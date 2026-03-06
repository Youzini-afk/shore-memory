<template>
  <div class="pet-notification-container">
    <TransitionGroup name="pet-list" tag="div">
      <div
        v-for="notification in notifications"
        :key="notification.id"
        class="pet-notification-item"
        :class="notification.type"
      >
        <div class="pet-notif-header">
          <span v-if="notification.type === 'error'" class="pet-notif-icon">
            <PixelIcon name="alert" size="sm" animation="pulse" class="text-rose-500" />
          </span>
          <span v-else-if="notification.type === 'success'" class="pet-notif-icon">
            <PixelIcon name="check" size="sm" animation="bounce" class="text-emerald-500" />
          </span>
          <span v-else class="pet-notif-icon">
            <PixelIcon name="info" size="sm" class="text-sky-500" />
          </span>
          <span class="pet-notif-title">{{ notification.title }}</span>
          <button class="pet-notif-close" @click="remove(notification.id)">
            <PixelIcon name="close" size="xs" />
          </button>
        </div>
        <div class="pet-notif-body">
          {{ notification.message }}
        </div>
        <div v-if="notification.duration > 0" class="pet-notif-progress">
          <div
            class="progress-bar"
            :style="{ animationDuration: notification.duration + 'ms' }"
          ></div>
        </div>
      </div>
    </TransitionGroup>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { listen } from '@/utils/ipcAdapter'
import PixelIcon from './PixelIcon.vue'

const notifications = ref([])
let nextId = 0
let unlistenFn = null

const add = (message, type = 'info', title = '', duration = 8000) => {
  const id = nextId++
  notifications.value.push({ id, message, type, title, duration })

  if (duration > 0) {
    setTimeout(() => {
      remove(id)
    }, duration)
  }
}

defineExpose({
  add
})

const remove = (id) => {
  const index = notifications.value.findIndex((n) => n.id === id)
  if (index !== -1) {
    notifications.value.splice(index, 1)
  }
}

onMounted(async () => {
  // 监听系统级错误 (与 Dashboard 同步)
  unlistenFn = await listen('system-error', (event) => {
    let msg = ''
    let title = '系统提示'
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

    // 如果没有 title，尝试推断
    if (title === '系统警告' || title === '系统错误') {
      if (msg.includes('Python')) title = '后端错误'
      else if (msg.includes('NapCat')) title = 'NapCat 错误'
      else if (msg.includes('WebView2')) title = '运行时错误'
    }

    add(msg, type, title, 10000)
  })
})

onUnmounted(() => {
  if (unlistenFn) unlistenFn()
})
</script>

<style scoped>
.pet-notification-container {
  position: fixed;
  bottom: 20px;
  right: 20px;
  z-index: 10000;
  display: flex;
  flex-direction: column-reverse; /* 新消息在底部，向上堆叠 */
  gap: 10px;
  pointer-events: none;
  width: 300px;
}

.pet-notification-item {
  background: rgba(15, 15, 20, 0.85);
  backdrop-filter: blur(8px);
  border-left: 3px solid #888;
  color: #eee;
  padding: 0;
  border-radius: 4px;
  box-shadow: 0 4px 15px rgba(0, 0, 0, 0.4);
  pointer-events: auto;
  overflow: hidden;
  font-family: 'JetBrains Mono', 'Consolas', monospace;
  font-size: 12px;
  /* 增加轻微文字阴影以柔化边缘，使其看起来不那么刺眼 */
  text-shadow: 0 0 0.2px rgba(255, 255, 255, 0.1);
  transition: all 0.3s ease;
  transform-origin: bottom right;
}

.pet-notification-item.error {
  border-left-color: #ff4757;
  box-shadow: 0 0 10px rgba(255, 71, 87, 0.1);
}
.pet-notification-item.success {
  border-left-color: #2ed573;
}
.pet-notification-item.info {
  border-left-color: #1e90ff;
}

.pet-notif-header {
  display: flex;
  align-items: center;
  padding: 8px 10px;
  background: rgba(255, 255, 255, 0.05);
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
}

.pet-notif-icon {
  margin-right: 8px;
  font-size: 14px;
}

.pet-notif-title {
  flex: 1;
  font-weight: bold;
  opacity: 0.9;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.pet-notif-close {
  background: none;
  border: none;
  color: #aaa;
  cursor: pointer;
  font-size: 16px;
  line-height: 1;
  padding: 0 4px;
}
.pet-notif-close:hover {
  color: #fff;
}

.pet-notif-body {
  padding: 10px;
  line-height: 1.4;
  opacity: 0.8;
  word-break: break-all;
  max-height: 100px;
  overflow-y: auto;
}

/* 进度条动画 */
.pet-notif-progress {
  height: 2px;
  background: rgba(255, 255, 255, 0.1);
  width: 100%;
}
.progress-bar {
  height: 100%;
  background: currentColor; /* 使用当前字体颜色，会被父级的 color 覆盖? 不会，需指定 */
  width: 100%;
  transform-origin: left;
  animation: progress linear forwards;
}
.pet-notification-item.error .progress-bar {
  background: #ff4757;
}
.pet-notification-item.success .progress-bar {
  background: #2ed573;
}
.pet-notification-item.info .progress-bar {
  background: #1e90ff;
}

@keyframes progress {
  from {
    transform: scaleX(1);
  }
  to {
    transform: scaleX(0);
  }
}

/* 列表过渡动画 */
.pet-list-enter-active,
.pet-list-leave-active {
  transition: all 0.3s ease;
}
.pet-list-enter-from {
  opacity: 0;
  transform: translateX(30px) scale(0.9);
}
.pet-list-leave-to {
  opacity: 0;
  transform: translateX(30px);
}
</style>
