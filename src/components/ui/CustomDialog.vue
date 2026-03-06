<template>
  <div
    v-if="visible"
    class="fixed inset-0 z-[10000] flex items-center justify-center bg-black/50 backdrop-blur-sm"
    @click.self="handleOverlayClick"
  >
    <div
      class="border shadow-2xl transform transition-all flex flex-col max-h-[90vh]"
      :class="[
        overflowVisible ? 'overflow-visible' : 'overflow-hidden',
        workMode
          ? 'bg-[#252526] border-slate-800/50 pixel-border-dark'
          : 'bg-[#fffcf9]/95 backdrop-blur-md border-moe-cocoa/5 pixel-border-moe'
      ]"
      :style="{ width: width || '400px' }"
    >
      <!-- 头部 -->
      <div
        class="px-4 py-3 border-b flex justify-between items-center shrink-0"
        :class="workMode ? 'border-slate-800/50 bg-[#2d2d2d]' : 'border-moe-cocoa/10 bg-moe-pink/5'"
      >
        <h3
          class="text-sm font-semibold select-none"
          :class="workMode ? 'text-[#cccccc]' : 'text-moe-cocoa'"
        >
          {{ title }}
        </h3>
        <button
          class="transition-colors"
          :class="
            workMode ? 'text-[#888888] hover:text-white' : 'text-moe-cocoa/40 hover:text-moe-cocoa'
          "
          @click="handleCancel"
        >
          <PixelIcon name="close" size="sm" />
        </button>
      </div>

      <!-- 内容 -->
      <div
        class="p-4 custom-scrollbar flex-1"
        :class="[
          overflowVisible ? 'overflow-visible' : 'overflow-y-auto',
          workMode ? '' : 'text-moe-cocoa'
        ]"
      >
        <slot>
          <p
            v-if="message"
            class="text-sm mb-4 whitespace-pre-wrap"
            :class="workMode ? 'text-[#cccccc]' : 'text-moe-cocoa/80'"
          >
            {{ message }}
          </p>

          <div v-if="type === 'prompt'">
            <input
              ref="inputRef"
              v-model="inputValue"
              class="w-full text-sm px-3 py-2 outline-none transition-all"
              :class="[
                workMode
                  ? 'bg-[#3c3c3c] border-[#3c3c3c] focus:border-[#007fd4] text-white pixel-border-sm-dark placeholder-gray-500'
                  : 'bg-white border-moe-cocoa/10 focus:border-moe-pink text-moe-cocoa pixel-border-moe placeholder-moe-cocoa/30'
              ]"
              :placeholder="placeholder"
              @keyup.enter="handleConfirm"
            />
          </div>
        </slot>
      </div>

      <!-- 底部 -->
      <div
        v-if="!$slots.footer && type !== 'custom'"
        class="px-4 py-3 flex justify-end gap-2 shrink-0 border-t"
        :class="workMode ? 'bg-[#2d2d2d] border-slate-800/50' : 'bg-moe-pink/5 border-moe-cocoa/10'"
      >
        <button
          v-if="type !== 'alert'"
          class="px-4 py-1.5 text-sm transition-all hover:scale-105 active:scale-95"
          :class="[
            workMode
              ? 'text-white bg-[#454545] hover:bg-[#525252] pixel-border-sm-dark'
              : 'text-moe-cocoa bg-white hover:bg-slate-50 pixel-border-moe'
          ]"
          @click="handleCancel"
        >
          取消
        </button>
        <button
          class="px-4 py-1.5 text-sm transition-all hover:scale-105 active:scale-95"
          :class="[
            workMode
              ? 'text-white bg-[#007fd4] hover:bg-[#0069b4] pixel-border-sm-dark'
              : 'text-white bg-moe-pink hover:bg-moe-pink-hover pixel-border-moe'
          ]"
          @click="handleConfirm"
        >
          确定
        </button>
      </div>
      <div
        v-else-if="$slots.footer"
        class="px-4 py-3 border-t shrink-0"
        :class="workMode ? 'bg-[#2d2d2d] border-slate-800/50' : 'bg-moe-pink/5 border-moe-cocoa/10'"
      >
        <slot name="footer"></slot>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, nextTick } from 'vue'
import PixelIcon from './PixelIcon.vue'

const props = defineProps({
  visible: Boolean,
  type: {
    type: String,
    default: 'alert' // 警告, 确认, 输入, 自定义
  },
  title: {
    type: String,
    default: '提示'
  },
  message: {
    type: String,
    default: ''
  },
  defaultValue: {
    type: String,
    default: ''
  },
  placeholder: {
    type: String,
    default: ''
  },
  width: {
    type: String,
    default: ''
  },
  /** 是否处于工作模式 */
  workMode: {
    type: Boolean,
    default: true
  },
  /** 是否允许内容溢出显示 (用于包含下拉框时) */
  overflowVisible: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['update:visible', 'confirm', 'cancel'])

const inputValue = ref('')
const inputRef = ref(null)

// 监听可见性变化以设置焦点
watch(
  () => props.visible,
  async (newVal) => {
    if (newVal) {
      inputValue.value = props.defaultValue
      if (props.type === 'prompt') {
        await nextTick()
        inputRef.value?.focus()
        inputRef.value?.select()
      }
    }
  }
)

// 处理确认操作
const handleConfirm = () => {
  if (props.type === 'prompt') {
    emit('confirm', inputValue.value)
  } else {
    emit('confirm')
  }
  emit('update:visible', false)
}

// 处理取消操作
const handleCancel = () => {
  emit('cancel')
  emit('update:visible', false)
}

// 处理遮罩层点击
const handleOverlayClick = () => {
  if (props.type !== 'alert') {
    handleCancel()
  }
}
</script>
