<template>
  <!-- 4. 待办任务 -->
  <div class="h-full flex flex-col overflow-hidden">
    <!-- Toolbar -->
    <div class="p-6 pb-4 flex-none">
      <PCard
        glass
        soft3d
        variant="orange"
        overflow-visible
        class="flex items-center justify-between !p-5 rounded-[2rem] relative group/ttoolbar z-30"
      >
        <!-- 背景装饰 ✨ -->
        <div
          class="absolute -right-20 -top-20 w-40 h-40 bg-orange-400/10 blur-[60px] rounded-full pointer-events-none group-hover/ttoolbar:bg-orange-400/20 transition-all duration-1000"
        ></div>

        <div class="flex items-center gap-4 relative z-10">
          <div
            class="p-3 bg-orange-50 rounded-2xl text-orange-500 border border-orange-100 shadow-sm shadow-orange-200/20 group-hover/ttoolbar:scale-110 group-hover/ttoolbar:rotate-6 transition-all duration-500"
          >
            <PixelIcon name="list" size="md" animation="bounce" />
          </div>
          <div>
            <h3 class="text-xl font-bold text-slate-800 flex items-center gap-2">
              待办与计划
              <span
                class="text-xs font-normal text-slate-400 tracking-widest uppercase ml-1 opacity-50 group-hover/ttoolbar:opacity-100 transition-opacity"
                ># Tasks</span
              >
            </h3>
            <p class="text-xs text-slate-500 flex items-center gap-1.5 mt-0.5">
              管理 AI 生成的提醒事项与话题
              <span class="group-hover/ttoolbar:animate-pulse">✨ 🐾</span>
            </p>
          </div>
        </div>

        <!-- 角色选择 (Agent Selector) -->
        <div class="flex items-center gap-4 relative z-10">
          <div class="flex flex-col gap-1 min-w-[150px]">
            <label
              class="text-[10px] font-bold text-slate-400 flex items-center gap-1.5 ml-1 uppercase tracking-wider"
            >
              <span class="w-1 h-1 rounded-full bg-orange-400 animate-pulse"></span>
              归属角色
            </label>
            <div class="relative group/tagent">
              <button
                class="w-full flex items-center justify-between px-4 py-2 bg-white/60 hover:bg-white/90 border border-orange-100/50 hover:border-orange-300 rounded-xl text-sm transition-all active:scale-95 shadow-lg shadow-black/30 backdrop-blur-md group/btn hover-pixel-bounce"
                :class="isSwitchingAgent ? 'opacity-50 cursor-not-allowed' : ''"
              >
                <span class="text-orange-600 font-bold flex items-center gap-2">
                  <span
                    class="text-xs opacity-0 group-hover/btn:opacity-100 transition-all duration-300 -translate-x-2 group-hover:translate-x-0"
                    ><PixelIcon name="paw" size="xs"
                  /></span>
                  {{ activeAgent?.name || '未知' }}
                </span>
                <PixelIcon
                  name="chevron-down"
                  size="xs"
                  class="text-slate-400 group-hover/tagent:rotate-180 transition-transform duration-500"
                />
              </button>

              <!-- 下拉菜单 (Dropdown Menu) -->
              <div
                class="absolute right-0 top-full mt-2 w-full py-2 bg-white/70 backdrop-blur-xl border border-orange-100 rounded-2xl shadow-xl shadow-orange-200/30 opacity-0 invisible group-hover/tagent:opacity-100 group-hover/tagent:visible transition-all duration-300 z-50 transform origin-top scale-95 group-hover/tagent:scale-100"
              >
                <div class="px-3 py-1.5 mb-1 border-b border-orange-50">
                  <span
                    class="text-[10px] font-bold text-slate-400 uppercase tracking-widest flex items-center gap-1"
                  >
                    切换角色 <span class="animate-bounce">✨</span>
                  </span>
                </div>
                <button
                  v-for="agent in availableAgents"
                  :key="agent.id"
                  class="w-full text-left px-4 py-2.5 text-sm hover:bg-orange-50 transition-all flex items-center justify-between group/item"
                  :class="{
                    'text-orange-600 font-bold bg-orange-50': agent.id === activeAgent?.id,
                    'text-slate-600': agent.id !== activeAgent?.id,
                    'opacity-50 cursor-not-allowed': !agent.is_enabled
                  }"
                  :disabled="agent.id === activeAgent?.id || !agent.is_enabled"
                  @click="switchAgent(agent.id)"
                >
                  <div class="flex items-center gap-2">
                    <span class="text-xs opacity-0 group-hover/item:opacity-100 transition-opacity"
                      ><PixelIcon name="paw" size="xs"
                    /></span>
                    <span>{{ agent.name }}</span>
                  </div>
                  <span
                    v-if="!agent.is_enabled"
                    class="text-[10px] text-slate-400 font-bold px-1.5 py-0.5 bg-slate-50 rounded-md"
                    >DISABLED</span
                  >
                </button>
              </div>
            </div>
          </div>
        </div>
      </PCard>
    </div>

    <!-- 任务列表 (Task List) -->
    <div class="flex-1 overflow-y-auto px-6 py-2 custom-scrollbar">
      <div
        v-if="tasks.length"
        class="columns-1 md:columns-2 lg:columns-3 xl:columns-4 gap-6 space-y-6 pb-8"
      >
        <div v-for="task in taskList" :key="task.id" class="break-inside-avoid mb-6">
          <PCard
            glass
            soft3d
            hoverable
            :variant="task.type === 'reminder' ? 'pink' : 'orange'"
            class="group/tcard relative !p-6 !rounded-[2rem] transition-all duration-500 overflow-hidden"
          >
            <!-- 背景装饰 ✨ -->
            <div
              class="absolute -right-10 -top-10 w-24 h-24 blur-[40px] rounded-full pointer-events-none transition-opacity duration-500 opacity-10 group-hover/tcard:opacity-20"
              :class="task.type === 'reminder' ? 'bg-pink-400' : 'bg-orange-400'"
            ></div>

            <!-- 🐾 Hover icon -->
            <div
              class="absolute -top-1 -right-1 opacity-0 group-hover/tcard:opacity-100 transition-all duration-500 scale-50 group-hover/tcard:scale-100 z-20"
            >
              <div
                class="shadow-lg rounded-full p-2"
                :class="
                  task.type === 'reminder'
                    ? 'bg-pink-400 shadow-pink-400/30'
                    : 'bg-orange-400 shadow-orange-400/30'
                "
              >
                <PixelIcon name="sparkle" size="sm" class="text-white" />
              </div>
            </div>

            <!-- Header -->
            <div class="flex items-start justify-between mb-4 relative z-10">
              <span
                class="px-3 py-1 rounded-full text-[10px] font-bold uppercase tracking-widest border backdrop-blur-md transition-all duration-300"
                :class="
                  task.type === 'reminder'
                    ? 'bg-pink-50 text-pink-500 border-pink-200 group-hover/tcard:bg-pink-100'
                    : 'bg-orange-50 text-orange-500 border-orange-200 group-hover/tcard:bg-orange-100'
                "
              >
                <span class="mr-1">{{ task.type === 'reminder' ? '⏰' : '💡' }}</span>
                {{ task.type === 'reminder' ? '提醒' : '话题' }}
              </span>
              <button
                class="text-slate-400 hover:text-pink-500 transition-all opacity-0 group-hover/tcard:opacity-100 p-2 rounded-xl hover:bg-pink-50 active:scale-90"
                @click="deleteTask(task.id)"
              >
                <PixelIcon name="trash" size="xs" />
              </button>
            </div>

            <!-- Content -->
            <div
              class="text-[15px] text-slate-600 leading-relaxed mb-6 font-medium relative z-10 group-hover/tcard:text-slate-800 transition-colors"
            >
              {{ task.content }}
            </div>

            <!-- Footer -->
            <div
              class="flex items-center justify-between text-[11px] text-slate-400 font-mono border-t border-sky-100/30 pt-4 mt-auto relative z-10 group-hover/tcard:border-sky-200 transition-colors"
            >
              <div class="flex items-center gap-2">
                <PixelIcon
                  name="calendar"
                  size="xs"
                  class="text-slate-300 group-hover/tcard:text-orange-500 transition-colors"
                />
                <span class="group-hover/tcard:text-slate-500 transition-colors">{{
                  new Date(task.time).toLocaleString('zh-CN', {
                    month: '2-digit',
                    day: '2-digit',
                    hour: '2-digit',
                    minute: '2-digit'
                  })
                }}</span>
              </div>
              <span class="opacity-0 group-hover/tcard:opacity-100 transition-opacity duration-700"
                ><PixelIcon name="paw" size="xs"
              /></span>
            </div>
          </PCard>
        </div>
      </div>

      <!-- Empty State -->
      <PEmpty v-else description="暂无待办任务，Pero 正在休息中... 🐾" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { inject, computed } from 'vue'
import PCard from '@/components/ui/PCard.vue'
import PEmpty from '@/components/ui/PEmpty.vue'
import PixelIcon from '@/components/ui/PixelIcon.vue'
import { TASKS_KEY, AGENT_CONFIG_KEY } from '@/composables/dashboard/injectionKeys'

const { tasks, deleteTask } = inject(TASKS_KEY)!
const { activeAgent, availableAgents, isSwitchingAgent, switchAgent } = inject(AGENT_CONFIG_KEY)!

const taskList = computed(() => tasks.value)
</script>
