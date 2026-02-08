<template>
  <transition name="modal-fade">
    <div v-if="visible" class="file-search-modal" @click.self="close">
      <div class="modal-content" :style="modalStyle">
        <div class="modal-header" @mousedown="startDragHeader">
          <div class="header-title">
            <span class="header-icon">🔍</span>
            <h3>找到的文件 ({{ files.length }})</h3>
          </div>
          <button class="close-btn" title="关闭 (Esc)" @click.stop="close">×</button>
        </div>

        <div class="file-list-container custom-scrollbar">
          <div v-if="files.length > 0" class="file-list">
            <div
              v-for="(file, index) in files"
              :key="index"
              class="file-item"
              @click="openFile(file)"
            >
              <div class="file-info">
                <span class="file-type-icon">{{ getFileIcon(file) }}</span>
                <div class="file-details">
                  <div class="file-name">{{ getFileName(file) }}</div>
                  <div class="file-path">{{ file }}</div>
                </div>
              </div>
              <div class="item-action">
                <span class="action-hint">点击打开目录</span>
              </div>
            </div>
          </div>

          <div v-else class="empty-state">
            <div class="empty-icon">📂</div>
            <p>没有找到相关文件</p>
          </div>
        </div>

        <div class="modal-footer">
          <p class="footer-hint">提示：点击文件项可直接在资源管理器中定位</p>
          <button class="footer-close-btn" @click="close">确定</button>
        </div>
      </div>
    </div>
  </transition>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, reactive } from 'vue'
import { API_BASE } from '../config'

const props = defineProps({
  visible: {
    type: Boolean,
    default: false
  },
  files: {
    type: Array,
    default: () => []
  }
})

const emit = defineEmits(['update:visible'])

// 拖动逻辑
const position = reactive({
  x: 0,
  y: 0,
  isDragging: false,
  startX: 0,
  startY: 0
})

const modalStyle = computed(() => {
  if (position.x === 0 && position.y === 0) return {}
  return {
    transform: `translate(${position.x}px, ${position.y}px)`,
    transition: position.isDragging ? 'none' : 'transform 0.3s ease'
  }
})

const startDragHeader = (e) => {
  // 仅左键拖动
  if (e.button !== 0) return

  position.isDragging = true
  position.startX = e.clientX - position.x
  position.startY = e.clientY - position.y

  window.addEventListener('mousemove', onDrag)
  window.addEventListener('mouseup', stopDrag)

  // 防止文本选中
  e.preventDefault()
}

const onDrag = (e) => {
  if (!position.isDragging) return
  position.x = e.clientX - position.startX
  position.y = e.clientY - position.startY
}

const stopDrag = () => {
  position.isDragging = false
  window.removeEventListener('mousemove', onDrag)
  window.removeEventListener('mouseup', stopDrag)
}

const close = () => {
  // 重置位置
  position.x = 0
  position.y = 0
  emit('update:visible', false)
}

// 快捷键支持
const handleEsc = (e) => {
  if (e.key === 'Escape' && props.visible) {
    close()
  }
}

onMounted(() => {
  window.addEventListener('keydown', handleEsc)
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleEsc)
})

const getFileName = (path) => {
  const parts = path.split(/[\\/]/)
  return parts[parts.length - 1] || path
}

const getFileIcon = (path) => {
  const ext = path.split('.').pop().toLowerCase()
  const icons = {
    pdf: '📕',
    doc: '📘',
    docx: '📘',
    xls: '📗',
    xlsx: '📗',
    png: '🖼️',
    jpg: '🖼️',
    jpeg: '🖼️',
    gif: '🖼️',
    txt: '📄',
    log: '📝',
    zip: '📦',
    rar: '📦',
    exe: '⚙️'
  }
  return icons[ext] || '📄'
}

const openFile = async (path) => {
  try {
    // 确保路径中的反斜杠被正确处理
    const sanitizedPath = path.replace(/\\/g, '/')
    console.log('[FileSearchModal] 尝试打开路径:', sanitizedPath)

    const response = await fetch(`${API_BASE}/open-path`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ path: sanitizedPath })
    })

    if (!response.ok) {
      const errData = await response.json()
      throw new Error(errData.detail || `HTTP 错误! 状态码: ${response.status}`)
    }

    console.log('[FileSearchModal] 成功打开路径')
  } catch (error) {
    console.error('打开文件失败:', error)
    alert('无法打开目录: ' + error.message)
  }
}
</script>

<style scoped>
.file-search-modal {
  position: fixed;
  top: 0;
  left: 0;
  width: 100vw;
  height: 100vh;
  background: transparent; /* 移除全屏半透明背景，避免显示巨大的矩形边框 */
  /* backdrop-filter: blur(4px); */
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 999999;
  pointer-events: auto;
}

.modal-content {
  background: rgba(255, 255, 255, 0.95);
  width: 90%;
  max-width: 600px;
  max-height: 80vh;
  border-radius: 20px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border: 1px solid rgba(255, 255, 255, 0.3);
  animation: modal-pop 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
  pointer-events: auto;
}

@keyframes modal-pop {
  from {
    transform: scale(0.9) translate(0, 0);
    opacity: 0;
  }
  to {
    transform: scale(1) translate(var(--tw-translate-x, 0), var(--tw-translate-y, 0));
    opacity: 1;
  }
}

.modal-header {
  padding: 20px 24px;
  background: linear-gradient(to right, #f8f9fa, #ffffff);
  border-bottom: 1px solid rgba(0, 0, 0, 0.05);
  display: flex;
  justify-content: space-between;
  align-items: center;
  cursor: grab;
}

.modal-header:active {
  cursor: grabbing;
}

.header-title {
  display: flex;
  align-items: center;
  gap: 12px;
  pointer-events: none; /* 让点击穿透到 header 处理拖拽 */
}

.header-icon {
  font-size: 1.4em;
}

.header-title h3 {
  margin: 0;
  font-size: 1.2rem;
  color: #2c3e50;
  font-weight: 600;
}

.close-btn {
  background: #f1f3f5;
  border: none;
  width: 32px;
  height: 32px;
  border-radius: 50%;
  font-size: 20px;
  cursor: pointer;
  color: #adb5bd;
  display: flex;
  justify-content: center;
  align-items: center;
  transition: all 0.2s;
  pointer-events: auto;
}

.close-btn:hover {
  background: #ff6b6b;
  color: white;
  transform: rotate(90deg);
}

.file-list-container {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  background: #ffffff;
}

/* 自定义滚动条 */
.custom-scrollbar::-webkit-scrollbar {
  width: 8px;
}

.custom-scrollbar::-webkit-scrollbar-track {
  background: #f1f1f1;
  border-radius: 4px;
}

.custom-scrollbar::-webkit-scrollbar-thumb {
  background: #ccc;
  border-radius: 4px;
}

.custom-scrollbar::-webkit-scrollbar-thumb:hover {
  background: #aaa;
}

.file-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.file-item {
  padding: 14px 18px;
  background: #f8f9fa;
  border-radius: 12px;
  cursor: pointer;
  display: flex;
  justify-content: space-between;
  align-items: center;
  transition: all 0.2s;
  border: 1px solid rgba(0, 0, 0, 0.03);
}

.file-item:hover {
  background: #f0f4ff;
  border-color: #d0e2ff;
  transform: translateX(4px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
}

.file-info {
  display: flex;
  align-items: center;
  gap: 15px;
  overflow: hidden;
}

.file-type-icon {
  font-size: 1.8em;
  flex-shrink: 0;
}

.file-details {
  overflow: hidden;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.file-name {
  font-weight: 600;
  color: #2c3e50;
  font-size: 0.95rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.file-path {
  font-size: 0.75rem;
  color: #7f8c8d;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  direction: rtl; /* 从右往左显示，方便看文件名末尾 */
  text-align: left;
}

.item-action {
  flex-shrink: 0;
  opacity: 0;
  transition: opacity 0.2s;
}

.file-item:hover .item-action {
  opacity: 1;
}

.action-hint {
  font-size: 0.75rem;
  color: #3498db;
  font-weight: 500;
  padding: 4px 8px;
  background: #ebf5fb;
  border-radius: 6px;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 0;
  color: #95a5a6;
}

.empty-icon {
  font-size: 4rem;
  margin-bottom: 15px;
  opacity: 0.5;
}

.modal-footer {
  padding: 16px 24px;
  background: #f8f9fa;
  border-top: 1px solid rgba(0, 0, 0, 0.05);
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.footer-hint {
  font-size: 0.8rem;
  color: #95a5a6;
  margin: 0;
}

.footer-close-btn {
  padding: 8px 24px;
  background: #3498db;
  color: white;
  border: none;
  border-radius: 10px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

.footer-close-btn:hover {
  background: #2980b9;
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(52, 152, 219, 0.3);
}

.footer-close-btn:active {
  transform: translateY(0);
}

/* 动画 */
.modal-fade-enter-active,
.modal-fade-leave-active {
  transition: opacity 0.3s;
}
.modal-fade-enter-from,
.modal-fade-leave-to {
  opacity: 0;
}
</style>
