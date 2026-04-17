<script setup lang="ts">
import PHero from '@/components/ui/PHero.vue'
import PCard from '@/components/ui/PCard.vue'
import PButton from '@/components/ui/PButton.vue'
import PEmpty from '@/components/ui/PEmpty.vue'
</script>

<template>
  <div class="min-h-full">
    <PHero
      title="Memory Graph"
      subtitle="以 Memory / Entity / Session 为中心，展开大规模关联网络"
    >
      <template #actions>
        <PButton variant="secondary" size="sm">布局 · Force</PButton>
        <PButton variant="secondary" size="sm">Depth · 2</PButton>
        <PButton variant="primary" size="sm">Reset View</PButton>
      </template>
    </PHero>

    <div class="px-8 pb-10">
      <PCard edge class="!p-0 overflow-hidden">
        <div
          class="h-[520px] relative flex items-center justify-center"
          style="background: radial-gradient(circle at 30% 20%, rgba(124,92,255,0.08), transparent 40%), radial-gradient(circle at 80% 70%, rgba(56,189,248,0.05), transparent 45%), #0A0A10"
        >
          <PEmpty
            title="神经网络画布待落地"
            hint="下一个里程碑 M4 会基于 Sigma.js + Graphology 实装：自定义节点薄晕 / 突触电流 / 脉冲动画 / LOD / Louvain 聚类。"
            milestone="Next · M4"
          />
        </div>
      </PCard>
    </div>
  </div>
</template>
