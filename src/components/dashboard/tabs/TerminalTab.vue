<template>
  <!-- 11. 系统终端 -->
  <div class="h-full flex flex-col p-6 overflow-hidden relative">
    <!-- 背景装饰 ✨ -->
    <div
      class="absolute -right-20 -top-20 w-80 h-80 bg-blue-400/5 blur-[100px] rounded-full pointer-events-none"
    ></div>
    <div
      class="absolute -left-20 -bottom-20 w-80 h-80 bg-indigo-400/5 blur-[100px] rounded-full pointer-events-none"
    ></div>

    <PCard
      glass
      soft3d
      full-height
      class="flex-1 flex flex-col overflow-hidden !p-0 border-blue-100/50"
    >
      <TerminalPanel class="h-full w-full" />
    </PCard>
  </div>
</template>

<script setup lang="ts">
import PCard from '@/components/ui/PCard.vue'
import TerminalPanel from '@/components/terminal/TerminalPanel.vue'
</script>
