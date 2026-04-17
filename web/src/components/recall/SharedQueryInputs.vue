<script setup lang="ts">
/**
 * 在 A/B Compare 模式下显示共享字段：query / user_uid / channel_uid /
 * session_uid / limit。Variant-specific 字段（recipe / scope / include_*）
 * 留给 VariantInputs。
 */
import { computed } from 'vue'
import { storeToRefs } from 'pinia'
import { Play, Search, ArrowLeftRight } from 'lucide-vue-next'
import PCard from '@/components/ui/PCard.vue'
import PInput from '@/components/ui/PInput.vue'
import PTextarea from '@/components/ui/PTextarea.vue'
import PSlider from '@/components/ui/PSlider.vue'
import PButton from '@/components/ui/PButton.vue'
import PKbd from '@/components/ui/PKbd.vue'
import { useRecallStore } from '@/stores/recall'

const store = useRecallStore()
const { form, compareLoading } = storeToRefs(store)

const hasQuery = computed(() => form.value.query.trim().length > 0)

async function run() {
  await store.runCompare()
}
</script>

<template>
  <PCard edge>
    <div class="flex items-center justify-between mb-4">
      <div class="text-[11px] uppercase tracking-[0.2em] font-display text-ink-4 flex items-center gap-2">
        <span class="h-1 w-1 rounded-full bg-accent" />
        共享查询
      </div>
      <button
        type="button"
        class="h-7 px-2 rounded-btn text-[11px] text-ink-3 hover:text-ink-1 hover:bg-shore-hover transition-colors flex items-center gap-1 disabled:opacity-45 disabled:cursor-not-allowed disabled:hover:bg-transparent"
        title="交换 A / B"
        :disabled="compareLoading"
        @click="store.swapVariants()"
      >
        <ArrowLeftRight class="h-3.5 w-3.5" :stroke-width="1.75" />
        交换
      </button>
    </div>

    <div class="mb-1.5 flex items-center justify-between text-[10.5px] font-display uppercase tracking-wider text-ink-4">
      <span>查询文本</span>
      <span class="flex items-center gap-1.5 text-[10px] normal-case tracking-normal">
        运行 <PKbd combo="mod+enter" />
      </span>
    </div>
    <PTextarea
      v-model="form.query"
      :rows="3"
      placeholder="A/B 对比：同一查询跑两套配方 / 作用域 / 过滤"
      @submit="run"
    />

    <div class="mt-4 grid grid-cols-2 gap-3">
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

    <div class="mt-4">
      <div class="mb-1 flex items-center justify-between text-[10.5px] font-display uppercase tracking-wider text-ink-4">
        <span>每组返回条数上限</span>
        <span class="normal-case tracking-normal text-ink-5">1 — 32</span>
      </div>
      <PSlider v-model="form.limit" :min="1" :max="32" :step="1" />
    </div>

    <div class="mt-5 flex items-center gap-2">
      <PButton
        variant="primary"
        size="md"
        :loading="compareLoading"
        :disabled="compareLoading || !hasQuery"
        class="flex-1"
        @click="run"
      >
        <Play class="h-4 w-4" :stroke-width="1.75" />
        <span>运行对比</span>
        <span class="ml-2 text-[11px] opacity-80">
          <PKbd combo="mod+enter" />
        </span>
      </PButton>
      <span
        class="hidden md:inline-flex items-center gap-1.5 text-[10px] text-ink-5 px-2 font-display"
      >
        <Search class="h-3 w-3" :stroke-width="1.75" />
        同一查询 · 仅变体参数不同
      </span>
    </div>
  </PCard>
</template>
