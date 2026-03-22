<template>
  <!-- 2. 对话日志 (重构版) -->
  <div class="h-full flex flex-col overflow-hidden">
    <!-- 工具栏 -->
    <div class="p-6 pb-0 flex-none">
      <PCard
        glass
        soft3d
        overflow-visible
        class="mb-4 !p-4 rounded-[2rem] relative group/toolbar z-30"
      >
        <!-- 背景装饰 ✨ -->
        <div
          class="absolute -right-20 -top-20 w-40 h-40 bg-sky-400/10 blur-[60px] rounded-full pointer-events-none group-hover/toolbar:bg-sky-400/20 transition-all duration-1000"
        ></div>
        <div
          class="absolute -left-10 -bottom-10 w-32 h-32 bg-sky-300/5 blur-[50px] rounded-full pointer-events-none group-hover/toolbar:bg-sky-300/15 transition-all duration-1000 delay-150"
        ></div>

        <div class="flex flex-wrap items-end gap-5 relative z-10">
          <!-- 助手选择器 -->
          <div class="flex flex-col gap-2 min-w-[150px]">
            <label
              class="text-[11px] font-bold text-slate-500 flex items-center gap-1.5 ml-1 uppercase tracking-wider"
            >
              <span class="w-1.5 h-1.5 rounded-full bg-sky-500 animate-pulse"></span> 角色
              <span class="opacity-50 font-normal">Agent</span>
            </label>
            <div class="relative group/agent">
              <button
                class="w-full flex items-center justify-between px-4 py-2.5 bg-white hover:bg-sky-50 border border-sky-100 rounded-2xl text-sm transition-all active:scale-95 shadow-lg shadow-black/30 backdrop-blur-md group/btn"
                :class="isSwitchingAgent ? 'opacity-50 cursor-not-allowed' : ''"
              >
                <span class="text-sky-600 font-bold flex items-center gap-2">
                  <img
                    v-if="activeAgent?.avatarUrl"
                    :src="activeAgent.avatarUrl"
                    class="w-6 h-6 rounded-lg object-cover"
                    alt="Avatar"
                  />
                  <span
                    v-else
                    class="text-xs opacity-0 group-hover/btn:opacity-100 transition-all duration-300 -translate-x-2 group-hover:translate-x-0"
                    ><PixelIcon name="paw" size="xs"
                  /></span>
                  {{ activeAgent?.name || '未知' }}
                  <span
                    class="text-[10px] font-normal opacity-40 group-hover:opacity-100 transition-opacity"
                    ><PixelIcon name="sparkle" size="xs"
                  /></span>
                </span>
                <PixelIcon
                  name="chevron-down"
                  size="xs"
                  class="text-slate-400 group-hover/agent:rotate-180 transition-transform duration-500"
                />
              </button>
              <!-- 下拉菜单 -->
              <div
                class="absolute left-0 top-full mt-3 w-full py-2 bg-white/70 backdrop-blur-2xl border border-sky-100 rounded-2xl shadow-2xl shadow-sky-200/40 opacity-0 invisible group-hover/agent:opacity-100 group-hover/agent:visible transition-all duration-500 z-50 transform origin-top scale-90 group-hover/agent:scale-100 ring-1 ring-sky-100/5"
              >
                <button
                  v-for="agent in availableAgents"
                  :key="agent.id"
                  class="w-full text-left px-4 py-2.5 text-sm hover:bg-sky-50 transition-all flex items-center justify-between group/item"
                  :class="{
                    'text-sky-600 font-bold bg-sky-50': agent.id === activeAgent?.id,
                    'text-slate-500': agent.id !== activeAgent?.id
                  }"
                  :disabled="agent.id === activeAgent?.id || !agent.is_enabled"
                  @click="switchAgent(agent.id)"
                >
                  <span
                    class="group-hover/item:translate-x-1.5 transition-transform flex items-center gap-2"
                  >
                    <img
                      v-if="agent.avatarUrl"
                      :src="agent.avatarUrl"
                      class="w-6 h-6 rounded-lg object-cover"
                      alt="Avatar"
                    />
                    <span v-else-if="agent.id === activeAgent?.id" class="text-xs"
                      ><PixelIcon name="paw" size="xs"
                    /></span>
                    {{ agent.name }}
                  </span>
                  <div class="flex items-center gap-2">
                    <span
                      v-if="!agent.is_enabled"
                      class="text-[10px] text-slate-500 font-normal bg-sky-100 px-1.5 py-0.5 rounded-lg border border-sky-200"
                      >禁用</span
                    >
                    <span
                      v-if="agent.id === activeAgent?.id"
                      class="text-sky-400 drop-shadow-[0_0_8px_rgba(14,165,233,0.5)]"
                      ><PixelIcon name="heart" size="xs"
                    /></span>
                  </div>
                </button>
              </div>
            </div>
          </div>

          <!-- 来源 -->
          <div class="flex flex-col gap-2 w-[140px] relative z-40">
            <label
              class="text-[11px] font-bold text-slate-500 flex items-center gap-1.5 ml-1 uppercase tracking-wider"
            >
              <span class="w-1.5 h-1.5 rounded-full bg-sky-500"></span> 来源
              <span class="opacity-50 font-normal">Source</span>
            </label>
            <PSelect
              v-model="selectedSource"
              :options="[
                { label: '全部来源', value: 'all', icon: 'sparkle' },
                { label: 'Desktop', value: 'desktop', icon: 'desktop' },
                { label: 'Mobile', value: 'mobile', icon: 'mobile' }
              ]"
              class="!rounded-2xl shadow-lg shadow-black/30 backdrop-blur-md"
              size="md"
              @change="fetchLogs"
            >
              <template #option="{ option }">
                <div class="flex items-center gap-2">
                  <PixelIcon v-if="option.icon" :name="option.icon" size="xs" class="opacity-70" />
                  <span>{{ option.label }}</span>
                </div>
              </template>
            </PSelect>
          </div>

          <!-- 会话 -->
          <div class="flex flex-col gap-2 w-[160px] relative z-30">
            <label
              class="text-[11px] font-bold text-slate-500 flex items-center gap-1.5 ml-1 uppercase tracking-wider"
            >
              <span class="w-1.5 h-1.5 rounded-full bg-sky-500"></span> 会话
              <span class="opacity-50 font-normal">Session</span>
            </label>
            <PSelect
              v-model="selectedSessionId"
              :options="[
                { label: '全部会话', value: 'all', icon: 'chat' },
                { label: '默认会话 (Text)', value: 'default', icon: 'thought' },
                { label: '语音会话 (Voice)', value: 'voice_session', icon: 'sparkle' }
              ]"
              class="!rounded-2xl shadow-lg shadow-black/30 backdrop-blur-md"
              size="md"
              @change="fetchLogs"
            >
              <template #option="{ option }">
                <div class="flex items-center gap-2">
                  <PixelIcon v-if="option.icon" :name="option.icon" size="xs" class="opacity-70" />
                  <span>{{ option.label }}</span>
                </div>
              </template>
            </PSelect>
          </div>

          <!-- Date -->
          <div class="flex flex-col gap-2 w-[160px] relative z-20">
            <label
              class="text-[11px] font-bold text-slate-500 flex items-center gap-1.5 ml-1 uppercase tracking-wider"
            >
              <span class="w-1.5 h-1.5 rounded-full bg-sky-500"></span> 日期
              <span class="opacity-50 font-normal">Date</span>
            </label>
            <div class="relative group/datepicker">
              <PDatePicker
                v-model="selectedDate"
                placeholder="选择日期"
                class="!rounded-2xl shadow-lg shadow-black/30 backdrop-blur-md"
                @update:model-value="fetchLogs"
              />
              <div
                class="absolute right-4 top-1/2 -translate-y-1/2 pointer-events-none opacity-50 group-hover/datepicker:opacity-100 transition-opacity"
              >
                <PixelIcon name="calendar" size="xs" />
              </div>
            </div>
          </div>

          <!-- Sort -->
          <div class="flex flex-col gap-2 w-[120px] relative z-10">
            <label
              class="text-[11px] font-bold text-slate-500 flex items-center gap-1.5 ml-1 uppercase tracking-wider"
            >
              <span class="w-1.5 h-1.5 rounded-full bg-sky-500"></span> 排序
              <span class="opacity-50 font-normal">Sort</span>
            </label>
            <PSelect
              v-model="selectedSort"
              :options="[
                { label: '最新在前', value: 'desc', icon: 'hourglass' },
                { label: '最早在前', value: 'asc', icon: 'clock' }
              ]"
              class="!rounded-2xl shadow-lg shadow-black/30 backdrop-blur-md"
              size="md"
              @change="fetchLogs"
            >
              <template #option="{ option }">
                <div class="flex items-center gap-2 text-xs">
                  <PixelIcon v-if="option.icon" :name="option.icon" size="xs" class="opacity-70" />
                  <span>{{ option.label }}</span>
                </div>
              </template>
            </PSelect>
          </div>

          <!-- 刷新 -->
          <div class="pb-0.5 ml-auto">
            <PButton
              variant="secondary"
              :loading="isLogsFetching"
              class="!rounded-2xl shadow-xl shadow-black/30 hover:scale-110 active:scale-95 transition-all px-6 group/refresh"
              @click="fetchLogs"
            >
              <span class="group-hover/refresh:rotate-180 transition-transform duration-700"
                >刷新</span
              >
              <PixelIcon name="refresh" size="xs" />
            </PButton>
          </div>
        </div>
      </PCard>
    </div>

    <!-- 聊天列表 -->
    <div class="flex-1 overflow-y-auto px-6 pb-6 custom-scrollbar">
      <PEmpty v-if="logs.length === 0">
        <template #description>
          <div class="flex items-center gap-2 justify-center">
            暂无对话记录 <PixelIcon name="thought" size="xs" />
          </div>
        </template>
      </PEmpty>

      <div v-else class="space-y-8 max-w-4xl mx-auto pt-4">
        <div
          v-for="log in logs"
          :key="log.id"
          class="flex gap-4 group"
          :class="log.role === 'user' ? 'flex-row-reverse' : ''"
        >
          <!-- 头像 -->
          <div
            class="flex-none w-14 h-14 rounded-2xl flex items-center justify-center text-lg shadow-xl border transition-all duration-500 group-hover:scale-110 group-hover:rotate-6 group-hover:shadow-sky-200/50 relative overflow-hidden"
            :class="
              log.role === 'user'
                ? 'bg-sky-50 text-sky-600 border-sky-200 shadow-sky-100/30'
                : 'bg-white text-purple-500 border-purple-100 shadow-purple-100/20'
            "
          >
            <div class="absolute inset-0 bg-gradient-to-tr from-white/20 to-transparent"></div>
            <PixelIcon v-if="log.role === 'user'" name="user" size="xl" class="relative z-10" />
            <PixelIcon v-else name="robot" size="xl" class="relative z-10" />
            <!-- 🐾 小脚印装饰 -->
            <div
              class="absolute -bottom-1 -right-1 text-[10px] opacity-0 group-hover:opacity-100 transition-opacity duration-500 z-20"
            >
              <PixelIcon name="paw" size="xs" animation="bounce" />
            </div>
          </div>

          <!-- 气泡内容 -->
          <div
            class="flex flex-col max-w-[85%] relative"
            :class="log.role === 'user' ? 'items-end' : 'items-start'"
          >
            <!-- Meta -->
            <div class="flex items-center gap-2 mb-2 text-[11px] text-slate-400 px-3 font-bold">
              <span
                class="tracking-widest uppercase flex items-center gap-1.5"
                :class="log.role === 'user' ? 'text-sky-600/70' : 'text-purple-500'"
              >
                <PixelIcon v-if="log.role !== 'user'" name="sparkle" size="xs" animation="spin" />
                {{ log.role === 'user' ? '主人' : activeAgent?.name || 'Pero' }}
                <PixelIcon v-if="log.role === 'user'" name="heart" size="xs" animation="pulse" />
              </span>
              <span class="opacity-40 font-mono text-[9px]">{{ log.displayTime }}</span>

              <!-- Tags -->
              <div class="flex items-center gap-2">
                <PTooltip
                  v-if="log.sentiment && log.sentiment !== 'neutral'"
                  :content="`情感: ${getSentimentLabel(log.sentiment)}`"
                >
                  <span
                    class="px-2.5 py-0.5 rounded-full bg-sky-50 text-sky-600 border border-sky-100 shadow-sm backdrop-blur-md flex items-center gap-1.5 hover:scale-105 transition-transform"
                  >
                    <PixelIcon :name="getSentimentEmoji(log.sentiment)" size="xs" />
                    <span class="text-[10px] font-bold">{{
                      getSentimentLabel(log.sentiment)
                    }}</span>
                  </span>
                </PTooltip>
                <span
                  v-if="log.importance > 1"
                  class="px-2.5 py-0.5 rounded-full bg-amber-50 text-amber-600 font-bold border border-amber-100 shadow-sm backdrop-blur-md flex items-center gap-1 hover:scale-105 transition-transform"
                >
                  <PixelIcon name="star" size="xs" />
                  {{ log.importance }}
                </span>
                <PTooltip
                  v-if="log.metadata?.memory_extracted || log.memory_id"
                  content="已提取记忆"
                >
                  <span
                    class="px-2.5 py-0.5 rounded-full bg-sky-50 text-sky-500 border border-sky-100 shadow-sm flex items-center gap-1.5 backdrop-blur-md hover:scale-105 transition-transform"
                  >
                    <PixelIcon name="brain" size="xs" />
                    <span class="text-[10px] font-bold flex items-center gap-1"
                      >已记下 <PixelIcon name="paw" size="xs"
                    /></span>
                  </span>
                </PTooltip>
                <span
                  v-if="log.analysis_status === 'processing'"
                  class="px-2.5 py-0.5 rounded-full bg-sky-50 text-sky-500 animate-pulse border border-sky-100 shadow-sm backdrop-blur-md"
                >
                  <PixelIcon name="refresh" size="xs" animation="spin" />
                </span>
                <PTooltip v-if="log.analysis_status === 'failed'" :content="log.last_error">
                  <span
                    class="px-2.5 py-0.5 rounded-full bg-rose-50 text-rose-500 cursor-help border border-rose-100 shadow-sm backdrop-blur-md"
                  >
                    <PixelIcon name="alert" size="xs" />
                  </span>
                </PTooltip>
              </div>
            </div>

            <!-- 气泡 -->
            <div
              class="relative px-7 py-5 rounded-[2.5rem] text-[14.5px] leading-relaxed shadow-xl transition-all duration-500 border group/bubble backdrop-blur-xl"
              :class="[
                log.role === 'user'
                  ? 'bg-sky-50/80 text-slate-700 rounded-tr-none border-sky-100 hover:border-sky-300 hover:bg-sky-100/90 shadow-sky-100/30'
                  : 'bg-white/80 text-slate-700 rounded-tl-none border-purple-100 hover:border-purple-300 hover:shadow-purple-100/50 shadow-purple-100/20',
                editingLogId === log.id ? 'w-full min-w-[400px]' : ''
              ]"
            >
              <!-- 机器人浮动图标 ✨ -->
              <div
                v-if="log.role !== 'user' && !editingLogId"
                class="absolute -right-5 -top-5 opacity-0 group-hover/bubble:opacity-100 transition-all duration-700 transform scale-0 group-hover/bubble:scale-125 rotate-12 group-hover/bubble:rotate-0 drop-shadow-[0_0_12px_rgba(192,132,252,0.4)] flex flex-col gap-1"
              >
                <PixelIcon name="sparkle" size="lg" animation="spin" />
                <PixelIcon name="heart" size="xs" animation="pulse" class="text-pink-400 ml-2" />
              </div>

              <!-- 用户浮动爪印 🐾 -->
              <div
                v-if="log.role === 'user' && !editingLogId"
                class="absolute -left-5 -top-5 opacity-0 group-hover/bubble:opacity-100 transition-all duration-700 transform scale-0 group-hover/bubble:scale-125 -rotate-12 group-hover/bubble:rotate-0 drop-shadow-[0_0_12px_rgba(14,165,233,0.3)]"
              >
                <PixelIcon name="paw" size="lg" animation="bounce" />
              </div>

              <!-- 编辑模式 -->
              <div v-if="editingLogId === log.id" class="space-y-4">
                <PTextarea
                  v-model="editingContent"
                  :rows="4"
                  placeholder="编辑内容..."
                  class="!rounded-2xl border-sky-200 focus:border-sky-400 transition-all"
                />
                <div class="flex items-center gap-3 justify-end">
                  <PButton size="sm" variant="ghost" class="rounded-xl" @click="cancelLogEdit"
                    >取消</PButton
                  >
                  <PButton
                    size="sm"
                    variant="primary"
                    class="rounded-xl px-6"
                    @click="saveLogEdit(log.id)"
                    >保存 💭</PButton
                  >
                </div>
              </div>

              <!-- 显示模式 -->
              <div v-else class="relative z-10">
                <!-- 图片 -->
                <div v-if="log.images && log.images.length > 0" class="flex flex-wrap gap-3 mb-3">
                  <div
                    v-for="(img, idx) in log.images"
                    :key="idx"
                    class="relative w-32 h-32 rounded-2xl overflow-hidden border border-sky-100 cursor-zoom-in group/img shadow-lg shadow-sky-100/40 hover:scale-105 transition-transform duration-500"
                    @click="openImageViewer(log.images, idx)"
                  >
                    <img :src="img" class="w-full h-full object-cover" />
                    <div
                      class="absolute inset-0 bg-sky-500/20 opacity-0 group-hover/img:opacity-100 transition-opacity flex items-center justify-center backdrop-blur-[2px]"
                    >
                      <PixelIcon name="eye" size="lg" class="text-white drop-shadow-md" />
                    </div>
                  </div>
                </div>

                <!-- 文本内容 -->
                <AsyncMarkdown
                  :content="formatLogContent(log.content)"
                  class="prose prose-sky prose-sm max-w-none"
                />
              </div>
            </div>

            <!-- 操作 -->
            <div
              class="flex items-center gap-3 mt-2 opacity-0 group-hover:opacity-100 transition-all duration-300 px-2"
            >
              <PTooltip v-if="log.analysis_status === 'failed'" content="重试分析">
                <button
                  class="p-1.5 text-amber-500 hover:bg-amber-500/15 rounded-xl transition-colors active:scale-90"
                  @click="retryLogAnalysis(log)"
                >
                  <PixelIcon name="refresh" size="xs" />
                </button>
              </PTooltip>
              <PTooltip content="编辑">
                <button
                  class="p-1.5 text-slate-500 hover:text-sky-400 hover:bg-sky-500/15 rounded-xl transition-all active:scale-90"
                  @click="startLogEdit(log)"
                >
                  <PixelIcon name="pencil" size="xs" />
                </button>
              </PTooltip>
              <PTooltip content="调试信息">
                <button
                  class="p-1.5 text-slate-500 hover:text-sky-400 hover:bg-sky-500/15 rounded-xl transition-all active:scale-90"
                  @click="openDebugDialog(log)"
                >
                  <PixelIcon name="terminal" size="xs" />
                </button>
              </PTooltip>
              <PTooltip content="删除">
                <button
                  class="p-1.5 text-slate-500 hover:text-rose-400 hover:bg-rose-500/15 rounded-xl transition-all active:scale-90"
                  @click="deleteLog(log.id)"
                >
                  <PixelIcon name="trash" size="xs" />
                </button>
              </PTooltip>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { inject } from 'vue'
import PCard from '@/components/ui/PCard.vue'
import PButton from '@/components/ui/PButton.vue'
import PSelect from '@/components/ui/PSelect.vue'
import PDatePicker from '@/components/ui/PDatePicker.vue'
import PEmpty from '@/components/ui/PEmpty.vue'
import PTextarea from '@/components/ui/PTextarea.vue'
import PTooltip from '@/components/ui/PTooltip.vue'
import PixelIcon from '@/components/ui/PixelIcon.vue'
import AsyncMarkdown from '@/components/markdown/AsyncMarkdown.vue'
import { LOGS_KEY, AGENT_CONFIG_KEY, DASHBOARD_KEY } from '@/composables/dashboard/injectionKeys'

const {
  logs,
  isLogsFetching,
  selectedSource,
  selectedSessionId,
  selectedDate,
  selectedSort,
  editingLogId,
  editingContent,
  fetchLogs,
  startLogEdit,
  cancelLogEdit,
  saveLogEdit,
  deleteLog,
  retryLogAnalysis,
  openDebugDialog,
  getSentimentEmoji,
  getSentimentLabel,
  formatLogContent
} = inject(LOGS_KEY)!
const { activeAgent, availableAgents, isSwitchingAgent, switchAgent } = inject(AGENT_CONFIG_KEY)!
const { openImageViewer } = inject(DASHBOARD_KEY)!
</script>
