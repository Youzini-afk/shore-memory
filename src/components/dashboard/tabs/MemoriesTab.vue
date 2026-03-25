<template>
  <!-- 3. 核心记忆 (重构版) -->
  <div class="h-full flex flex-col overflow-hidden">
    <!-- 工具栏 -->
    <div class="p-6 pb-0 flex-none">
      <PCard
        glass
        soft3d
        variant="purple"
        overflow-visible
        class="mb-4 !p-5 rounded-[2rem] relative group/mtoolbar z-30"
      >
        <!-- 背景装饰 ✨ -->
        <div
          class="absolute -right-20 -top-20 w-40 h-40 bg-purple-400/10 blur-[60px] rounded-full pointer-events-none group-hover/mtoolbar:bg-purple-400/20 transition-all duration-1000"
        ></div>

        <div class="flex flex-wrap items-end gap-5 relative z-10">
          <!-- 助手选择器 -->
          <div class="flex flex-col gap-2 min-w-[160px]">
            <label
              class="text-[11px] font-bold text-slate-500 flex items-center gap-1.5 ml-1 uppercase tracking-wider"
            >
              <span class="w-1.5 h-1.5 rounded-full bg-purple-500 animate-pulse"></span>
              角色
              <span class="opacity-50 font-normal">Agent</span>
            </label>
            <div class="relative group/magent">
              <button
                class="w-full flex items-center justify-between px-4 py-2.5 bg-purple-50/50 hover:bg-purple-100/50 border border-purple-100/50 hover:border-purple-300 rounded-2xl text-sm transition-all active:scale-95 shadow-lg shadow-black/30 backdrop-blur-md group/mbtn hover-pixel-bounce"
                :class="isSwitchingAgent ? 'opacity-50 cursor-not-allowed' : ''"
              >
                <span class="text-purple-600 font-bold flex items-center gap-2">
                  <img
                    v-if="activeAgent?.avatarUrl"
                    :src="activeAgent.avatarUrl"
                    class="w-6 h-6 rounded-lg object-cover"
                    alt="Avatar"
                  />
                  <span
                    v-else
                    class="text-xs opacity-0 group-hover/mbtn:opacity-100 transition-all duration-300 -translate-x-2 group-hover:translate-x-0"
                    ><PixelIcon name="paw" size="xs" animation="bounce"
                  /></span>
                  {{ activeAgent?.name || '未知' }}
                </span>
                <PixelIcon
                  name="chevron-down"
                  size="xs"
                  class="text-slate-400 group-hover/magent:rotate-180 transition-transform duration-500"
                />
              </button>
              <div
                class="absolute left-0 top-full mt-3 w-full py-2 bg-white/70 backdrop-blur-2xl border border-purple-100 rounded-2xl shadow-2xl shadow-purple-200/40 opacity-0 invisible group-hover/magent:opacity-100 group-hover/magent:visible transition-all duration-500 z-50 transform origin-top scale-90 group-hover/magent:scale-100 ring-1 ring-purple-100/5"
              >
                <button
                  v-for="agent in availableAgents"
                  :key="agent.id"
                  class="w-full text-left px-4 py-2.5 text-sm hover:bg-purple-50 transition-all flex items-center justify-between group/mitem"
                  :class="{
                    'text-purple-600 font-bold bg-purple-50': agent.id === activeAgent?.id,
                    'text-slate-500': agent.id !== activeAgent?.id
                  }"
                  :disabled="agent.id === activeAgent?.id || !agent.is_enabled"
                  @click="switchAgent(agent.id)"
                >
                  <span
                    class="group-hover/mitem:translate-x-1.5 transition-transform flex items-center gap-2"
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
                      class="text-[10px] text-slate-400 font-bold bg-slate-50 px-1.5 py-0.5 rounded-lg border border-slate-200"
                      >禁用</span
                    >
                    <span v-if="agent.id === activeAgent?.id" class="text-purple-400"
                      ><PixelIcon name="heart" size="xs"
                    /></span>
                  </div>
                </button>
              </div>
            </div>
          </div>

          <!-- 筛选类型 -->
          <div class="flex flex-col gap-2 w-[160px]">
            <label
              class="text-[11px] font-bold text-slate-500 flex items-center gap-1.5 ml-1 uppercase tracking-wider"
            >
              <span class="w-1.5 h-1.5 rounded-full bg-purple-500"></span> 类型
              <span class="opacity-50 font-normal">Type</span>
            </label>
            <PSelect
              v-model="memoryFilterType"
              :options="[
                { label: '全部类型', value: '', icon: 'sparkle' },
                { label: '记忆块 (Event)', value: 'event', icon: 'puzzle' },
                { label: '事实 (Fact)', value: 'fact', icon: 'brain' },
                { label: '誓言 (Promise)', value: 'promise', icon: 'handshake' },
                { label: '偏好 (Preference)', value: 'preference', icon: 'heart' },
                { label: '工作日志 (Log)', value: 'work_log', icon: 'pencil' },
                { label: '归档 (Archived)', value: 'archived_event', icon: 'archive' }
              ]"
              size="md"
              class="!rounded-2xl shadow-lg shadow-black/30 backdrop-blur-md"
              @change="fetchMemories"
            >
              <template #option="{ option }">
                <div class="flex items-center gap-2 text-xs">
                  <PixelIcon v-if="option.icon" :name="option.icon" size="xs" class="opacity-70" />
                  <span>{{ option.label }}</span>
                </div>
              </template>
            </PSelect>
          </div>

          <!-- 日期筛选 -->
          <div class="flex flex-col gap-2 w-[160px]">
            <label
              class="text-[11px] font-bold text-slate-500 flex items-center gap-1.5 ml-1 uppercase tracking-wider"
            >
              <span class="w-1.5 h-1.5 rounded-full bg-purple-500"></span> 日期
              <span class="opacity-50 font-normal">Date</span>
            </label>
            <div class="relative group/mdate">
              <PDatePicker
                v-model="memoryFilterDate"
                placeholder="选择日期"
                class="!rounded-2xl shadow-lg shadow-black/30 backdrop-blur-md"
                @update:model-value="fetchMemories"
              />
              <div
                class="absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none opacity-40 group-hover/mdate:opacity-100 transition-opacity"
              >
                <PixelIcon name="calendar" size="xs" />
              </div>
            </div>
          </div>

          <!-- 视图模式 -->
          <div
            class="flex bg-purple-50/50 p-1 rounded-2xl border border-purple-100 self-end h-[42px] items-center relative group/vmode shadow-lg shadow-black/30 backdrop-blur-md"
          >
            <!-- 🐾 浮动装饰 -->
            <div
              class="absolute -top-6 left-1/2 -translate-x-1/2 text-[10px] opacity-0 group-hover/vmode:opacity-60 transition-all duration-500 translate-y-2 group-hover/vmode:translate-y-0"
            >
              <PixelIcon name="paw" size="xs" animation="bounce" />
            </div>

            <div
              class="absolute h-[34px] bg-white border border-purple-200 rounded-xl transition-all duration-500 ease-out pointer-events-none shadow-sm shadow-purple-100/50"
              :style="{
                left: memoryViewMode === 'list' ? '4px' : '56px',
                width: memoryViewMode === 'list' ? '48px' : '48px'
              }"
            ></div>
            <PTooltip
              v-for="mode in [
                { id: 'list', icon: 'list', label: '列表' },
                { id: 'graph', icon: 'chart', label: '图谱' }
              ]"
              :key="mode.id"
              :content="mode.label"
            >
              <button
                class="relative flex items-center justify-center w-12 py-1.5 rounded-xl text-xs font-medium transition-all z-10 hover:scale-110 active:scale-90 group/vbtn"
                :class="
                  memoryViewMode === mode.id
                    ? 'text-purple-600 font-bold'
                    : 'text-slate-400 hover:text-purple-500'
                "
                @click="
                  () => {
                    memoryViewMode = mode.id
                    if (mode.id === 'graph') fetchMemoryGraph()
                  }
                "
              >
                <PixelIcon
                  :name="mode.icon"
                  size="sm"
                  class="transition-transform duration-500 group-hover/vbtn:rotate-12"
                />
              </button>
            </PTooltip>
          </div>

          <!-- 操作 -->
          <div class="flex items-center gap-3 pb-0.5 ml-auto">
            <PTooltip content="清除无效连线">
              <PButton
                variant="danger"
                size="sm"
                :loading="isClearingEdges"
                class="!rounded-xl flat-action-btn"
                @click="clearOrphanedEdges"
                ><div class="flex items-center gap-1.5">
                  <PixelIcon name="trash" size="xs" />清理
                </div></PButton
              >
            </PTooltip>
            <PTooltip content="扫描孤立记忆">
              <PButton
                variant="primary"
                size="sm"
                :loading="isScanningLonely"
                class="!rounded-xl flat-action-btn"
                @click="triggerScanLonely"
                ><div class="flex items-center gap-1.5">
                  <PixelIcon name="search" size="xs" />扫描
                </div></PButton
              >
            </PTooltip>
            <PTooltip content="每日深度维护">
              <PButton
                variant="warning"
                size="sm"
                :loading="isRunningMaintenance"
                class="!rounded-xl flat-action-btn"
                @click="triggerMaintenance"
                ><div class="flex items-center gap-1.5">
                  <PixelIcon name="settings" size="xs" />维护
                </div></PButton
              >
            </PTooltip>
            <PTooltip content="触发梦境联想">
              <PButton
                variant="success"
                size="sm"
                :loading="isDreaming"
                class="!rounded-xl flat-action-btn"
                @click="triggerDream"
                ><div class="flex items-center gap-1.5">
                  <PixelIcon name="sparkle" size="xs" />梦境
                </div></PButton
              >
            </PTooltip>
          </div>
        </div>

        <!-- Tags -->
        <div
          v-if="topTags.length"
          class="mt-5 flex items-center gap-3 overflow-x-auto pb-1.5 custom-scrollbar group/tags"
        >
          <span
            class="text-[11px] font-bold text-slate-500 shrink-0 flex items-center gap-2 uppercase tracking-wider"
          >
            <span
              class="text-xs opacity-0 group-hover/tags:opacity-100 transition-all duration-500 -translate-x-2 group-hover/tags:translate-x-0"
              >🐾</span
            >
            热门标签 <span class="opacity-40 font-normal">Tags</span>:
          </span>
          <div class="flex items-center gap-2">
            <button
              v-for="{ tag, count } in topTags"
              :key="tag"
              class="px-4 py-1.5 rounded-full text-[10px] font-bold transition-all border shrink-0 active:scale-90 flex items-center gap-2 group/tag backdrop-blur-md"
              :class="
                memoryFilterTags.includes(tag)
                  ? 'bg-sky-500/20 text-sky-600 border-sky-500/40 shadow-lg shadow-sky-500/20'
                  : 'bg-sky-50/50 text-slate-500 border-sky-100 hover:bg-sky-100/50 hover:border-sky-300 hover:text-sky-600'
              "
              @click="
                () => {
                  if (memoryFilterTags.includes(tag))
                    memoryFilterTags = memoryFilterTags.filter((t: string) => t !== tag)
                  else memoryFilterTags.push(tag)
                  fetchMemories()
                }
              "
            >
              <span
                class="opacity-0 w-0 group-hover/tag:w-auto group-hover/tag:opacity-100 transition-all duration-500 overflow-hidden"
                >✨</span
              >
              # {{ tag }}
              <span
                v-if="count > 1"
                class="text-[9px] opacity-40 group-hover:opacity-100 transition-opacity"
                >({{ count }})</span
              >
            </button>
          </div>
        </div>
      </PCard>
    </div>

    <!-- 列表模式 -->
    <div
      v-show="memoryViewMode === 'list'"
      class="flex-1 overflow-y-auto px-6 pb-6 custom-scrollbar"
    >
      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
        <div
          v-for="m in memories"
          :key="m.id"
          class="group relative bg-white/80 hover:bg-sky-50/50 border border-sky-100 hover:border-sky-300 rounded-2xl p-4 transition-all duration-300 flex flex-col h-[280px] hover:-translate-y-1 hover:shadow-xl hover:shadow-sky-100/30"
        >
          <!-- 悬停效果 ✨ -->
          <div
            class="absolute -top-1.5 -right-1.5 opacity-0 group-hover:opacity-100 transition-all duration-300 scale-0 group-hover:scale-110 z-20"
          >
            <div class="bg-sky-500 shadow-lg shadow-sky-500/40 rounded-full p-1.5">
              <PixelIcon name="sparkle" size="xs" class="text-white" />
            </div>
          </div>

          <!-- 头部 -->
          <div class="flex items-start justify-between mb-3">
            <div class="flex flex-wrap gap-2">
              <span
                class="px-2 py-0.5 rounded-full text-[10px] uppercase font-bold tracking-wider bg-sky-100 text-sky-600 border border-sky-200 shadow-sm shadow-sky-100/10"
              >
                {{ getMemoryTypeLabel(m.type) }}
              </span>
              <span
                v-if="m.sentiment && m.sentiment !== 'neutral'"
                class="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full bg-white/50 border border-sky-100 shadow-sm animate-bounce"
                style="animation-duration: 3s"
              >
                <PixelIcon :name="getSentimentEmoji(m.sentiment)" size="xs" class="text-sky-500" />
                <span class="text-[10px] font-bold text-sky-600">{{
                  getSentimentLabel(m.sentiment)
                }}</span>
              </span>
            </div>
            <button
              class="p-1.5 rounded-lg text-slate-400 hover:text-rose-500 hover:bg-rose-50 transition-all opacity-0 group-hover:opacity-100 active:scale-90"
              @click="deleteMemory(m.id)"
            >
              <PixelIcon name="trash" size="xs" />
            </button>
          </div>

          <!-- 内容 -->
          <div
            class="flex-1 overflow-y-auto custom-scrollbar mb-3 text-sm text-slate-600 leading-relaxed group-hover:text-slate-700 transition-colors"
          >
            {{ m.content }}
          </div>

          <!-- 底部 -->
          <div class="mt-auto pt-3 border-t border-sky-100/50 flex flex-col gap-2">
            <div class="flex flex-wrap gap-1">
              <span
                v-for="c in m.clusters ? m.clusters.split(',') : []"
                :key="c"
                class="px-1.5 py-0.5 rounded-full text-[10px] bg-amber-50 text-amber-600 border border-amber-100"
              >
                {{ c.replace(/[\[\]]/g, '') }}
              </span>
              <span
                v-for="t in m.tags ? m.tags.split(',') : []"
                :key="t"
                class="px-1.5 py-0.5 rounded-full text-[10px] bg-sky-50 text-sky-600 border border-sky-100"
              >
                #{{ t }}
              </span>
            </div>

            <div class="flex items-center justify-between text-[10px] text-slate-400 font-mono">
              <div class="flex gap-2">
                <PTooltip content="重要度">
                  <span class="flex items-center gap-0.5">
                    ⭐ <span class="text-amber-500/80">{{ m.importance }}</span>
                  </span>
                </PTooltip>
                <PTooltip content="活跃度">
                  <span class="flex items-center gap-0.5">
                    🔥
                    <span class="text-rose-500/80">{{ m.access_count || 0 }}</span>
                  </span>
                </PTooltip>
              </div>
              <span class="group-hover:text-slate-500 transition-colors">{{ m.realTime }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 图谱模式 -->
    <div
      v-show="memoryViewMode === 'graph'"
      v-loading="isLoadingGraph"
      class="flex-1 flex gap-4 p-6 pt-0 overflow-hidden"
    >
      <div
        v-if="memoryGraphData.nodes.length === 0"
        class="flex-1 flex items-center justify-center"
      >
        <PEmpty description="暂无关联数据或数据量过少" />
      </div>
      <div v-else class="flex-1 flex gap-4 h-full">
        <!-- 图表 -->
        <div
          ref="graphRef"
          class="flex-1 h-full bg-sky-50/30 border border-sky-100 rounded-xl overflow-hidden"
        ></div>

        <!-- 图例 -->
        <div
          class="w-64 bg-white/90 backdrop-blur border border-sky-100 rounded-xl p-4 overflow-y-auto custom-scrollbar"
        >
          <h4 class="text-sm font-bold text-slate-700 mb-4 flex items-center gap-2">
            <PixelIcon name="chart" size="xs" class="text-sky-400" /> 图谱图例 🎨✨
          </h4>

          <div class="space-y-4">
            <div class="group/item cursor-help transition-all hover:translate-x-1">
              <div class="text-xs font-bold text-slate-500 mb-1 flex items-center gap-1">
                <span class="w-1.5 h-1.5 rounded-full bg-sky-400 animate-pulse"></span> 🧠 节点
                (Node)
              </div>
              <p class="text-[10px] text-slate-400 leading-relaxed group-hover/item:text-slate-500">
                代表独立的记忆片段。颜色代表情感，大小代表重要度。🐾
              </p>
            </div>

            <div class="group/item cursor-help transition-all hover:translate-x-1">
              <div class="text-xs font-bold text-slate-500 mb-1 flex items-center gap-1">
                <span class="w-3 h-[1.5px] bg-sky-500/50"></span> 🔗 连线 (Edge)
              </div>
              <p class="text-[10px] text-slate-400 leading-relaxed group-hover/item:text-slate-500">
                代表记忆之间的逻辑关联。🤝
              </p>
            </div>

            <div>
              <div class="text-xs font-bold text-slate-500 mb-2 flex items-center gap-1">
                🎨 情感 (Sentiment)
                <span class="text-[10px] opacity-50 font-normal">颜色参考</span>
              </div>
              <div class="flex gap-2 flex-wrap">
                <span
                  class="px-2 py-0.5 rounded-full text-[10px] bg-sky-50 text-sky-600 border border-sky-100 hover:bg-sky-100 transition-colors"
                  >正面 😊</span
                >
                <span
                  class="px-2 py-0.5 rounded-full text-[10px] bg-rose-50 text-rose-600 border border-rose-100 hover:bg-rose-100 transition-colors"
                  >负面 😟</span
                >
                <span
                  class="px-2 py-0.5 rounded-full text-[10px] bg-sky-50 text-slate-500 border border-sky-100 hover:bg-sky-100 transition-colors"
                  >中性 😐</span
                >
              </div>
            </div>

            <div class="pt-4 border-t border-sky-100">
              <p class="text-[10px] text-slate-400 flex justify-between">
                <span>当前节点:</span>
                <span class="text-slate-600 font-mono">{{ memoryGraphData.nodes.length }}</span>
              </p>
              <p class="text-[10px] text-slate-400 flex justify-between mt-1">
                <span>当前连线:</span>
                <PTooltip content="记忆强度">
                  <span class="text-slate-600 font-mono cursor-help">{{
                    memoryGraphData.edges.length
                  }}</span>
                </PTooltip>
              </p>
              <p class="text-[10px] text-slate-400 flex justify-between mt-1">
                <span>上次激活:</span>
                <PTooltip content="上次激活时间">
                  <span class="text-slate-600 font-mono cursor-help">{{
                    memoryGraphData.lastActive
                      ? new Date(memoryGraphData.lastActive).toLocaleTimeString()
                      : '-'
                  }}</span>
                </PTooltip>
              </p>
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
import PTooltip from '@/components/ui/PTooltip.vue'
import PixelIcon from '@/components/ui/PixelIcon.vue'
import { MEMORIES_KEY, AGENT_CONFIG_KEY, LOGS_KEY } from '@/composables/dashboard/injectionKeys'

const {
  memories,
  memoryFilterTags,
  memoryFilterDate,
  memoryFilterType,
  memoryViewMode,
  memoryGraphData,
  isLoadingGraph,
  graphRef,
  topTags,
  isClearingEdges,
  isScanningLonely,
  isRunningMaintenance,
  isDreaming,
  fetchMemories,
  fetchMemoryGraph,
  deleteMemory,
  clearOrphanedEdges,
  triggerScanLonely,
  triggerMaintenance,
  triggerDream,
  getMemoryTypeLabel
} = inject(MEMORIES_KEY)!
const { activeAgent, availableAgents, isSwitchingAgent, switchAgent } = inject(AGENT_CONFIG_KEY)!

// getSentimentEmoji / getSentimentLabel 来自 logs composable
const { getSentimentEmoji, getSentimentLabel } = inject(LOGS_KEY)!
</script>
