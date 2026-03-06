<template>
  <transition name="modal-fade">
    <div v-if="visible" class="file-search-modal pixel-ui" @click.self="close">
      <div
        class="modal-content pixel-border-moe bg-white/95 backdrop-blur-md shadow-xl"
        :style="modalStyle"
      >
        <div
          class="modal-header bg-moe-pink/10 border-b-2 border-moe-pink/20"
          @mousedown="startDragHeader"
        >
          <div class="header-title text-moe-cocoa">
            <span class="header-icon animate-bounce">🔍</span>
            <h3 class="font-bold pixel-font">找到的文件 ({{ files.length }})</h3>
          </div>
          <button
            class="close-btn text-moe-pink hover:text-moe-cocoa transition-colors"
            title="关闭 (Esc)"
            @click.stop="close"
          >
            <PixelIcon name="x" size="sm" />
          </button>
        </div>

        <div class="file-list-container custom-scrollbar">
          <div v-if="files.length > 0" class="file-list p-2 space-y-2">
            <div
              v-for="(file, index) in files"
              :key="index"
              class="file-item group pixel-border-sm-transparent hover:pixel-border-sm-moe hover:bg-moe-sky/5 transition-all duration-200 cursor-pointer p-2 relative overflow-hidden"
              @click="openFile(file)"
            >
              <div class="file-info flex items-center gap-3 relative z-10">
                <span class="file-type-icon text-xl group-hover:scale-110 transition-transform">{{
                  getFileIcon(file)
                }}</span>
                <div class="file-details flex-1 min-w-0">
                  <div class="file-name text-sm font-bold text-moe-cocoa truncate">
                    {{ getFileName(file) }}
                  </div>
                  <div class="file-path text-xs text-moe-cocoa/50 truncate font-mono">
                    {{ file }}
                  </div>
                </div>
              </div>
              <div
                class="item-action absolute right-2 top-1/2 -translate-y-1/2 opacity-0 group-hover:opacity-100 transition-opacity"
              >
                <span
                  class="action-hint text-[10px] bg-moe-sky text-white px-2 py-1 pixel-border-sm"
                  >打开</span
                >
              </div>
            </div>
          </div>

          <div
            v-else
            class="empty-state flex flex-col items-center justify-center h-40 text-moe-cocoa/40"
          >
            <div class="empty-icon text-4xl mb-2 opacity-50">📂</div>
            <p class="text-sm pixel-font">没有找到相关文件</p>
          </div>
        </div>

        <div
          class="modal-footer border-t-2 border-moe-pink/10 bg-moe-pink/5 p-3 flex justify-between items-center"
        >
          <p class="footer-hint text-[10px] text-moe-cocoa/60">
            提示：点击文件项可直接在资源管理器中定位
          </p>
          <button
            class="footer-close-btn px-4 py-1.5 bg-moe-pink text-white text-xs font-bold pixel-border-sm hover:bg-moe-pink/90 press-effect transition-all"
            @click="close"
          >
            确定
          </button>
        </div>
      </div>
    </div>
  </transition>
</template>

<script setup>
import { computed, onMounted, onUnmounted, reactive } from 'vue'
import { API_BASE } from '../../config'

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
  background: transparent;
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 999999;
  pointer-events: auto;
}

.modal-content {
  width: 600px;
  max-height: 80vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.modal-header {
  padding: 12px 16px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  user-select: none;
  cursor: grab;
}

.modal-header:active {
  cursor: grabbing;
}

.header-title {
  display: flex;
  align-items: center;
  gap: 8px;
}

.file-list-container {
  flex: 1;
  overflow-y: auto;
  min-height: 200px;
}
</style>
