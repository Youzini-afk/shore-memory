<script setup lang="ts">
import AppShell from '@/components/shell/AppShell.vue'
import { onMounted } from 'vue'
import { useAppStore } from '@/stores/app'

const app = useAppStore()

onMounted(() => {
  app.bootstrap()
})
</script>

<template>
  <AppShell>
    <router-view v-slot="{ Component }">
      <component :is="Component" />
    </router-view>
  </AppShell>
</template>
