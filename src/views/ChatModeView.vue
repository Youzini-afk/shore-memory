<template>
  <!-- 全局彩色背景层 -->
  <div
    class="absolute inset-0 bg-gradient-to-br from-sky-200/20 via-sky-100/10 to-transparent pointer-events-none z-0"
  ></div>

  <div class="h-full w-full flex overflow-hidden backdrop-blur-xl relative z-10">
    <!-- 侧边栏 -->
    <div class="w-64 flex flex-col border-r border-white/40 bg-white/40 backdrop-blur-md pt-8">
      <!-- 搜索 -->
      <div class="px-4 pb-4 pt-2">
        <div class="relative">
          <input
            type="text"
            placeholder="搜索助手..."
            class="w-full bg-black/5 text-slate-700 text-xs rounded-lg pl-8 pr-3 py-2 focus:outline-none focus:bg-white/50 transition-colors placeholder-slate-500/50"
          />
          <Search class="w-3.5 h-3.5 absolute left-2.5 top-2.5 text-slate-500/50" />
        </div>
      </div>

      <!-- 助手列表 -->
      <div class="flex-1 overflow-y-auto custom-scrollbar px-2 space-y-1">
        <div class="flex items-center justify-between px-2 py-1.5">
          <div class="text-[10px] font-bold text-slate-500/70 uppercase tracking-widest">
            Agents
          </div>
          <button
            class="text-slate-400 hover:text-sky-500 transition-colors"
            title="刷新"
            @click="loadAgents"
          >
            <div
              class="w-3 h-3 border-2 border-current border-t-transparent rounded-full"
              :class="{ 'animate-spin': isLoading }"
            ></div>
          </button>
        </div>

        <div v-if="errorMsg" class="px-2 py-2 text-xs text-red-500 bg-red-50 rounded">
          {{ errorMsg }}
        </div>

        <div
          v-if="agents.length === 0 && !isLoading && !errorMsg"
          class="px-2 py-4 text-center text-xs text-slate-400"
        >
          暂无助手 (No Agents)
        </div>

        <div
          v-for="agent in agents"
          :key="agent.id"
          class="flex items-center gap-3 p-2 rounded-xl cursor-pointer transition-colors group"
          :class="
            activeAgentId === agent.id
              ? 'bg-sky-500/10 border border-sky-500/20'
              : 'hover:bg-white/30'
          "
          @click="switchAgent(agent)"
        >
          <div class="relative">
            <div
              class="w-10 h-10 rounded-full flex items-center justify-center text-white font-bold text-sm shadow-md"
              :class="
                activeAgentId === agent.id
                  ? 'bg-gradient-to-br from-sky-400 to-blue-500'
                  : 'bg-slate-400'
              "
            >
              {{ agent.name ? agent.name[0].toUpperCase() : '?' }}
            </div>
            <div
              v-if="activeAgentId === agent.id"
              class="absolute -bottom-0.5 -right-0.5 w-3 h-3 bg-emerald-500 border-2 border-white rounded-full"
            ></div>
          </div>
          <div class="flex-1 min-w-0">
            <div class="flex items-center justify-between">
              <span class="text-sm font-bold text-slate-800 truncate">{{ agent.name }}</span>
            </div>
            <div
              class="text-xs truncate"
              :class="activeAgentId === agent.id ? 'text-sky-600' : 'text-slate-400'"
            >
              {{ activeAgentId === agent.id ? 'Active' : 'Standby' }}
            </div>
          </div>
        </div>
      </div>

      <!-- 底部操作 -->
      <div class="p-4 border-t border-white/20 flex gap-2">
        <button
          class="flex-1 py-2 rounded-lg bg-indigo-500/10 text-indigo-600 text-xs font-bold hover:bg-indigo-500/20 transition-colors flex items-center justify-center gap-2"
          @click="openStronghold"
        >
          <Home class="w-4 h-4" />
          据点 (群聊)
        </button>
      </div>
    </div>

    <!-- 主聊天区域 -->
    <div class="flex-1 flex flex-col relative z-10 pt-8">
      <!-- 顶部标题栏 -->
      <header
        class="h-14 px-6 flex items-center justify-between border-b border-white/20 bg-white/20 backdrop-blur-sm"
      >
        <div class="flex items-center gap-3">
          <span class="text-lg font-bold text-slate-800"> 与 {{ activeAgentName }} 聊天中 </span>
          <span
            class="px-2 py-0.5 rounded-full text-[10px] font-bold border bg-emerald-500/10 text-emerald-600 border-emerald-500/20"
          >
            ONLINE
          </span>
        </div>
        <div class="flex items-center gap-4 text-slate-500">
          <button class="hover:text-sky-600 transition-colors"><Bell class="w-4 h-4" /></button>
          <button class="hover:text-sky-600 transition-colors"><Settings class="w-4 h-4" /></button>
        </div>
      </header>

      <!-- 聊天组件 -->
      <!-- 使用 key 强制在目标改变时重新挂载 -->
      <ChatInterface
        v-if="activeAgentId"
        :key="'direct-' + activeAgentId"
        :work-mode="false"
        class="flex-1"
        mode="direct"
        :target-id="activeAgentId"
        :agent-name="activeAgentName"
      />
      <div v-else class="flex-1 flex items-center justify-center text-slate-400">
        <div class="text-center">
          <p>请选择一个助手开始聊天</p>
        </div>
      </div>
    </div>
  </div>

  <!-- 移除模态框代码 -->
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { Search, Bell, Settings, Home } from 'lucide-vue-next'
import { invoke } from '@/utils/ipcAdapter'
import ChatInterface from '../components/chat/ChatInterface.vue'

const API_BASE = 'http://127.0.0.1:9120'

// 状态
const agents = ref([])
const isLoading = ref(false)
const errorMsg = ref('')
const activeAgentId = ref(null)
const activeAgentName = ref('Pero')

// 获取数据
const loadAgents = async () => {
  isLoading.value = true
  errorMsg.value = ''
  try {
    const resAll = await fetch(`${API_BASE}/api/agents`)
    if (!resAll.ok) throw new Error(`HTTP ${resAll.status}`)

    const allAgents = await resAll.json()
    agents.value = allAgents.filter((a) => a.is_enabled)

    const active = allAgents.find((a) => a.is_active)
    if (active) {
      activeAgentId.value = active.id
      activeAgentName.value = active.name
    } else if (agents.value.length > 0) {
      activeAgentId.value = agents.value[0].id
      activeAgentName.value = agents.value[0].name
    }
  } catch (e) {
    console.error('Failed to load agents', e)
    errorMsg.value = `加载失败: ${e.message}`
  } finally {
    isLoading.value = false
  }
}

// 操作
const switchAgent = async (agent) => {
  activeAgentId.value = agent.id
  activeAgentName.value = agent.name

  try {
    await fetch(`${API_BASE}/api/agents/active`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ agent_id: agent.id })
    })
  } catch (e) {
    console.error('Failed to switch agent', e)
  }
}

const openStronghold = async () => {
  try {
    await invoke('open_stronghold_window')
  } catch (e) {
    console.error('Failed to open stronghold window', e)
  }
}

onMounted(() => {
  loadAgents()
})
</script>

<style scoped>
.custom-scrollbar::-webkit-scrollbar {
  width: 4px;
}
.custom-scrollbar::-webkit-scrollbar-track {
  background: transparent;
}
.custom-scrollbar::-webkit-scrollbar-thumb {
  background: rgba(0, 0, 0, 0.1);
  border-radius: 2px;
}
.custom-scrollbar::-webkit-scrollbar-thumb:hover {
  background: rgba(0, 0, 0, 0.2);
}
</style>
