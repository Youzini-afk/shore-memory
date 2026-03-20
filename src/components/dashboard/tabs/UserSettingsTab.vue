<template>
  <!-- 8. 用户设定 (重构版) -->
  <div class="h-full overflow-y-auto custom-scrollbar p-6">
    <div class="max-w-2xl mx-auto pb-12">
      <!-- Header -->
      <div class="flex items-center gap-4 mb-8">
        <div
          class="p-3 bg-sky-50 rounded-2xl text-sky-500 border border-sky-100 shadow-sm shadow-sky-200/20"
        >
          <PixelIcon name="user" size="md" animation="bounce" />
        </div>
        <div>
          <h3 class="text-2xl font-bold text-slate-800 flex items-center gap-2">
            主人身份设定
            <span class="text-xs font-normal text-slate-400 tracking-widest uppercase ml-1"
              ># Owner Persona</span
            >
          </h3>
          <p class="text-sm text-slate-500 flex items-center gap-1">
            让 {{ activeAgent?.name || 'Pero' }} 更好地认识主人吧
            <PixelIcon name="sparkle" size="xs" animation="pulse" />
            <PixelIcon name="paw" size="xs" />
          </p>
        </div>
      </div>

      <PCard
        glass
        soft3d
        pixel
        variant="sky"
        class="relative overflow-hidden border-sky-100 hover:border-sky-300 transition-all duration-700 rounded-[2.5rem] shadow-xl shadow-sky-100/30 group/settings-card bg-white/80"
      >
        <!-- 背景装饰 ✨ -->
        <div
          class="absolute -right-20 -top-20 w-60 h-60 bg-sky-400/5 blur-[80px] rounded-full pointer-events-none group-hover/settings-card:bg-sky-400/10 transition-all duration-1000"
        ></div>
        <div
          class="absolute -left-10 -bottom-10 w-40 h-40 bg-sky-400/5 blur-[60px] rounded-full pointer-events-none group-hover/settings-card:bg-sky-400/10 transition-all duration-1000 delay-300"
        ></div>

        <div class="p-4 space-y-8 relative z-10">
          <!-- Name & QQ -->
          <div class="grid grid-cols-1 md:grid-cols-2 gap-8">
            <div class="space-y-3">
              <label class="text-sm font-bold text-slate-600 flex items-center gap-2 ml-1">
                <span class="w-1.5 h-1.5 rounded-full bg-sky-400 animate-pulse"></span>
                主人的名字
                <span class="text-[10px] text-slate-400 font-normal uppercase">Owner Name</span>
              </label>
              <PInput
                v-model="userSettings.owner_name"
                class="!rounded-2xl !bg-white/80 !border-sky-100 focus:!border-sky-300 transition-all shadow-sm"
                :placeholder="(activeAgent?.name || 'Pero') + ' 对你的称呼'"
              />
            </div>
            <div class="space-y-3">
              <label class="text-sm font-bold text-slate-600 flex items-center gap-2 ml-1">
                <span class="w-1.5 h-1.5 rounded-full bg-sky-400 animate-pulse"></span>
                主人的 QQ 号
                <span class="text-[10px] text-slate-400 font-normal uppercase">Owner QQ</span>
              </label>
              <PInput
                v-model="userSettings.owner_qq"
                class="!rounded-2xl !bg-white/80 !border-sky-100 focus:!border-sky-300 transition-all shadow-sm"
                :placeholder="'用于 ' + (activeAgent?.name || 'Pero') + ' 主动联系你'"
              />
            </div>
          </div>

          <!-- Persona -->
          <div class="space-y-3">
            <label class="text-sm font-bold text-slate-600 flex items-center gap-2 ml-1">
              <span class="w-1.5 h-1.5 rounded-full bg-sky-400 animate-pulse"></span>
              主人的人设信息
              <span class="text-[10px] text-slate-400 font-normal uppercase">Owner Persona</span>
            </label>
            <PTextarea
              v-model="userSettings.user_persona"
              class="!rounded-[2rem] !bg-white/80 !border-sky-100 focus:!border-sky-300 transition-all shadow-sm leading-relaxed"
              :rows="10"
              placeholder="描述一下你自己，比如你的性格、职业、与 Pero 的关系等。这些信息会帮助 Pero 更好地了解你并调整交流方式。🐾"
            />
            <p class="text-[11px] text-slate-400 px-2 flex items-center gap-1.5">
              💡 完善的人设能让对话更具个性化和沉浸感哦~
            </p>
          </div>

          <!-- Actions -->
          <div class="pt-4 flex justify-end">
            <PButton
              variant="primary"
              size="lg"
              class="!rounded-2xl px-10 py-6 shadow-lg shadow-sky-400/20 hover:scale-105 active:scale-95 transition-all group/save-btn hover-pixel-bounce"
              :loading="isSaving"
              @click="saveUserSettings"
            >
              <span class="flex items-center gap-2">
                保存设定
                <span class="text-lg group-hover/save-btn:scale-125 transition-transform"
                  ><PixelIcon name="thought" size="sm"
                /></span>
              </span>
            </PButton>
          </div>
        </div>
      </PCard>
    </div>
  </div>
</template>

<script setup lang="ts">
import { inject } from 'vue'
import PCard from '@/components/ui/PCard.vue'
import PButton from '@/components/ui/PButton.vue'
import PInput from '@/components/ui/PInput.vue'
import PTextarea from '@/components/ui/PTextarea.vue'
import PixelIcon from '@/components/ui/PixelIcon.vue'
import {
  MODEL_CONFIG_KEY,
  AGENT_CONFIG_KEY,
  DASHBOARD_KEY
} from '@/composables/dashboard/injectionKeys'

const { userSettings, saveUserSettings, isSaving } = inject(MODEL_CONFIG_KEY)!
const { activeAgent } = inject(AGENT_CONFIG_KEY)!
</script>
