<template>
  <div
    class="w-12 h-full bg-slate-900 flex flex-col items-center py-2 select-none z-20 pixel-border-r-dark"
  >
    <!-- 资源管理器 -->
    <div
      class="w-10 h-10 flex items-center justify-center cursor-pointer transition-all relative mb-2 group"
      :class="
        activeTab === 'explorer'
          ? 'text-moe-pink bg-white/5 pixel-border-sm-moe'
          : 'text-slate-500 hover:text-moe-sky hover:bg-white/5'
      "
      title="Explorer (Ctrl+Shift+E)"
      @click="$emit('update:activeTab', 'explorer')"
    >
      <div
        v-if="activeTab === 'explorer'"
        class="absolute left-0 top-1 bottom-1 w-1 bg-moe-pink rounded-r"
      ></div>
      <PixelIcon name="folder" size="sm" />
    </div>

    <!-- 搜索 -->
    <div
      class="w-10 h-10 flex items-center justify-center cursor-pointer transition-all relative mb-2 group"
      :class="
        activeTab === 'search'
          ? 'text-moe-pink bg-white/5 pixel-border-sm-moe'
          : 'text-slate-500 hover:text-moe-sky hover:bg-white/5'
      "
      title="Search (Ctrl+Shift+F)"
      @click="$emit('update:activeTab', 'search')"
    >
      <div
        v-if="activeTab === 'search'"
        class="absolute left-0 top-1 bottom-1 w-1 bg-moe-pink rounded-r"
      ></div>
      <PixelIcon name="search" size="sm" />
    </div>

    <div class="flex-1"></div>

    <!-- 设置 -->
    <div
      class="w-10 h-10 flex items-center justify-center cursor-pointer transition-colors text-slate-500 hover:text-moe-sky mb-1 press-effect"
      title="Settings"
    >
      <PixelIcon name="settings" size="sm" />
    </div>
  </div>
</template>

<script setup>
// import { Files as FilesIcon, Search as SearchIcon, Settings as SettingsIcon } from 'lucide-vue-next'

defineProps({
  activeTab: {
    type: String,
    default: 'explorer'
  }
})

defineEmits(['update:activeTab'])
</script>
