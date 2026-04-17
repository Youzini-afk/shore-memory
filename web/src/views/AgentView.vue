<script setup lang="ts">
import PHero from '@/components/ui/PHero.vue'
import PCard from '@/components/ui/PCard.vue'
import PEmpty from '@/components/ui/PEmpty.vue'
</script>

<template>
  <div class="min-h-full">
    <PHero title="Agent" subtitle="mood · vibe · mind 三元组与最近记忆趋势" />
    <div class="px-8 pb-10">
      <PCard edge>
        <PEmpty
          title="Agent 状态待接入"
          hint="下一个里程碑 M5 会接 /v1/agents/{agent_id}/state 做编辑与可视化。"
          milestone="Next · M5"
        />
      </PCard>
    </div>
  </div>
</template>
