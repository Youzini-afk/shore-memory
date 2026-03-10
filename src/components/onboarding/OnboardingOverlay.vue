<template>
  <div
    class="fixed inset-0 z-[10000] flex flex-col items-center p-12 transition-all duration-1000 overflow-hidden pointer-events-none"
    :class="[
      isVisible && isAppearing ? 'opacity-100' : 'opacity-0',
      isVisible && isAppearing && !spotlightRect
        ? 'bg-black/40 backdrop-blur-md'
        : 'bg-transparent',
      isDialogAtTop ? 'justify-start pt-32' : 'justify-end pb-12'
    ]"
  >
    <!-- Spotlight Mask (SVG with Hole) 🔦 -->
    <svg v-if="spotlightRect" class="absolute inset-0 w-full h-full pointer-events-none z-0">
      <defs>
        <mask id="spotlight-mask">
          <rect width="100%" height="100%" fill="white" />
          <rect
            :x="spotlightRect.x - 8"
            :y="spotlightRect.y - 8"
            :width="spotlightRect.width + 16"
            :height="spotlightRect.height + 16"
            rx="4"
            fill="black"
          />
        </mask>
      </defs>
      <rect width="100%" height="100%" fill="rgba(0,0,0,0.4)" mask="url(#spotlight-mask)" />

      <!-- Highlight Border -->
      <rect
        :x="spotlightRect.x - 10"
        :y="spotlightRect.y - 10"
        :width="spotlightRect.width + 20"
        :height="spotlightRect.height + 20"
        fill="none"
        stroke="#0ea5e9"
        stroke-width="3"
        stroke-dasharray="8 4"
        class="animate-[pixel-border-dash_2s_linear_infinite]"
        rx="6"
      />
    </svg>

    <!-- Guiding Arrow 🏹 -->
    <div
      v-if="spotlightRect"
      class="absolute z-[10001] pointer-events-none transition-all duration-500"
      :style="{
        top: spotlightRect.y + spotlightRect.height / 2 + 'px',
        left:
          spotlightRect.x < windowWidth / 2
            ? spotlightRect.x + spotlightRect.width + 20 + 'px'
            : spotlightRect.x - 120 + 'px',
        transform: 'translateY(-50%)'
      }"
    >
      <div
        class="flex items-center gap-3"
        :class="spotlightRect.x < windowWidth / 2 ? 'flex-row-reverse' : 'flex-row'"
      >
        <div
          class="px-3 py-1 bg-sky-500 text-white text-[10px] font-black pixel-border-sm font-moe shadow-lg"
          :class="
            spotlightRect.x < windowWidth / 2
              ? 'animate-pixel-bounce-horizontal-right'
              : 'animate-pixel-bounce-horizontal-left'
          "
        >
          点这里喵！
        </div>
        <PixelIcon
          :name="spotlightRect.x < windowWidth / 2 ? 'chevron-left' : 'chevron-right'"
          size="lg"
          class="text-sky-400 drop-shadow-lg"
          :class="
            spotlightRect.x < windowWidth / 2
              ? 'animate-pixel-bounce-horizontal-right'
              : 'animate-pixel-bounce-horizontal-left'
          "
        />
      </div>
    </div>

    <!-- Pero's 2D Sprite (Tachie) -->
    <div
      v-if="currentStep?.expression !== 'none'"
      class="absolute bottom-0 transition-all duration-1000 ease-out z-10"
      :class="[
        isAppearing ? 'opacity-100 scale-100' : 'translate-y-40 opacity-0 scale-95',
        !spotlightRect
          ? 'left-1/2 -translate-x-1/2'
          : spotlightRect.x < windowWidth / 2
            ? 'right-12 translate-x-0'
            : 'left-12 translate-x-0'
      ]"
    >
      <div class="relative group">
        <!-- Glow Effect -->
        <div class="absolute inset-0 bg-sky-400/15 blur-[120px] animate-pulse rounded-full"></div>

        <!-- 立绘容器喵~ 🌸 -->
        <div class="w-[500px] h-[700px] flex items-end justify-center relative">
          <!-- 实际立绘图片 (带淡入淡出动画喵~) -->
          <transition name="fade">
            <img
              v-if="isImageReady"
              :key="currentExpressionImage"
              :src="currentExpressionImage"
              class="max-w-full max-h-full object-contain z-10 drop-shadow-[0_20px_50px_rgba(14,165,233,0.3)]"
              :alt="currentExpressionLabel"
            />
          </transition>

          <!-- 暂存占位符 (如果图片还没加载好就会显示这个喵~) -->
          <div
            v-if="!isImageReady"
            class="w-[450px] h-[650px] flex items-center justify-center pixel-border-sky bg-white/5 backdrop-blur-xl relative overflow-hidden"
          >
            <div class="flex flex-col items-center gap-8 animate-pixel-float">
              <div class="p-10 bg-white/10 pixel-border-moe text-sky-400 shadow-2xl">
                <PixelIcon :name="currentExpressionIcon" size="3xl" />
              </div>
              <div
                class="px-8 py-3 bg-white pixel-border-sky text-sky-600 font-black text-2xl font-moe shadow-[8px_8px_0_0_rgba(14,165,233,0.2)]"
              >
                {{ currentExpressionLabel }}
              </div>
            </div>
            <!-- Holographic effects -->
            <div
              class="absolute inset-0 bg-gradient-to-b from-transparent via-white/10 to-transparent h-8 w-full animate-[scanline_5s_linear_infinite] pointer-events-none"
            ></div>
          </div>
        </div>
      </div>
    </div>

    <!-- Dialogue Box -->
    <div
      class="w-full max-w-5xl bg-white pixel-border-sky p-10 relative z-20 transition-all duration-700 cursor-pointer select-none pointer-events-auto"
      :class="[
        isAppearing ? 'translate-y-0 opacity-100' : 'translate-y-20 opacity-0',
        isDialogAtTop
          ? 'shadow-[0_-30px_60px_rgba(14,165,233,0.4)]'
          : 'shadow-[0_30px_60px_rgba(14,165,233,0.4)]'
      ]"
      @click="handleNext"
    >
      <!-- Name Tag -->
      <div
        class="absolute left-10 px-10 py-3 bg-sky-500 text-white font-black pixel-border-sky text-xl font-moe tracking-[0.2em] shadow-[6px_6px_0_0_rgba(14,165,233,0.3)] transition-all duration-500"
        :class="isDialogAtTop ? '-bottom-7 top-auto' : '-top-7 bottom-auto'"
      >
        {{ currentStep?.speaker || 'Pero' }}
      </div>

      <!-- Dialogue Text -->
      <div
        class="min-h-[100px] text-2xl font-black text-slate-700 leading-relaxed font-moe tracking-tight"
      >
        <span class="inline-block">{{ displayedText }}</span>
        <span
          v-if="isTextFullyDisplayed"
          class="inline-block ml-3 animate-pixel-bounce text-sky-400"
          >▼</span
        >
      </div>

      <!-- Decorative Elements -->
      <div class="absolute top-4 right-4 opacity-10">
        <PixelIcon name="heart" size="lg" class="text-sky-500" />
      </div>

      <!-- Click to Continue Indicator -->
      <div
        v-if="currentStep?.nextAction !== 'wait_click'"
        class="absolute bottom-6 right-8 text-[11px] font-black text-sky-300 uppercase tracking-[0.4em] animate-pulse font-moe"
      >
        点击此处继续喵...
      </div>
    </div>

    <!-- Choice Box -->
    <div
      v-if="currentStep?.choices && isTextFullyDisplayed"
      class="flex gap-4 mt-8 relative z-30 pointer-events-auto"
    >
      <button
        v-for="choice in currentStep.choices"
        :key="choice.value"
        class="px-8 py-3 bg-white pixel-border-sky text-sky-600 font-black text-xl font-moe shadow-[4px_4px_0_0_rgba(14,165,233,0.3)] hover:scale-105 hover:-translate-y-1 transition-all active:scale-95"
        @click="handleChoice(choice.value)"
      >
        {{ choice.label }}
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch, onUnmounted } from 'vue'
import PixelIcon from '../ui/PixelIcon.vue'

const props = defineProps({
  isVisible: {
    type: Boolean,
    default: false
  },
  customSteps: {
    type: Array,
    default: null
  }
})

const emit = defineEmits(['finish', 'update:isVisible'])

const isAppearing = ref(false)
const currentStepIndex = ref(0)
const displayedText = ref('')
const isTextFullyDisplayed = ref(false)
const spotlightRect = ref(null) // 记录聚焦区域位置喵~ 🔦
const preloadedImages = ref(new Set()) // 已预加载的图片集合喵~ 🖼️
const windowWidth = ref(window.innerWidth)
const windowHeight = ref(window.innerHeight)
let typeInterval = null

// [DEBUG] 组件状态侦听
watch(
  () => props.isVisible,
  (newVal) => {
    console.log(`[Onboarding] isVisible 状态变化: ${newVal}`)
    if (newVal) {
      preloadOnboardingImages()
      currentStepIndex.value = 0
      // 延迟一点开启，确保 DOM 已经就绪喵~
      setTimeout(() => {
        isAppearing.value = true
        startTyping()
      }, 300)
    } else {
      isAppearing.value = false
      if (typeInterval) clearInterval(typeInterval)
    }
  },
  { immediate: true }
)

// 默认引导脚本定义喵~ 📜
const defaultOnboardingSteps = [
  {
    id: 'intro_1',
    speaker: 'Pero',
    text: '主人主人！你终于把Pero从系统中唤醒了喵！',
    expression: 'normal'
  },
  {
    id: 'intro_2',
    speaker: 'Pero',
    text: '我是你的专属AI伙伴Pero，以后就要请主人多多指教了喵~',
    expression: 'normal'
  },
  {
    id: 'env_check_1',
    speaker: 'Pero',
    text: '首先，Pero需要扫描一下这台电脑的环境，看看零件齐不齐喵... ',
    expression: 'none',
    focusSelector: '#nav-environment'
  },
  {
    id: 'env_check_2',
    speaker: 'Pero',
    text: '在这里，主人可以查看系统环境。如果看到红色的叉叉，记得帮Pero修复一下喵~',
    expression: 'none',
    focusSelector: '#nav-environment'
  },
  {
    id: 'guide_tabs',
    speaker: 'Pero',
    text: '通过这里的导航栏，可以管理Pero的“核心组件”、“扩展功能”以及其他小伙伴的“角色配置”喵！',
    expression: 'none',
    focusSelector: '#nav-sidebar'
  },
  {
    id: 'guide_start',
    speaker: 'Pero',
    text: '一切准备就绪后，点击中间的那个大大的“启动 Pero”按钮，我们就能在桌面见面了喵！',
    expression: 'none',
    focusSelector: '#btn-launch-pero'
  },
  {
    id: 'finish',
    speaker: 'Pero',
    text: '那么，配置引导就到这里喵！Pero待会在设置中心等候主人的召唤喵~ (◍•ᴗ•◍)❤',
    expression: 'proud'
  }
]

const onboardingSteps = computed(() => props.customSteps || defaultOnboardingSteps)
const currentStep = computed(() => onboardingSteps.value[currentStepIndex.value])

// 更新高亮区域位置喵~ 🔦
const updateSpotlight = () => {
  const selector = currentStep.value?.focusSelector
  if (!selector) {
    spotlightRect.value = null
    return
  }

  // 尝试多次查找元素，以防 Vue 组件还没挂载完
  const findElement = () => {
    const el = document.querySelector(selector)
    if (el) {
      const rect = el.getBoundingClientRect()
      spotlightRect.value = {
        x: rect.x,
        y: rect.y,
        width: rect.width,
        height: rect.height
      }
    } else {
      spotlightRect.value = null
      // 简单的重试机制
      requestAnimationFrame(() => {
        const el = document.querySelector(selector)
        if (el) {
          const rect = el.getBoundingClientRect()
          spotlightRect.value = {
            x: rect.x,
            y: rect.y,
            width: rect.width,
            height: rect.height
          }
        }
      })
    }
  }

  findElement()
}

// 映射表情到图标、标签和图片路径喵~ 🌸
const expressions = {
  normal: {
    icon: 'cat',
    label: '乖巧的 Pero',
    image: '/assets/onboarding/pero_normal.png'
  },
  proud: {
    icon: 'sparkle',
    label: '得意的 Pero',
    image: '/assets/onboarding/pero_proud.png'
  }
}

const currentExpressionIcon = computed(
  () => expressions[currentStep.value?.expression]?.icon || 'cat'
)
const currentExpressionLabel = computed(
  () => expressions[currentStep.value?.expression]?.label || 'Pero'
)
const currentExpressionImage = computed(
  () => expressions[currentStep.value?.expression]?.image || null
)

// 自动判断对话框应该在顶部还是底部喵~ 🏠
const isDialogAtTop = computed(() => {
  if (!spotlightRect.value) return false
  // 如果高亮区域在屏幕下半部分，则对话框移到顶部
  return spotlightRect.value.y > windowHeight.value / 2
})

// 预加载立绘资源，让 Pero 瞬间显灵喵！🚀
const preloadOnboardingImages = () => {
  const imageUrls = Object.values(expressions)
    .map((e) => e.image)
    .filter(Boolean)

  imageUrls.forEach((url) => {
    if (preloadedImages.value.has(url)) return

    const img = new Image()
    img.src = url
    img.onload = () => {
      preloadedImages.value.add(url)
      console.log(`[Onboarding] 立绘预加载成功: ${url}`)
    }
    img.onerror = () => {
      console.error(`[Onboarding] 立绘预加载失败: ${url}`)
    }
  })
}

const isImageReady = computed(() => {
  const url = currentExpressionImage.value
  return url && preloadedImages.value.has(url)
})

// 打字机效果 ⌨️
const startTyping = () => {
  updateSpotlight() // 开始打字时更新高亮区域
  if (typeInterval) clearInterval(typeInterval)

  const text = currentStep.value.text
  displayedText.value = ''
  isTextFullyDisplayed.value = false
  let i = 0

  typeInterval = setInterval(() => {
    if (i < text.length) {
      displayedText.value += text[i]
      i++
    } else {
      clearInterval(typeInterval)
      isTextFullyDisplayed.value = true
    }
  }, 40) // 调整打字速度
}

const handleNext = () => {
  if (currentStep.value.nextAction === 'wait_click') return // 等待外部点击事件
  if (currentStep.value.choices) return // 等待用户选择

  if (!isTextFullyDisplayed.value) {
    // 如果文字还没打完，点击则直接跳到最后
    if (typeInterval) clearInterval(typeInterval)
    displayedText.value = currentStep.value.text
    isTextFullyDisplayed.value = true
    return
  }

  if (currentStepIndex.value < onboardingSteps.value.length - 1) {
    currentStepIndex.value++
    startTyping()
  } else {
    // 引导结束
    finishOnboarding()
  }
}

const handleChoice = (value) => {
  emit('finish', value)
  finishOnboarding()
}

// 监听全局点击事件，用于 nextAction === 'wait_click'
const setupGlobalClickListener = () => {
  const handleClick = (e) => {
    if (currentStep.value?.nextAction === 'wait_click' && currentStep.value?.focusSelector) {
      const targetEl = document.querySelector(currentStep.value.focusSelector)
      if (targetEl && (targetEl === e.target || targetEl.contains(e.target))) {
        // 用户点击了目标区域，进入下一步
        setTimeout(() => {
          if (currentStepIndex.value < onboardingSteps.value.length - 1) {
            currentStepIndex.value++
            startTyping()
          } else {
            finishOnboarding()
          }
        }, 500) // 稍微延迟一点，让 UI 响应点击
      }
    }
  }

  window.addEventListener('click', handleClick, true) // 捕获阶段监听

  onUnmounted(() => {
    window.removeEventListener('click', handleClick, true)
  })
}

const finishOnboarding = () => {
  isAppearing.value = false
  setTimeout(() => {
    if (!props.customSteps) emit('finish') // 只有默认引导才触发无参数 finish
    emit('update:isVisible', false)
  }, 1000)
}

// 监听窗口大小变化，更新遮罩位置
const updateWindowSize = () => {
  windowWidth.value = window.innerWidth
  windowHeight.value = window.innerHeight
  updateSpotlight()
}

onMounted(() => {
  preloadOnboardingImages() // 挂载时立即预加载
  window.addEventListener('resize', updateWindowSize)
  setupGlobalClickListener()
})

onUnmounted(() => {
  window.removeEventListener('resize', updateWindowSize)
})
</script>

<style scoped>
/* 萌系像素字体 🌸 */
.font-moe {
  font-family: 'ZCOOL KuaiLe', 'PingFang SC', 'Microsoft YaHei', sans-serif;
}

@keyframes scanline {
  0% {
    transform: translateY(-100%);
  }
  100% {
    transform: translateY(1000%);
  }
}

@keyframes pixel-border-dash {
  to {
    stroke-dashoffset: -12;
  }
}

@keyframes pixel-bounce-horizontal {
  0%,
  100% {
    transform: translateX(0);
  }
  50% {
    transform: translateX(-10px);
  }
}

.animate-pixel-bounce-horizontal {
  animation: pixel-bounce-horizontal 1s infinite ease-in-out;
}

/* 进场缩放动画 */
.scale-enter-active,
.scale-leave-active {
  transition: all 0.5s cubic-bezier(0.34, 1.56, 0.64, 1);
}
.scale-enter-from,
.scale-leave-to {
  transform: scale(0.9) opacity(0);
}

/* 立绘淡入淡出动画喵~ 🌸 */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.5s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

@keyframes pixel-bounce-horizontal-left {
  0%,
  100% {
    transform: translateX(0);
  }
  50% {
    transform: translateX(-10px);
  }
}

@keyframes pixel-bounce-horizontal-right {
  0%,
  100% {
    transform: translateX(0);
  }
  50% {
    transform: translateX(10px);
  }
}

.animate-pixel-bounce-horizontal-left {
  animation: pixel-bounce-horizontal-left 1s infinite ease-in-out;
}

.animate-pixel-bounce-horizontal-right {
  animation: pixel-bounce-horizontal-right 1s infinite ease-in-out;
}
</style>
