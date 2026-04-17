<script setup lang="ts">
import PHero from '@/components/ui/PHero.vue'
import PCard from '@/components/ui/PCard.vue'
import PButton from '@/components/ui/PButton.vue'
import PEmpty from '@/components/ui/PEmpty.vue'
</script>

<template>
  <div class="min-h-full">
    <PHero
      title="Recall Playground"
      subtitle="对 Agent 的长期记忆做一次多信号召回 · 观察分数拆解"
    >
      <template #actions>
        <PButton variant="secondary" size="sm">保存为模板</PButton>
        <PButton variant="primary" size="sm">召回 ⌘↵</PButton>
      </template>
    </PHero>

    <div class="px-8 pb-10 grid grid-cols-12 gap-5">
      <div class="col-span-5">
        <PCard edge>
          <div class="text-[12px] uppercase font-display tracking-wider text-ink-4">
            查询构造器
          </div>
          <PEmpty
            class="!py-14"
            title="查询面板待接入"
            hint="下一个里程碑 M2 会实装：Agent · Query · Recipe · Filters · 召回。"
            milestone="Next · M2"
          />
        </PCard>
      </div>
      <div class="col-span-7">
        <PCard edge>
          <div class="text-[12px] uppercase font-display tracking-wider text-ink-4">
            命中结果
          </div>
          <PEmpty
            class="!py-14"
            title="结果流待接入"
            hint="将展示延迟 · 命中数 · 缓存状态 · 分数拆解堆叠条。"
            milestone="Next · M2"
          />
        </PCard>
      </div>
    </div>
  </div>
</template>
