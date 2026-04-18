<script setup lang="ts">
import { computed, ref } from 'vue'
import { storeToRefs } from 'pinia'
import PCard from '@/components/ui/PCard.vue'
import PInput from '@/components/ui/PInput.vue'
import PButton from '@/components/ui/PButton.vue'
import PBadge from '@/components/ui/PBadge.vue'
import { useAgentStore } from '@/stores/agent'

const agentStore = useAgentStore()
const { draft, dirty, dirtyFields, saving, saveError, lastSavedAt } =
  storeToRefs(agentStore)

interface FieldMeta {
  key: 'mood' | 'vibe' | 'mind'
  label: string
  placeholder: string
  presets: string[]
  limit: number
}

const FIELDS: FieldMeta[] = [
  {
    key: 'mood',
    label: 'Mood · 心情',
    placeholder: '如：平静、好奇',
    presets: ['平静', '开心', '好奇', '紧张', '疲惫', '失落', '专注', '期待'],
    limit: 32
  },
  {
    key: 'vibe',
    label: 'Vibe · 氛围',
    placeholder: '如：正常、活泼',
    presets: ['正常', '活泼', '专注', '放松', '低落', '严肃', '温柔', '紧凑'],
    limit: 32
  },
  {
    key: 'mind',
    label: 'Mind · 心绪',
    placeholder: '如：正在整理记忆',
    presets: [
      '正在整理记忆',
      '在听你说',
      '需要休息',
      '专注思考',
      '回味刚刚的对话',
      '准备回应'
    ],
    limit: 64
  }
]

const savedLabel = computed(() => {
  if (!lastSavedAt.value) return null
  const diff = Date.now() - lastSavedAt.value
  if (diff < 4_000) return '已保存'
  if (diff < 60_000) return `${Math.floor(diff / 1000)} 秒前已保存`
  return null
})

const overLimit = computed(() => {
  for (const field of FIELDS) {
    if ((draft.value[field.key]?.length ?? 0) > field.limit) return true
  }
  return false
})

const canSave = computed(() => dirty.value && !saving.value && !overLimit.value)

function applyPreset(key: FieldMeta['key'], value: string) {
  draft.value[key] = value
}

const toastShown = ref(false)

async function handleSave() {
  try {
    await agentStore.save()
    toastShown.value = true
    window.setTimeout(() => {
      toastShown.value = false
    }, 1600)
  } catch {
    // error already stored in store.saveError
  }
}

function handleReset() {
  agentStore.resetDraft()
}

function isDirtyField(key: FieldMeta['key']) {
  return dirtyFields.value.includes(key)
}

function remainingFor(field: FieldMeta) {
  const used = draft.value[field.key]?.length ?? 0
  return field.limit - used
}
</script>

<template>
  <PCard edge class="flex flex-col gap-5">
    <div class="flex items-center justify-between gap-3">
      <div>
        <div class="font-display text-[14px] text-ink-1">手动编辑</div>
        <div class="mt-0.5 text-[11.5px] text-ink-4">
          只修改"脏字段"才会发 PATCH；评分 / 反思任务也会自动回写
        </div>
      </div>
      <div class="flex items-center gap-2 text-[11px] text-ink-4">
        <PBadge v-if="dirty" tone="amber" size="sm">未保存</PBadge>
        <span v-else-if="savedLabel" class="text-state-active tabular">{{ savedLabel }}</span>
      </div>
    </div>

    <div class="flex flex-col gap-5">
      <div v-for="field in FIELDS" :key="field.key" class="flex flex-col gap-2">
        <div class="flex items-center justify-between">
          <label class="text-[11.5px] tracking-wide text-ink-3 font-display">
            {{ field.label }}
          </label>
          <span
            class="text-[10.5px] tabular"
            :class="remainingFor(field) < 0 ? 'text-state-invalidated' : 'text-ink-5'"
          >
            {{ remainingFor(field) }} 字余量
          </span>
        </div>
        <PInput
          v-model="draft[field.key]"
          :placeholder="field.placeholder"
          size="md"
        />
        <div class="flex flex-wrap gap-1.5">
          <button
            v-for="preset in field.presets"
            :key="preset"
            type="button"
            class="px-2.5 h-6 rounded-pill text-[11px] border transition-all duration-240 ease-shore select-none"
            :class="[
              draft[field.key] === preset
                ? 'text-ink-1 border-accent/50 bg-accent/12'
                : 'text-ink-3 border-shore-line hover:text-ink-1 hover:border-shore-border hover:bg-shore-hover'
            ]"
            @click="applyPreset(field.key, preset)"
          >
            {{ preset }}
          </button>
          <span
            v-if="isDirtyField(field.key)"
            class="inline-flex items-center px-2 h-6 rounded-pill text-[10px] text-sig-amber border border-sig-amber/35 bg-sig-amber/10 tracking-wide uppercase"
          >
            改动待保存
          </span>
        </div>
      </div>
    </div>

    <div v-if="saveError" class="text-[11.5px] text-state-invalidated">
      {{ saveError }}
    </div>

    <div class="flex items-center justify-end gap-2 pt-1 border-t border-shore-line/60">
      <PButton
        size="sm"
        variant="ghost"
        :disabled="!dirty || saving"
        @click="handleReset"
      >
        恢复草稿
      </PButton>
      <PButton
        size="sm"
        variant="primary"
        :disabled="!canSave"
        :loading="saving"
        @click="handleSave"
      >
        保存状态
      </PButton>
    </div>

    <transition name="fade">
      <div
        v-if="toastShown"
        class="pointer-events-none absolute bottom-3 right-3 px-3 py-1.5 rounded-btn bg-state-active/20 border border-state-active/40 text-[11px] text-state-active"
      >
        ✓ 已同步至服务端
      </div>
    </transition>
  </PCard>
</template>

<style scoped>
.fade-enter-active,
.fade-leave-active {
  transition: opacity 200ms ease, transform 200ms ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
  transform: translateY(4px);
}
</style>
