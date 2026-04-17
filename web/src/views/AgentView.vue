<script setup lang="ts">
import PHero from '@/components/ui/PHero.vue'
import PCard from '@/components/ui/PCard.vue'
import PEmpty from '@/components/ui/PEmpty.vue'
</script>

<template>
  <div class="min-h-full">
    <PHero title="Agent 状态" subtitle="心情 · 氛围 · 心绪三元组与最近记忆趋势" />
    <div class="px-8 pb-10">
      <PCard edge>
        <PEmpty
          title="Agent 状态即将接入"
          hint="下一个里程碑会接入 /v1/agents/{agent_id}/state，提供编辑与可视化。"
          milestone="即将上线 · M5"
        />
      </PCard>
    </div>
  </div>
</template>
