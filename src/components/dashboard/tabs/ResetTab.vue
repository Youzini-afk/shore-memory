<template>
  <!-- 9. 恢复出厂设置 (重构版) -->
  <div class="h-full overflow-y-auto custom-scrollbar p-6 flex items-center justify-center">
    <PCard
      glass
      soft3d
      pixel
      variant="rose"
      class="max-w-lg w-full !p-8 !rounded-[2.5rem] relative overflow-hidden group/reset-card"
    >
      <!-- 背景装饰 ✨ -->
      <div
        class="absolute -right-20 -top-20 w-60 h-60 bg-rose-400/10 blur-[80px] rounded-full pointer-events-none group-hover/reset-card:bg-rose-400/20 transition-all duration-1000"
      ></div>
      <div
        class="absolute -left-20 -bottom-20 w-40 h-40 bg-amber-400/5 blur-[60px] rounded-full pointer-events-none group-hover/reset-card:bg-amber-400/10 transition-all duration-1000 delay-300"
      ></div>

      <div class="relative z-10">
        <div class="flex items-center gap-4 mb-8">
          <div
            class="p-4 bg-rose-50 rounded-2xl text-rose-500 border border-rose-100 shadow-sm shadow-rose-100/30 group-hover/reset-card:scale-110 group-hover/reset-card:rotate-6 transition-all duration-500 soft-3d-shadow"
          >
            <PixelIcon name="alert" size="lg" animation="pulse" />
          </div>
          <div>
            <h3 class="text-xl font-black text-slate-800">恢复出厂设置</h3>
            <p class="text-[10px] text-slate-400 mt-1 uppercase tracking-widest font-bold">
              # System Factory Reset
            </p>
          </div>
        </div>

        <div class="space-y-6">
          <div
            class="bg-white/40 backdrop-blur-md rounded-[2rem] p-6 border border-rose-100/50 soft-3d-shadow"
          >
            <p class="text-sm font-bold text-slate-700 mb-4 flex items-center gap-2">
              <span class="w-1.5 h-1.5 rounded-full bg-rose-500 animate-pulse"></span>
              此操作将执行以下清理：
            </p>
            <ul class="space-y-3 text-slate-500 text-xs font-medium">
              <li class="flex items-center gap-3 group/item hover:text-slate-800 transition-colors">
                <span
                  class="w-1 h-1 rounded-full bg-rose-200 group-hover/item:bg-rose-500 transition-colors"
                ></span>
                清除所有 <strong class="text-rose-500">长期记忆</strong> (Memories)
              </li>
              <li class="flex items-center gap-3 group/item hover:text-slate-800 transition-colors">
                <span
                  class="w-1 h-1 rounded-full bg-rose-200 group-hover/item:bg-rose-500 transition-colors"
                ></span>
                清除所有 <strong class="text-rose-500">对话历史</strong> (Logs)
              </li>
              <li class="flex items-center gap-3 group/item hover:text-slate-800 transition-colors">
                <span
                  class="w-1 h-1 rounded-full bg-rose-200 group-hover/item:bg-rose-500 transition-colors"
                ></span>
                重置 Pero 的 <strong class="text-rose-500">状态与情绪</strong> (Pet State)
              </li>
              <li class="flex items-center gap-3 group/item hover:text-slate-800 transition-colors">
                <span
                  class="w-1 h-1 rounded-full bg-rose-200 group-hover/item:bg-rose-500 transition-colors"
                ></span>
                清除所有 <strong class="text-rose-500">待办提醒与话题</strong> (Tasks)
              </li>
              <li class="flex items-center gap-3 group/item hover:text-slate-800 transition-colors">
                <span
                  class="w-1 h-1 rounded-full bg-rose-200 group-hover/item:bg-rose-500 transition-colors"
                ></span>
                重置 <strong class="text-rose-500">主人设定</strong> (Owner Persona)
              </li>
            </ul>
          </div>

          <div
            class="p-4 bg-amber-50/50 backdrop-blur-md border border-amber-100 rounded-2xl text-[11px] text-amber-600 font-medium leading-relaxed soft-3d-shadow"
          >
            <span class="mr-1">💡</span>
            注：模型 API 配置、语音配置、MCP 配置将被保留，不用担心重新配置服务器哦~ ✨
          </div>

          <div class="pt-4 flex justify-center">
            <PButton
              variant="danger"
              size="lg"
              class="!rounded-2xl px-10 py-7 shadow-xl shadow-rose-400/20 hover:scale-105 active:scale-95 transition-all group/reset-btn relative overflow-hidden hover-pixel-bounce"
              :loading="isSaving"
              @click="handleSystemReset"
            >
              <div class="flex items-center gap-3 relative z-10">
                <PixelIcon
                  name="trash"
                  size="md"
                  class="group-hover/reset-btn:shake transition-transform"
                />
                <span class="font-black tracking-widest text-base">立即执行深度重置</span>
                <span class="text-xl group-hover/reset-btn:rotate-12 transition-transform"
                  ><PixelIcon name="firecracker" size="md"
                /></span>
              </div>
              <!-- 按钮光泽效果 -->
              <div
                class="absolute inset-0 bg-gradient-to-r from-transparent via-white/20 to-transparent -translate-x-full group-hover:translate-x-full transition-transform duration-1000"
              ></div>
            </PButton>
          </div>
        </div>
      </div>
    </PCard>
  </div>

  <!-- 10. NapCat 终端 -->
</template>

<script setup lang="ts">
import { inject } from 'vue'
import PCard from '@/components/ui/PCard.vue'
import PButton from '@/components/ui/PButton.vue'
import PixelIcon from '@/components/ui/PixelIcon.vue'
import {
  MODEL_CONFIG_KEY,
  AGENT_CONFIG_KEY,
  DASHBOARD_KEY
} from '@/composables/dashboard/injectionKeys'

const { handleSystemReset, isSaving } = inject(MODEL_CONFIG_KEY)!
const { activeAgent } = inject(AGENT_CONFIG_KEY)!
</script>
