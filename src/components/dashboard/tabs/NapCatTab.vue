<template>
  <!-- 10. NapCat 终端 -->
  <div class="h-full flex flex-col p-6 overflow-hidden relative">
    <!-- 背景装饰 ✨ -->
    <div
      class="absolute -right-20 -top-20 w-80 h-80 bg-emerald-400/5 blur-[100px] rounded-full pointer-events-none"
    ></div>
    <div
      class="absolute -left-20 -bottom-20 w-80 h-80 bg-sky-400/5 blur-[100px] rounded-full pointer-events-none"
    ></div>

    <PCard
      glass
      soft3d
      full-height
      class="flex-1 flex flex-col overflow-hidden !p-0 border-emerald-100/50"
    >
      <NapCatTerminal class="h-full w-full" />
    </PCard>
  </div>
</template>

<script setup lang="ts">
import PCard from '@/components/ui/PCard.vue'
import NapCatTerminal from '@/components/terminal/NapCatTerminal.vue'
</script>
