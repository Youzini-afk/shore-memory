<script setup lang="ts">
import SideNav from './SideNav.vue'
import TopBar from './TopBar.vue'
</script>

<template>
  <div class="shore-shell h-full w-full bg-shore-bg text-ink-1 flex">
    <SideNav class="shrink-0" />
    <div class="flex-1 min-w-0 flex flex-col">
      <TopBar />
      <main class="flex-1 min-h-0 overflow-auto bg-shore-surface">
        <slot />
      </main>
    </div>
  </div>
</template>

<style scoped>
.shore-shell {
  min-height: 100vh;
}
</style>
