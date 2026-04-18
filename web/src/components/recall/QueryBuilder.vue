<script setup lang="ts">
import { ref, computed } from 'vue'
import { storeToRefs } from 'pinia'
import { Search, History, Bookmark, X, Trash2, FileText } from 'lucide-vue-next'
import PCard from '@/components/ui/PCard.vue'
import PButton from '@/components/ui/PButton.vue'
import PInput from '@/components/ui/PInput.vue'
import PTextarea from '@/components/ui/PTextarea.vue'
import PSegment from '@/components/ui/PSegment.vue'
import PSlider from '@/components/ui/PSlider.vue'
import PSwitch from '@/components/ui/PSwitch.vue'
import PKbd from '@/components/ui/PKbd.vue'
import { useRecallStore } from '@/stores/recall'
import type { MemoryScopeHint, RecallRecipeId } from '@/api/types'

const store = useRecallStore()
const { form, loading, error, history, templates } = storeToRefs(store)

const queryEl = ref<InstanceType<typeof PTextarea> | null>(null)
const templateName = ref('')
const showHistory = ref(false)
const showTemplates = ref(false)

defineExpose({
  focusQuery: () => {
    // 暴露给父页用于 ⌘K 聚焦
    const el = (queryEl.value as unknown as HTMLElement | null)?.querySelector?.('textarea') as
      | HTMLTextAreaElement
      | null
    el?.focus()
    el?.select?.()
  }
})

const recipeOptions: { label: string; value: RecallRecipeId; hint: string }[] = [
  { value: 'fast', label: '极速', hint: '仅向量，最低延迟' },
  { value: 'hybrid', label: '混合', hint: '向量 + BM25（默认）' },
  { value: 'entity_heavy', label: '实体优先', hint: '加强实体信号' },
  { value: 'contiguous', label: '连贯性', hint: '启用连贯性加分' }
]

const scopeOptions: { label: string; value: MemoryScopeHint }[] = [
  { value: 'auto', label: '自动' },
  { value: 'private', label: '私有' },
  { value: 'group', label: '群组' },
  { value: 'shared', label: '共享' },
  { value: 'system', label: '系统' }
]

async function submit() {
  await store.submit()
}

function saveTemplate() {
  const name = templateName.value.trim() || form.value.query.slice(0, 20) || '召回模板'
  store.saveTemplate(name)
  templateName.value = ''
  showTemplates.value = true
}

function formatTime(ts: number): string {
  const d = new Date(ts)
  const hh = String(d.getHours()).padStart(2, '0')
  const mm = String(d.getMinutes()).padStart(2, '0')
  return `${hh}:${mm}`
}

const hasQuery = computed(() => form.value.query.trim().length > 0)
</script>

<template>
  <PCard edge>
    <!-- Header -->
    <div class="flex items-center justify-between mb-4">
      <div class="text-[11px] uppercase tracking-[0.2em] font-display text-ink-4 flex items-center gap-2">
        <span class="h-1 w-1 rounded-full bg-accent" />
        查询构造器
      </div>
      <div class="flex items-center gap-1">
        <button
          type="button"
          class="h-7 px-2 rounded-btn text-[11px] text-ink-3 hover:text-ink-1 hover:bg-shore-hover transition-colors flex items-center gap-1"
          :class="showHistory ? 'bg-shore-hover text-ink-1' : ''"
          title="最近查询"
          @click="showHistory = !showHistory; showTemplates = false"
        >
          <History class="h-3.5 w-3.5" :stroke-width="1.75" />
          历史
        </button>
        <button
          type="button"
          class="h-7 px-2 rounded-btn text-[11px] text-ink-3 hover:text-ink-1 hover:bg-shore-hover transition-colors flex items-center gap-1"
          :class="showTemplates ? 'bg-shore-hover text-ink-1' : ''"
          title="模板"
          @click="showTemplates = !showTemplates; showHistory = false"
        >
          <Bookmark class="h-3.5 w-3.5" :stroke-width="1.75" />
          模板
        </button>
      </div>
    </div>

    <!-- History panel -->
    <div
      v-if="showHistory"
      class="mb-4 rounded-panel bg-shore-elev border border-shore-line/80 max-h-[220px] overflow-y-auto divide-y divide-shore-line/60"
    >
      <div
        v-if="!history.length"
        class="px-3 py-5 text-center text-[12px] text-ink-4"
      >
        暂无历史
      </div>
      <button
        v-for="entry in history"
        :key="entry.id"
        type="button"
        class="w-full flex items-start gap-3 px-3 py-2 text-left hover:bg-shore-hover transition-colors"
        @click="store.loadFromHistory(entry); showHistory = false"
      >
        <span class="mt-0.5 text-[10.5px] font-mono tabular text-ink-5 w-10 shrink-0">{{ formatTime(entry.at) }}</span>
        <span class="flex-1 min-w-0">
          <span class="block truncate text-[12.5px] text-ink-1">{{ entry.form.query }}</span>
          <span class="mt-0.5 block text-[10.5px] text-ink-4 font-display">
            {{ entry.form.recipe }} · {{ entry.hits }} hit · {{ entry.latencyMs }} ms
            <span v-if="entry.degraded" class="text-sig-amber">· degraded</span>
          </span>
        </span>
      </button>
      <div v-if="history.length" class="p-2 flex justify-end">
        <button
          type="button"
          class="text-[10.5px] text-ink-4 hover:text-state-invalidated flex items-center gap-1"
          @click="store.clearHistory()"
        >
          <Trash2 class="h-3 w-3" :stroke-width="1.75" />清空历史
        </button>
      </div>
    </div>

    <!-- Templates panel -->
    <div
      v-if="showTemplates"
      class="mb-4 rounded-panel bg-shore-elev border border-shore-line/80 overflow-hidden"
    >
      <div class="px-3 py-2 flex items-center gap-2 border-b border-shore-line/60">
        <PInput
          v-model="templateName"
          size="sm"
          placeholder="模板名称，例如: shore · 散步偏好"
          class="flex-1"
        >
          <template #prefix>
            <FileText class="h-3.5 w-3.5" :stroke-width="1.75" />
          </template>
        </PInput>
        <PButton size="sm" variant="primary" :disabled="!hasQuery" @click="saveTemplate"
          >保存为模板</PButton
        >
      </div>
      <div class="max-h-[180px] overflow-y-auto divide-y divide-shore-line/60">
        <div v-if="!templates.length" class="px-3 py-5 text-center text-[12px] text-ink-4">
          还没有模板
        </div>
        <div
          v-for="tpl in templates"
          :key="tpl.id"
          class="flex items-center gap-3 px-3 py-2 hover:bg-shore-hover transition-colors"
        >
          <button
            type="button"
            class="flex-1 text-left min-w-0"
            @click="store.loadFromTemplate(tpl); showTemplates = false"
          >
            <span class="block truncate text-[12.5px] text-ink-1">{{ tpl.name }}</span>
            <span class="block truncate text-[10.5px] text-ink-4 font-display">
              {{ tpl.form.recipe }} · limit {{ tpl.form.limit }}
              <span v-if="tpl.form.query"> · {{ tpl.form.query.slice(0, 28) }}</span>
            </span>
          </button>
          <button
            type="button"
            class="shrink-0 h-6 w-6 flex items-center justify-center rounded-btn text-ink-5 hover:text-state-invalidated hover:bg-state-invalidated/10 transition-colors"
            title="删除模板"
            @click="store.deleteTemplate(tpl.id)"
          >
            <X class="h-3.5 w-3.5" :stroke-width="1.75" />
          </button>
        </div>
      </div>
    </div>

    <!-- Query textarea -->
    <div>
      <div class="mb-1.5 flex items-center justify-between text-[10.5px] font-display uppercase tracking-wider text-ink-4">
        <span>查询文本</span>
        <span class="flex items-center gap-1.5 text-[10px] normal-case tracking-normal">
          提交 <PKbd combo="mod+enter" />
        </span>
      </div>
      <PTextarea
        ref="queryEl"
        v-model="form.query"
        :rows="3"
        placeholder="请输入查询文本，例如：用户最近一次对咖啡因的偏好是什么？"
        @submit="submit"
      />
    </div>

    <div class="mt-4">
      <div class="mb-1.5 text-[10.5px] font-display uppercase tracking-wider text-ink-4">
        子查询（可选）
      </div>
      <PTextarea
        v-model="form.subqueries_text"
        :rows="3"
        placeholder="显式多意图拆分，每行或用逗号分隔。留空则按 query / auto plan 决定。"
      />
      <div class="mt-1 text-[10.5px] text-ink-5">
        最多 4 条；填写后优先使用你提供的子查询。
      </div>
    </div>

    <label class="mt-4 flex items-center gap-3 cursor-pointer">
      <PSwitch v-model="form.auto_plan" />
      <div class="flex-1 min-w-0">
        <div class="text-[12.5px] text-ink-1 font-display">自动规划子查询</div>
        <div class="text-[10.5px] text-ink-4">
          使用 `query_planner` 角色自动拆分 query；显式子查询不为空时将忽略自动规划结果。
        </div>
      </div>
    </label>

    <!-- Recipe -->
    <div class="mt-4">
      <div class="mb-1.5 text-[10.5px] font-display uppercase tracking-wider text-ink-4">
        召回配方
      </div>
      <PSegment v-model="form.recipe" :options="recipeOptions" block />
      <div class="mt-1 text-[10.5px] text-ink-5">
        <template v-if="form.recipe === 'fast'">仅向量，最低延迟，跳过 BM25 / 实体 / 连贯性</template>
        <template v-else-if="form.recipe === 'hybrid'">向量 + BM25 添加式融合（默认）</template>
        <template v-else-if="form.recipe === 'entity_heavy'">加大实体信号权重，适合事实与关系类查询</template>
        <template v-else-if="form.recipe === 'contiguous'">启用连贯性加分，同会话的相邻记忆会被拉入</template>
      </div>
    </div>

    <!-- Filters -->
    <div class="mt-4 grid grid-cols-2 gap-3">
      <div class="col-span-2">
        <div class="mb-1.5 text-[10.5px] font-display uppercase tracking-wider text-ink-4">
          作用域
        </div>
        <PSegment v-model="form.scope_hint" :options="scopeOptions" size="sm" block />
      </div>
      <div>
        <div class="mb-1.5 text-[10.5px] font-display uppercase tracking-wider text-ink-4">
          用户 UID
        </div>
        <PInput v-model="form.user_uid" size="sm" placeholder="可选" mono />
      </div>
      <div>
        <div class="mb-1.5 text-[10.5px] font-display uppercase tracking-wider text-ink-4">
          频道 UID
        </div>
        <PInput v-model="form.channel_uid" size="sm" placeholder="可选" mono />
      </div>
      <div class="col-span-2">
        <div class="mb-1.5 text-[10.5px] font-display uppercase tracking-wider text-ink-4">
          会话 UID
        </div>
        <PInput v-model="form.session_uid" size="sm" placeholder="可选" mono />
      </div>
    </div>

    <!-- Sliders -->
    <div class="mt-5 space-y-3">
      <div>
        <div class="mb-1 flex items-center justify-between text-[10.5px] font-display uppercase tracking-wider text-ink-4">
          <span>返回条数上限</span>
          <span class="normal-case tracking-normal text-ink-5">1 — 32</span>
        </div>
        <PSlider v-model="form.limit" :min="1" :max="32" :step="1" />
      </div>
    </div>

    <!-- Switches -->
    <div class="mt-5 space-y-3">
      <label
        class="flex items-center gap-3 cursor-pointer"
      >
        <PSwitch v-model="form.include_invalid" />
        <div class="flex-1 min-w-0">
          <div class="text-[12.5px] text-ink-1 font-display">包含失效记忆</div>
          <div class="text-[10.5px] text-ink-4">时光回溯：也考虑已失效或被取代的记忆</div>
        </div>
      </label>

      <label class="flex items-center gap-3 cursor-pointer">
        <PSwitch v-model="form.include_state" />
        <div class="flex-1 min-w-0">
          <div class="text-[12.5px] text-ink-1 font-display">返回 Agent 状态</div>
          <div class="text-[10.5px] text-ink-4">返回当前 Agent 的心情 / 氛围 / 心绪快照</div>
        </div>
      </label>

      <label class="flex items-center gap-3 cursor-pointer">
        <PSwitch v-model="form.debug" />
        <div class="flex-1 min-w-0">
          <div class="text-[12.5px] text-ink-1 font-display">调试模式</div>
          <div class="text-[10.5px] text-ink-4">附带分数拆解与生命周期元数据</div>
        </div>
      </label>
    </div>

    <!-- Error -->
    <div
      v-if="error"
      class="mt-4 rounded-btn bg-state-invalidated/10 border border-state-invalidated/30 px-3 py-2 text-[12px] text-state-invalidated"
    >
      {{ error }}
    </div>

    <!-- Actions -->
    <div class="mt-5 flex items-center gap-2">
      <PButton
        variant="primary"
        size="md"
        :loading="loading"
        :disabled="loading || !hasQuery"
        class="flex-1"
        @click="submit"
      >
        <Search class="h-4 w-4" :stroke-width="1.75" />
        <span>召回</span>
        <span class="ml-2 text-[11px] opacity-80">
          <PKbd combo="mod+enter" />
        </span>
      </PButton>
      <PButton variant="secondary" size="md" :disabled="!hasQuery" @click="saveTemplate">
        保存为模板
      </PButton>
    </div>
  </PCard>
</template>
