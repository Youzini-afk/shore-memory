<script setup lang="ts">
import PHero from '@/components/ui/PHero.vue'
import PCard from '@/components/ui/PCard.vue'
import PButton from '@/components/ui/PButton.vue'
import PEmpty from '@/components/ui/PEmpty.vue'
</script>

<template>
  <div class="min-h-full">
    <PHero
      title="Memories"
      subtitle="浏览 · 筛选 · 编辑 · 导出 Agent 的长期记忆"
    >
      <template #actions>
        <PButton variant="secondary" size="sm">导出 JSON</PButton>
        <PButton variant="primary" size="sm">+ 新建记忆</PButton>
      </template>
    </PHero>

    <div class="px-8 pb-10">
      <PCard edge>
        <PEmpty
          title="记忆列表待接入"
          hint="下一个里程碑 M3 会实装 Linear 式信息条 + 常驻详情栏（Overview / Metadata / History）。"
          milestone="Next · M3"
        />
      </PCard>
    </div>
  </div>
</template>
