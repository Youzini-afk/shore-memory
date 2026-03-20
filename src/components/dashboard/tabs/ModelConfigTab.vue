<template>
  <!-- 5. 模型配置 (重构版) -->
  <div class="h-full flex flex-col overflow-hidden">
    <!-- Toolbar & Tabs -->
    <div class="p-6 pb-0 flex-none">
      <PCard
        glass
        soft3d
        variant="sky"
        overflow-visible
        class="mb-4 !p-5 rounded-[2rem] relative group/mtoolbar z-30"
      >
        <!-- 背景装饰 ✨ -->
        <div
          class="absolute -right-20 -top-20 w-40 h-40 bg-sky-400/10 blur-[60px] rounded-full pointer-events-none group-hover/mtoolbar:bg-sky-400/20 transition-all duration-1000"
        ></div>

        <div class="flex flex-wrap items-center justify-between gap-5 relative z-10">
          <div class="flex items-center gap-4">
            <div
              class="p-3 bg-sky-50 rounded-2xl text-sky-500 border border-sky-100 shadow-sm shadow-sky-200/20 group-hover/mtoolbar:scale-110 group-hover/mtoolbar:rotate-6 transition-all duration-500"
            >
              <PixelIcon name="settings" size="md" animation="spin" />
            </div>
            <div>
              <div class="flex items-center gap-3 mb-1">
                <button
                  class="text-xl font-bold transition-all"
                  :class="
                    currentModelTab === 'llm'
                      ? 'text-slate-800 scale-105'
                      : 'text-slate-400 hover:text-slate-600'
                  "
                  @click="currentModelTab = 'llm'"
                >
                  模型配置
                </button>
                <span class="text-slate-200 text-xl">/</span>
                <button
                  class="text-xl font-bold transition-all"
                  :class="
                    currentModelTab === 'vector'
                      ? 'text-slate-800 scale-105'
                      : 'text-slate-400 hover:text-slate-600'
                  "
                  @click="currentModelTab = 'vector'"
                >
                  向量模型
                </button>
                <span
                  class="text-xs font-normal text-slate-400 tracking-widest uppercase ml-1 opacity-50 group-hover/mtoolbar:opacity-100 transition-opacity"
                  ># {{ currentModelTab.toUpperCase() }}</span
                >
              </div>
              <p class="text-xs text-slate-500 flex items-center gap-1.5 mt-0.5">
                {{
                  currentModelTab === 'llm'
                    ? '配置 Pero 的大脑，支持多模型协作'
                    : '配置记忆系统的 Embedding 与 Reranker 模型'
                }}
                <span class="group-hover/mtoolbar:animate-pulse">✨ 🐾</span>
              </p>
            </div>
          </div>

          <div v-if="currentModelTab === 'llm'" class="flex items-center gap-3">
            <PButton
              variant="secondary"
              class="!rounded-2xl shadow-lg shadow-sky-200/20 hover:scale-105 active:scale-95 transition-all px-5 border-sky-100 hover:border-sky-300 hover-pixel-bounce"
              @click="openGlobalSettings"
            >
              <div class="flex items-center gap-1.5">
                <PixelIcon name="globe" size="xs" />
                全局服务商 <span class="ml-1 opacity-60">Global</span>
              </div>
            </PButton>
            <PButton
              variant="primary"
              class="!rounded-2xl shadow-lg shadow-sky-400/20 hover:scale-105 active:scale-95 transition-all px-6 hover-pixel-bounce"
              @click="openModelEditor(null)"
            >
              <div class="flex items-center gap-1.5">
                <PixelIcon name="plus" size="xs" />
                添加模型 <span class="ml-1 opacity-80">Add New</span>
              </div>
            </PButton>
          </div>
          <div v-else class="flex items-center gap-3">
            <PButton
              variant="secondary"
              class="!rounded-2xl shadow-lg shadow-sky-200/20 hover:scale-105 active:scale-95 transition-all px-5 border-sky-100 hover:border-sky-300"
              :loading="isReindexing"
              @click="triggerReindex"
            >
              <div class="flex items-center gap-1.5">
                <PixelIcon name="refresh" size="xs" />
                全量重索引 <span class="ml-1 opacity-60">Reindex</span>
              </div>
            </PButton>
            <PButton
              variant="primary"
              class="!rounded-2xl shadow-lg shadow-sky-400/20 hover:scale-105 active:scale-95 transition-all px-8"
              :loading="isSaving"
              @click="saveVectorConfig"
            >
              保存配置 <span class="ml-1 opacity-80">Save</span>
            </PButton>
          </div>
        </div>
      </PCard>
    </div>

    <!-- Models Grid (LLM Tab) -->
    <div v-if="currentModelTab === 'llm'" class="flex-1 overflow-y-auto px-6 py-4 custom-scrollbar">
      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6 pb-8">
        <div v-for="model in models" :key="model.id" class="group relative">
          <!-- 卡片主体 -->
          <PCard
            glass
            soft3d
            hoverable
            class="h-full !p-6 !rounded-[2rem] transition-all duration-500 overflow-hidden flex flex-col group/mcard"
            :class="[
              currentActiveModelId === model.id
                ? 'border-sky-300 bg-sky-50/50 ring-1 ring-sky-200'
                : '',
              secretaryModelId === model.id ? 'border-amber-300 bg-amber-50/50' : '',
              reflectionModelId === model.id ? 'border-rose-300 bg-rose-50/50' : ''
            ]"
          >
            <!-- 背景装饰 ✨ -->
            <div
              class="absolute -right-10 -top-10 w-24 h-24 blur-[40px] rounded-full pointer-events-none transition-all duration-700 opacity-10 group-hover/mcard:opacity-30"
              :class="[
                currentActiveModelId === model.id ? 'bg-sky-400' : 'bg-sky-200',
                secretaryModelId === model.id ? 'bg-amber-400' : '',
                reflectionModelId === model.id ? 'bg-rose-400' : ''
              ]"
            ></div>

            <!-- 头部信息 -->
            <div class="flex items-start justify-between mb-5 relative z-10">
              <div class="flex-1 min-w-0 pr-4">
                <PTooltip :content="model.name">
                  <h3
                    class="text-lg font-bold text-slate-700 truncate group-hover/mcard:text-slate-900 transition-colors"
                  >
                    {{ model.name }}
                  </h3>
                </PTooltip>
                <div class="flex items-center gap-2 mt-1.5">
                  <span
                    class="text-[10px] font-mono text-slate-400 uppercase tracking-widest group-hover/mcard:text-slate-500"
                  >
                    {{ model.provider }}
                  </span>
                  <div
                    v-if="model.enable_vision"
                    class="flex items-center gap-1 px-1.5 py-0.5 rounded-md bg-sky-50 text-sky-500 border border-sky-100 text-[9px] font-bold"
                  >
                    <PixelIcon name="eye" size="xs" /> VISION
                  </div>
                </div>
              </div>

              <!-- 角色指示器 (图标) -->
              <div class="flex -space-x-2">
                <PTooltip v-if="currentActiveModelId === model.id" content="主模型 (Main)">
                  <div
                    class="w-8 h-8 rounded-full bg-sky-400 flex items-center justify-center text-white shadow-lg shadow-sky-400/30 border-2 border-white z-30"
                  >
                    <PixelIcon name="terminal" size="sm" />
                  </div>
                </PTooltip>
                <PTooltip v-if="secretaryModelId === model.id" content="秘书模型 (Secretary)">
                  <div
                    class="w-8 h-8 rounded-full bg-amber-400 flex items-center justify-center text-white shadow-lg shadow-amber-400/30 border-2 border-white z-20"
                  >
                    <PixelIcon name="chat" size="sm" />
                  </div>
                </PTooltip>
                <PTooltip v-if="reflectionModelId === model.id" content="反思模型 (Reflection)">
                  <div
                    class="w-8 h-8 rounded-full bg-rose-400 flex items-center justify-center text-white shadow-lg shadow-rose-400/30 border-2 border-white z-10"
                  >
                    <PixelIcon name="brain" size="sm" />
                  </div>
                </PTooltip>
                <PTooltip v-if="auxModelId === model.id" content="辅助模型 (Aux)">
                  <div
                    class="w-8 h-8 rounded-full bg-indigo-400 flex items-center justify-center text-white shadow-lg shadow-indigo-400/30 border-2 border-white z-0"
                  >
                    <PixelIcon name="sparkle" size="sm" />
                  </div>
                </PTooltip>
              </div>
            </div>

            <!-- 统计 / 信息 -->
            <div class="space-y-3 mb-6 relative z-10">
              <div class="flex items-center justify-between text-[11px]">
                <span class="text-slate-400">模型 ID</span>
                <span class="text-slate-500 font-mono truncate max-w-[120px]">{{
                  model.model_id
                }}</span>
              </div>
              <div class="flex items-center justify-between text-[11px]">
                <span class="text-slate-400">上下文窗口</span>
                <span class="text-slate-500 font-mono">{{
                  model.max_tokens ? (model.max_tokens / 1024).toFixed(0) + 'K' : '自动'
                }}</span>
              </div>
            </div>

            <!-- 操作按钮 (常驻但带主题色) -->
            <div
              class="mt-auto pt-4 border-t border-sky-100/30 flex items-center justify-end gap-2 relative z-30"
            >
              <PTooltip content="编辑模型" placement="top">
                <button
                  class="p-2 rounded-xl text-slate-400 hover:text-sky-500 hover:bg-sky-50 transition-all active:scale-90 group/btn-edit"
                  @click="openModelEditor(model)"
                >
                  <PixelIcon
                    name="pencil"
                    size="xs"
                    class="group-hover/btn-edit:rotate-12 transition-transform"
                  />
                </button>
              </PTooltip>
              <PTooltip content="删除模型" placement="top">
                <button
                  class="p-2 rounded-xl text-slate-400 hover:text-rose-500 hover:bg-rose-50 transition-all active:scale-90 group/btn-del"
                  @click="deleteModel(model.id)"
                >
                  <PixelIcon
                    name="trash"
                    size="xs"
                    class="group-hover/btn-del:shake transition-transform"
                  />
                </button>
              </PTooltip>
            </div>

            <!-- 快速切换角色操作 (仅悬停显示) - 优化后的设计 ✨ -->
            <div
              class="absolute left-1/2 -translate-x-1/2 bottom-12 bg-white/90 backdrop-blur-2xl p-2.5 rounded-2xl border border-sky-100/50 opacity-0 group-hover/mcard:opacity-100 translate-y-2 group-hover/mcard:translate-y-0 transition-all duration-500 z-40 flex gap-1.5 justify-center shadow-2xl shadow-sky-200/40 pointer-events-none group-hover/mcard:pointer-events-auto border-b-2 border-b-sky-200/50"
            >
              <div
                class="absolute -top-2 left-1/2 -translate-x-1/2 px-2 py-0.5 bg-sky-500 rounded-full text-[7px] text-white font-black tracking-widest uppercase shadow-sm whitespace-nowrap"
              >
                Quick Roles
              </div>
              <PTooltip content="设为主模型" placement="top">
                <button
                  class="p-2 rounded-xl transition-all active:scale-90"
                  :class="
                    currentActiveModelId === model.id
                      ? 'bg-sky-500 text-white shadow-lg shadow-sky-200 soft-3d-shadow'
                      : 'bg-sky-50/50 text-sky-500 hover:bg-sky-100 border border-sky-100/50'
                  "
                  @click="setActiveModel(model.id)"
                >
                  <PixelIcon name="terminal" size="xs" />
                </button>
              </PTooltip>
              <PTooltip content="设为秘书模型" placement="top">
                <button
                  class="p-2 rounded-xl transition-all active:scale-90"
                  :class="
                    secretaryModelId === model.id
                      ? 'bg-amber-400 text-white shadow-lg shadow-amber-200 soft-3d-shadow'
                      : 'bg-amber-50/50 text-amber-500 hover:bg-amber-100 border border-amber-100/50'
                  "
                  @click="setSecretaryModel(model.id)"
                >
                  <PixelIcon name="chat" size="xs" />
                </button>
              </PTooltip>
              <PTooltip content="设为反思模型" placement="top">
                <button
                  class="p-2 rounded-xl transition-all active:scale-90"
                  :class="
                    reflectionModelId === model.id
                      ? 'bg-rose-400 text-white shadow-lg shadow-rose-200 soft-3d-shadow'
                      : 'bg-rose-50/50 text-rose-500 hover:bg-rose-100 border border-rose-100/50'
                  "
                  @click="setReflectionModel(model.id)"
                >
                  <PixelIcon name="brain" size="xs" />
                </button>
              </PTooltip>
              <PTooltip content="设为辅助模型" placement="top">
                <button
                  class="p-2 rounded-xl transition-all active:scale-90"
                  :class="
                    auxModelId === model.id
                      ? 'bg-indigo-400 text-white shadow-lg shadow-indigo-200 soft-3d-shadow'
                      : 'bg-indigo-50/50 text-indigo-500 hover:bg-indigo-100 border border-indigo-100/50'
                  "
                  @click="setAuxModel(model.id)"
                >
                  <PixelIcon name="sparkle" size="xs" />
                </button>
              </PTooltip>
            </div>
          </PCard>
        </div>
      </div>
    </div>

    <!-- Vector Models Config (Vector Tab) -->
    <div v-else class="flex-1 overflow-y-auto px-6 py-4 custom-scrollbar">
      <div class="max-w-4xl mx-auto space-y-8 pb-12">
        <!-- Embedding Section -->
        <PCard pixel class="!p-8 !overflow-visible">
          <div class="flex items-center gap-4 mb-8">
            <div class="p-3 bg-sky-100 rounded-2xl text-sky-600">
              <PixelIcon name="brain" size="md" />
            </div>
            <div>
              <h4 class="text-lg font-bold text-slate-800">Embedding 嵌入模型</h4>
              <p class="text-sm text-slate-500">将记忆文本转换为数学向量，是 RAG 检索的核心</p>
            </div>
          </div>

          <div class="grid grid-cols-1 md:grid-cols-2 gap-x-8 gap-y-6">
            <div class="space-y-2 relative z-50">
              <label class="text-xs font-black text-slate-400 uppercase tracking-widest ml-1"
                >模型来源 Provider</label
              >
              <PSelect
                v-model="embeddingProvider"
                :options="[
                  { label: '本地内置 (MiniLM-384)', value: 'local' },
                  { label: '在线 API (OpenAI 兼容)', value: 'api' }
                ]"
                @change="handleEmbeddingProviderChange"
              />
            </div>

            <div class="space-y-2">
              <label class="text-xs font-black text-slate-400 uppercase tracking-widest ml-1"
                >向量维度 Dimension</label
              >
              <PInputNumber
                v-model="embeddingDimension"
                :min="1"
                :max="4096"
                :disabled="embeddingProvider === 'local'"
              />
              <p
                v-if="embeddingProvider === 'local'"
                class="text-[10px] text-slate-400 mt-1 italic"
              >
                * 本地模型固定为 384 维
              </p>
            </div>

            <div v-if="embeddingProvider === 'api'" class="space-y-2 md:col-span-2">
              <label
                class="text-xs font-black text-slate-400 uppercase tracking-widest ml-1 flex items-center justify-between"
              >
                <span>模型 ID Model ID</span>
                <button
                  class="text-sky-500 hover:text-sky-600 transition-colors flex items-center gap-1 active:scale-95"
                  :disabled="isFetchingEmbeddingModels"
                  @click="fetchRemoteVectorModels('embedding')"
                >
                  <PixelIcon
                    :name="isFetchingEmbeddingModels ? 'refresh' : 'search'"
                    size="xs"
                    :animation="isFetchingEmbeddingModels ? 'spin' : ''"
                  />
                  {{ isFetchingEmbeddingModels ? '获取中...' : '查询模型' }}
                </button>
              </label>
              <PInput v-model="embeddingModelId" placeholder="例如: text-embedding-3-small" />
              <!-- 可选模型列表 🐈 -->
              <div
                v-if="availableEmbeddingModels.length > 0"
                class="flex flex-wrap gap-2 mt-2 max-h-[100px] overflow-y-auto custom-scrollbar p-1"
              >
                <button
                  v-for="m in availableEmbeddingModels"
                  :key="m"
                  class="px-3 py-1 text-[10px] rounded-full border border-sky-100 bg-sky-50 text-sky-600 hover:bg-sky-500 hover:text-white transition-all active:scale-90"
                  :class="{
                    '!bg-sky-500 !text-white !border-sky-500': embeddingModelId === m
                  }"
                  @click="embeddingModelId = m"
                >
                  {{ m }}
                </button>
              </div>
            </div>

            <div v-if="embeddingProvider === 'api'" class="space-y-2">
              <label class="text-xs font-black text-slate-400 uppercase tracking-widest ml-1"
                >API Base URL (可选)</label
              >
              <PInput v-model="embeddingApiBase" placeholder="留空则使用全局配置" />
            </div>

            <div v-if="embeddingProvider === 'api'" class="space-y-2">
              <label class="text-xs font-black text-slate-400 uppercase tracking-widest ml-1"
                >API Key (可选)</label
              >
              <PInput v-model="embeddingApiKey" type="password" placeholder="留空则使用全局配置" />
            </div>
          </div>
        </PCard>

        <!-- Reranker Section -->
        <PCard pixel class="!p-8 !overflow-visible">
          <div class="flex items-center gap-4 mb-8">
            <div class="p-3 bg-amber-100 rounded-2xl text-amber-600">
              <PixelIcon name="sparkle" size="md" />
            </div>
            <div>
              <h4 class="text-lg font-bold text-slate-800">Reranker 重排序模型</h4>
              <p class="text-sm text-slate-500">对初步检索的结果进行精排，大幅提升回答准确度</p>
            </div>
          </div>

          <div class="grid grid-cols-1 md:grid-cols-2 gap-x-8 gap-y-6">
            <div class="space-y-2 relative z-40">
              <label class="text-xs font-black text-slate-400 uppercase tracking-widest ml-1"
                >模型来源 Provider</label
              >
              <PSelect
                v-model="rerankerProvider"
                :options="[
                  { label: '本地内置 (BGE-M3)', value: 'local' },
                  { label: '在线 API (SiliconFlow等)', value: 'api' }
                ]"
              />
            </div>

            <div v-if="rerankerProvider === 'api'" class="space-y-2 md:col-span-2">
              <label
                class="text-xs font-black text-slate-400 uppercase tracking-widest ml-1 flex items-center justify-between"
              >
                <span>模型 ID Model ID</span>
                <button
                  class="text-sky-500 hover:text-sky-600 transition-colors flex items-center gap-1 active:scale-95"
                  :disabled="isFetchingRerankerModels"
                  @click="fetchRemoteVectorModels('reranker')"
                >
                  <PixelIcon
                    :name="isFetchingRerankerModels ? 'refresh' : 'search'"
                    size="xs"
                    :animation="isFetchingRerankerModels ? 'spin' : ''"
                  />
                  {{ isFetchingRerankerModels ? '获取中...' : '查询模型' }}
                </button>
              </label>
              <PInput v-model="rerankerModelId" placeholder="例如: BAAI/bge-reranker-v2-m3" />
              <!-- 可选模型列表 🐈 -->
              <div
                v-if="availableRerankerModels.length > 0"
                class="flex flex-wrap gap-2 mt-2 max-h-[100px] overflow-y-auto custom-scrollbar p-1"
              >
                <button
                  v-for="m in availableRerankerModels"
                  :key="m"
                  class="px-3 py-1 text-[10px] rounded-full border border-sky-100 bg-sky-50 text-sky-600 hover:bg-sky-500 hover:text-white transition-all active:scale-90"
                  :class="{
                    '!bg-sky-500 !text-white !border-sky-500': rerankerModelId === m
                  }"
                  @click="rerankerModelId = m"
                >
                  {{ m }}
                </button>
              </div>
            </div>

            <div v-if="rerankerProvider === 'api'" class="space-y-2">
              <label class="text-xs font-black text-slate-400 uppercase tracking-widest ml-1"
                >API Base URL (可选)</label
              >
              <PInput v-model="rerankerApiBase" placeholder="留空则使用全局配置" />
            </div>

            <div v-if="rerankerProvider === 'api'" class="space-y-2">
              <label class="text-xs font-black text-slate-400 uppercase tracking-widest ml-1"
                >API Key (可选)</label
              >
              <PInput v-model="rerankerApiKey" type="password" placeholder="留空则使用全局配置" />
            </div>
          </div>
        </PCard>

        <!-- Help Alert -->
        <div class="bg-amber-50 border-2 border-amber-100 p-5 rounded-[1.5rem] flex gap-4">
          <div class="text-amber-500 mt-1">
            <PixelIcon name="alert" size="sm" />
          </div>
          <div class="text-xs text-amber-700 leading-relaxed">
            <p class="font-bold mb-1 italic">喵娘的温馨提示：</p>
            <ul class="list-disc ml-4 space-y-1">
              <li>切换向量模型后，原有的记忆将保存在旧索引中，互不干扰喵~</li>
              <li>如果您希望在新模型下也能搜索到旧记忆，请点击上方的“全量重索引”按钮喵！</li>
              <li>使用 API 模式时，请确保在“全局服务商”中正确配置了 Key 和 Base URL。</li>
            </ul>
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
import PInput from '@/components/ui/PInput.vue'
import PInputNumber from '@/components/ui/PInputNumber.vue'
import PSelect from '@/components/ui/PSelect.vue'
import PTooltip from '@/components/ui/PTooltip.vue'
import PixelIcon from '@/components/ui/PixelIcon.vue'
import { MODEL_CONFIG_KEY, DASHBOARD_KEY } from '@/composables/dashboard/injectionKeys'

const {
  models,
  currentModelTab,
  currentActiveModelId,
  secretaryModelId,
  reflectionModelId,
  auxModelId,
  openGlobalSettings,
  openModelEditor,
  deleteModel,
  setActiveModel,
  setSecretaryModel,
  setReflectionModel,
  setAuxModel,
  embeddingProvider,
  embeddingModelId,
  embeddingApiBase,
  embeddingApiKey,
  rerankerProvider,
  rerankerModelId,
  rerankerApiBase,
  rerankerApiKey,
  embeddingDimension,
  isReindexing,
  availableEmbeddingModels,
  isFetchingEmbeddingModels,
  availableRerankerModels,
  isFetchingRerankerModels,
  handleEmbeddingProviderChange,
  fetchRemoteVectorModels,
  saveVectorConfig,
  triggerReindex,
  isSaving
} = inject(MODEL_CONFIG_KEY)!
</script>
