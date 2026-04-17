<script setup lang="ts">
import AppShell from '@/components/shell/AppShell.vue'
import AuthGate from '@/components/auth/AuthGate.vue'
import { onMounted, onUnmounted } from 'vue'
import { useAppStore } from '@/stores/app'

const app = useAppStore()

onMounted(() => {
  void app.bootstrap()
})

onUnmounted(() => {
  app.teardown()
})
</script>

<template>
  <AuthGate v-if="!app.canRenderConsole" />
  <AppShell v-else>
    <router-view v-slot="{ Component }">
      <component :is="Component" />
    </router-view>
  </AppShell>
</template>
