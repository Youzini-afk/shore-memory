<script setup lang="ts">
/**
 * 空状态组件 - 具有可爱动画与 sky blue 主题 (喵~🐾)
 */
import PixelIcon from './PixelIcon.vue'

defineProps<{
  description?: string
  /** 是否显示可爱的小猫爪 */
  showPaw?: boolean
}>()
</script>

<template>
  <div class="flex flex-col items-center justify-center py-16 text-slate-400 group/pempty">
    <!-- 装饰性图标容器 -->
    <div class="relative mb-6">
      <div
        class="p-6 bg-sky-50/50 rounded-[2rem] border border-sky-100 shadow-inner group-hover/pempty:border-sky-300 transition-all duration-500 group-hover/pempty:shadow-[0_0_20px_rgba(14,165,233,0.1)]"
      >
        <PixelIcon
          name="inbox"
          size="2xl"
          class="opacity-30 group-hover/pempty:opacity-60 group-hover/pempty:text-sky-500 transition-all duration-500 group-hover/pempty:scale-110"
        />
      </div>

      <!-- 漂浮的小星星 ✨ -->
      <div
        class="absolute -top-2 -right-2 text-sky-500/40 animate-bounce opacity-0 group-hover/pempty:opacity-100 transition-opacity duration-500"
      >
        ✨
      </div>
      <div
        class="absolute -bottom-1 -left-3 text-sky-500/20 animate-pulse delay-75 opacity-0 group-hover/pempty:opacity-100 transition-opacity duration-500"
      >
        ✨
      </div>
    </div>

    <!-- 文字描述 -->
    <div class="text-center space-y-2">
      <p
        class="text-sm font-bold text-slate-400 group-hover:text-sky-500 transition-colors duration-500 tracking-wide"
      >
        {{ description || '这里空空如也喵...' }}
      </p>

      <!-- 可爱的小提示 -->
      <div
        class="flex items-center justify-center gap-1.5 opacity-0 group-hover/pempty:opacity-100 transition-all duration-700 translate-y-2 group-hover/pempty:translate-y-0"
      >
        <span class="w-1.5 h-1.5 bg-sky-500/20 rounded-full"></span>
        <span class="text-[10px] text-sky-500/40 font-mono italic">NO DATA FOUND</span>
        <span class="w-1.5 h-1.5 bg-sky-500/20 rounded-full"></span>
      </div>
    </div>

    <!-- 底部的小尾巴 🐾 -->
    <div
      v-if="showPaw !== false"
      class="mt-4 text-sky-500/10 group-hover/pempty:text-sky-500/30 transition-colors duration-500 text-xl"
    >
      🐾
    </div>
  </div>
</template>
