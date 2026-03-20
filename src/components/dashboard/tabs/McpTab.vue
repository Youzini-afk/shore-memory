<template>
  <!-- 7. MCP 配置 (重构版) -->
  <div class="h-full flex flex-col overflow-hidden">
    <!-- Toolbar -->
    <div class="p-6 pb-0 flex-none">
      <PCard
        glass
        soft3d
        variant="sky"
        overflow-visible
        class="mb-4 !p-5 rounded-[2rem] relative group/mtoolbar z-30"
      >
        <!-- 背景装饰 ✨ -->
        <div
          class="absolute -right-20 -top-20 w-40 h-40 bg-sky-400/10 blur-[60px] rounded-full pointer-events-none group-hover/mtoolbar:bg-sky-400/20 transition-all duration-1000"
        ></div>

        <div class="flex flex-wrap items-center justify-between gap-5 relative z-10">
          <div class="flex items-center gap-4">
            <div
              class="p-3 bg-sky-50 rounded-2xl text-sky-500 border border-sky-100 shadow-sm shadow-sky-200/20 group-hover/mtoolbar:scale-110 group-hover/mtoolbar:rotate-6 transition-all duration-500"
            >
              <PixelIcon name="terminal" size="md" animation="bounce" />
            </div>
            <div>
              <h3 class="text-xl font-bold text-slate-800 flex items-center gap-2">
                MCP 扩展能力
                <span
                  class="text-xs font-normal text-slate-400 tracking-widest uppercase ml-1 opacity-50 group-hover/mtoolbar:opacity-100 transition-opacity"
                  ># MCP Config</span
                >
              </h3>
              <p class="text-xs text-slate-500 flex items-center gap-1.5 mt-0.5">
                让 Pero 拥有操作工具、访问网页和执行命令的能力
                <span class="group-hover/mtoolbar:animate-bounce">🛠️ 🐾</span>
              </p>
            </div>
          </div>

          <PButton
            variant="primary"
            class="!rounded-2xl shadow-lg shadow-sky-400/20 hover:scale-105 active:scale-95 transition-all px-6 relative z-10 hover-pixel-bounce"
            @click="openMcpEditor(null)"
          >
            <div class="flex items-center gap-1.5">
              <PixelIcon name="plus" size="xs" />
              添加 MCP 服务器 <span class="ml-1 opacity-80">Add Server</span>
            </div>
          </PButton>
        </div>
      </PCard>
    </div>

    <!-- MCP Servers Grid -->
    <div class="flex-1 overflow-y-auto px-6 py-4 custom-scrollbar">
      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6 pb-8">
        <div v-for="mcp in mcps" :key="mcp.id" class="group/mcp-container relative">
          <!-- 卡片主体 -->
          <PCard
            glass
            soft3d
            hoverable
            variant="sky"
            class="h-full !p-6 !rounded-[2rem] transition-all duration-500 overflow-hidden flex flex-col group/mcard"
            :class="[
              mcp.enabled ? 'border-sky-300/30 hover:shadow-sky-100/50' : 'opacity-60 grayscale'
            ]"
          >
            <!-- 背景装饰 ✨ -->
            <div
              class="absolute -right-10 -top-10 w-24 h-24 blur-[40px] rounded-full pointer-events-none transition-all duration-700 opacity-10 group-hover/mcard:opacity-30"
              :class="mcp.enabled ? 'bg-sky-400' : 'bg-sky-200'"
            ></div>

            <!-- Header -->
            <div class="flex items-center justify-between mb-5 relative z-10">
              <div class="flex-1 min-w-0 pr-4">
                <PTooltip :content="mcp.name">
                  <h3
                    class="text-base font-black text-slate-800 truncate group-hover/mcard:text-sky-600 transition-colors"
                  >
                    {{ mcp.name }}
                  </h3>
                </PTooltip>
                <div class="flex items-center gap-2 mt-1">
                  <span
                    class="px-2.5 py-1 rounded-lg text-[9px] uppercase font-black border tracking-widest transition-all"
                    :class="
                      mcp.type === 'stdio'
                        ? 'bg-slate-50 text-slate-400 border-slate-100 group-hover/mcard:border-slate-200'
                        : 'bg-sky-50 text-sky-500 border-sky-100 group-hover/mcard:border-sky-200 shadow-sm shadow-sky-100'
                    "
                    >{{ mcp.type }}</span
                  >
                </div>
              </div>
              <PSwitch
                v-model="mcp.enabled"
                class="scale-90"
                @change="() => toggleMcpEnabled(mcp)"
              />
            </div>

            <!-- Config Details -->
            <div class="space-y-3 mb-6 relative z-10">
              <div class="flex flex-col gap-2">
                <span class="text-[10px] font-black text-slate-400 uppercase tracking-widest ml-1">
                  {{ mcp.type === 'stdio' ? '启动命令 Command' : '服务地址 URL' }}
                </span>
                <PTooltip :content="mcp.type === 'stdio' ? mcp.command : mcp.url">
                  <div
                    class="text-[11px] text-slate-600 font-mono break-all bg-sky-50/50 p-3.5 rounded-2xl border border-sky-100/50 group-hover/mcard:border-sky-200 transition-all leading-relaxed soft-3d-shadow"
                  >
                    {{ mcp.type === 'stdio' ? mcp.command : mcp.url }}
                  </div>
                </PTooltip>
              </div>
            </div>

            <!-- Actions -->
            <div
              class="mt-auto pt-5 border-t border-sky-100/30 flex items-center justify-end gap-2 relative z-10"
            >
              <PTooltip content="配置服务器" placement="top">
                <button
                  class="p-2 rounded-xl text-slate-400 hover:text-sky-500 hover:bg-sky-50 transition-all active:scale-90 group/btn-edit"
                  @click="openMcpEditor(mcp)"
                >
                  <PixelIcon
                    name="pencil"
                    size="xs"
                    class="group-hover/btn-edit:rotate-12 transition-transform"
                  />
                </button>
              </PTooltip>
              <PTooltip content="删除服务器" placement="top">
                <button
                  class="p-2 rounded-xl text-slate-400 hover:text-rose-500 hover:bg-rose-50 transition-all active:scale-90 group/btn-del"
                  @click="deleteMcp(mcp.id)"
                >
                  <PixelIcon
                    name="trash"
                    size="xs"
                    class="group-hover/btn-del:shake transition-transform"
                  />
                </button>
              </PTooltip>
            </div>
          </PCard>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { inject } from 'vue'
import PCard from '@/components/ui/PCard.vue'
import PButton from '@/components/ui/PButton.vue'
import PSwitch from '@/components/ui/PSwitch.vue'
import PTooltip from '@/components/ui/PTooltip.vue'
import PixelIcon from '@/components/ui/PixelIcon.vue'
import { MODEL_CONFIG_KEY } from '@/composables/dashboard/injectionKeys'

const { mcps, openMcpEditor, deleteMcp, toggleMcpEnabled, isSaving } = inject(MODEL_CONFIG_KEY)!
</script>
