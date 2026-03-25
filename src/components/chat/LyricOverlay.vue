<template>
  <transition name="lyric-fade">
    <div
      v-if="visible"
      ref="lyricRef"
      class="lyric-overlay-container fixed z-[1000] pointer-events-auto select-none group"
      :style="{
        left: position.x + 'px',
        top: position.y + 'px',
        transform: 'translateX(-50%)'
      }"
      @mousedown="startDrag"
    >
      <!-- 拖拽句柄 (平时隐藏，Hover 显示) -->
      <div class="drag-handle opacity-0 group-hover:opacity-100 transition-opacity">
        <PixelIcon name="grip-horizontal" size="xs" />
      </div>

      <div class="lyric-bar">
        <!-- 思考状态 -->
        <div v-if="isThinking" class="lyric-thinking flex items-center gap-3 px-2">
          <div class="thinking-dots">
            <div class="dot"></div>
            <div class="dot"></div>
            <div class="dot"></div>
          </div>
          <span class="text-xs font-bold text-white/90 tracking-widest">{{ thinkingMessage }}</span>
        </div>

        <!-- 文字内容 -->
        <div v-else class="lyric-text-container">
          <div class="lyric-text" :title="text">
            {{ text }}
          </div>
        </div>
      </div>
    </div>
  </transition>
</template>

<script setup lang="ts">
import { ref, watch, onMounted, onUnmounted } from 'vue'
import PixelIcon from '../ui/PixelIcon.vue'

const props = defineProps<{
  text: string
  isThinking: boolean
  thinkingMessage?: string
  duration?: number
}>()

const visible = ref(false)
const position = ref({ x: window.innerWidth / 2, y: window.innerHeight - 100 })
const lyricRef = ref<HTMLElement | null>(null)

let fadeTimer: NodeJS.Timeout | null = null
let isDragging = false
let startX = 0
let startY = 0
let initialX = 0
let initialY = 0

// 加载位置持久化
onMounted(() => {
  const saved = localStorage.getItem('ppc.lyric_pos')
  if (saved) {
    try {
      const pos = JSON.parse(saved)
      position.value = pos
    } catch (e) {
      console.error('加载歌词位置失败:', e)
    }
  } else {
    // 默认位置：底部居中
    position.value = { x: window.innerWidth / 2, y: window.innerHeight - 80 }
  }

  // 初始化显示逻辑
  if (props.text || props.isThinking) {
    visible.value = true
    if (!props.isThinking) startFadeTimer()
  }
})

// 监听文字变化
watch(
  () => props.text,
  (newVal) => {
    if (newVal) {
      visible.value = true
      if (!props.isThinking) startFadeTimer()
    }
  }
)

// 监听思考状态
watch(
  () => props.isThinking,
  (newVal) => {
    if (newVal) {
      visible.value = true
      if (fadeTimer) clearTimeout(fadeTimer)
    } else {
      // 思考结束，开始淡出倒计时
      startFadeTimer()
    }
  }
)

const startFadeTimer = () => {
  if (fadeTimer) clearTimeout(fadeTimer)
  const waitTime = props.duration || 5000
  fadeTimer = setTimeout(() => {
    visible.value = false
  }, waitTime)
}

// 拖拽逻辑
const startDrag = (e: MouseEvent) => {
  isDragging = true
  startX = e.clientX
  startY = e.clientY
  initialX = position.value.x
  initialY = position.value.y

  document.addEventListener('mousemove', handleDrag)
  document.addEventListener('mouseup', stopDrag)

  // 拖拽时取消淡出
  if (fadeTimer) clearTimeout(fadeTimer)
}

const handleDrag = (e: MouseEvent) => {
  if (!isDragging) return
  const dx = e.clientX - startX
  const dy = e.clientY - startY

  // 限制在屏幕范围内
  let newX = initialX + dx
  let newY = initialY + dy

  newX = Math.max(100, Math.min(window.innerWidth - 100, newX))
  newY = Math.max(40, Math.min(window.innerHeight - 40, newY))

  position.value = { x: newX, y: newY }
}

const stopDrag = () => {
  if (!isDragging) return
  isDragging = false
  localStorage.setItem('ppc.lyric_pos', JSON.stringify(position.value))
  document.removeEventListener('mousemove', handleDrag)
  document.removeEventListener('mouseup', stopDrag)

  // 停止拖拽后重新开始淡出
  if (!props.isThinking) startFadeTimer()
}

onUnmounted(() => {
  if (fadeTimer) clearTimeout(fadeTimer)
  document.removeEventListener('mousemove', handleDrag)
  document.removeEventListener('mouseup', stopDrag)
})
</script>

<style scoped>
.lyric-bar {
  background: transparent;
  backdrop-filter: none;
  border: none;
  padding: 20px 40px; /* 增加上下边距，防止发光被切断 */
  width: max-content; /* 宽度随内容撑开 */
  max-width: 90vw; /* 最大不超过屏幕 90% */
  box-shadow: none;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  overflow: visible; /* 确保发光效果不被切断 */
}

.lyric-text {
  font-family: 'ZCOOL KuaiLe', 'PingFang SC', 'Microsoft YaHei', sans-serif;
  font-size: 1.8rem; /* 再次调大一点点，更显可爱 */
  font-weight: 400; /* ZCOOL KuaiLe 不需要太粗，本身就很圆润 */
  color: #ffffff;
  /* 融合 Wiki 的描边阴影与歌词的外发光 */
  text-shadow:
    0 0 15px rgba(249, 168, 212, 0.8),
    0 0 30px rgba(249, 168, 212, 0.4),
    3px 3px 0 rgba(45, 27, 30, 0.2);
  white-space: pre-wrap;
  word-break: break-all;
  text-align: center;
  letter-spacing: 0.05em; /* 快乐体间距不用太宽，紧凑点更可爱 */
  line-height: 1.4;
  padding: 15px 0;
  animation: text-float 3s infinite ease-in-out;
  filter: drop-shadow(0 0 2px rgba(255, 255, 255, 0.5)); /* 增加一层朦胧感 */
}

@keyframes moe-bounce {
  0%,
  100% {
    transform: scale(1) rotate(0deg);
  }
  50% {
    transform: scale(1.2) rotate(15deg);
  }
}

@keyframes text-float {
  0%,
  100% {
    transform: translateY(0);
  }
  50% {
    transform: translateY(-2px);
  }
}

.drag-handle {
  position: absolute;
  top: -18px;
  left: 50%;
  transform: translateX(-50%);
  background: rgba(30, 41, 59, 0.8);
  padding: 4px 12px;
  border-radius: 6px;
  cursor: grab;
  color: #f9a8d4;
  border: 1px solid rgba(255, 255, 255, 0.1);
  box-shadow: 0 4px 10px rgba(0, 0, 0, 0.2);
}

.drag-handle:active {
  cursor: grabbing;
}

/* 思考点动画 */
.thinking-dots {
  display: flex;
  gap: 4px;
}

.dot {
  width: 6px;
  height: 6px;
  background: #f9a8d4;
  border-radius: 50%;
  animation: dot-wave 1.5s infinite ease-in-out;
}

.dot:nth-child(2) {
  animation-delay: 0.2s;
}
.dot:nth-child(3) {
  animation-delay: 0.4s;
}

@keyframes dot-wave {
  0%,
  100% {
    transform: translateY(0);
    opacity: 0.4;
  }
  50% {
    transform: translateY(-4px);
    opacity: 1;
  }
}

.lyric-fade-enter-active {
  transition: all 0.6s cubic-bezier(0.34, 1.56, 0.64, 1);
}
.lyric-fade-leave-active {
  transition: all 2.5s cubic-bezier(0.4, 0, 0.2, 1); /* 缓慢平滑淡出 */
}

.lyric-fade-enter-from,
.lyric-fade-leave-to {
  opacity: 0;
  transform: translateX(-50%) translateY(30px) scale(0.9);
  filter: blur(15px);
}
</style>
