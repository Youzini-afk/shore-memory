<script setup lang="ts">
/**
 * 开关组件 - 具有可爱质感的主题化组件 (喵~🐾)
 */
import PixelIcon from './PixelIcon.vue'

const props = defineProps<{
  modelValue: boolean
  label?: string
  activeColor?: string
  inactiveColor?: string
  disabled?: boolean
  /** 是否开启像素风格 (Minecraft Mode) */
  pixel?: boolean
}>()

const emit = defineEmits(['update:modelValue', 'change'])

/**
 * 切换开关状态
 */
const toggle = () => {
  if (props.disabled) return
  const newValue = !props.modelValue
  emit('update:modelValue', newValue)
  emit('change', newValue)
}
</script>

<template>
  <div
    class="flex items-center gap-3 cursor-pointer select-none group active:scale-95 transition-all duration-500"
    :class="{ 'opacity-50 cursor-not-allowed': disabled }"
    @click="toggle"
  >
    <!-- 开关主体 -->
    <div
      class="relative w-11 h-6 transition-all duration-500 ease-[cubic-bezier(0.34,1.56,0.64,1)] shadow-inner"
      :class="[
        pixel ? 'pixel-border-sky' : 'rounded-full',
        modelValue
          ? activeColor || 'bg-sky-400 shadow-sky-200/50'
          : inactiveColor || 'bg-slate-200 hover:bg-slate-300 shadow-slate-100/50'
      ]"
    >
      <!-- 滑块 -->
      <div
        class="absolute left-1 top-1 w-4 h-4 bg-white transition-all duration-500 ease-[cubic-bezier(0.34,1.56,0.64,1)] flex items-center justify-center shadow-md"
        :class="[
          pixel ? 'pixel-border-sm' : 'rounded-full',
          modelValue ? 'translate-x-5' : 'translate-x-0'
        ]"
      >
        <!-- 滑块内的小装饰 🐾 -->
        <div
          class="transition-all duration-500 transform"
          :class="modelValue ? 'opacity-100 scale-100 rotate-0' : 'opacity-0 scale-50 -rotate-45'"
        >
          <div
            v-if="pixel"
            class="w-2 h-2 bg-sky-400 flex items-center justify-center overflow-hidden pixel-border-sm"
          >
            <div class="w-1 h-1 bg-white/80"></div>
          </div>
          <div v-else class="text-sky-400">
            <PixelIcon name="paw" size="xs" />
          </div>
        </div>
      </div>
    </div>

    <!-- 标签文字 -->
    <span
      v-if="label"
      class="text-[13px] font-bold text-slate-500 group-hover:text-sky-500 transition-colors flex items-center gap-1.5"
    >
      {{ label }}
      <span v-if="modelValue" class="text-[10px] animate-bounce text-sky-400">✨</span>
    </span>
  </div>
</template>
