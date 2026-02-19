<template>
  <div class="relative h-full w-full overflow-hidden">
    <CustomTitleBar v-if="isElectron()" title="Stronghold" :show-mode-toggle="false" />

    <div :class="['absolute left-0 right-0 bottom-0 flex', isElectron() ? 'top-8' : 'top-0']">
      <!-- Left Sidebar: Facilities & Rooms -->
      <div
        class="w-64 flex flex-col border-r border-slate-200 dark:border-slate-800 bg-white/70 dark:bg-slate-900/70 backdrop-blur-md z-10"
      >
        <!-- Stronghold Header -->
        <div class="p-4 border-b border-slate-200 dark:border-slate-800">
          <h2 class="text-xl font-bold text-slate-800 dark:text-slate-100 flex items-center gap-2">
            <component :is="'HomeFilled'" class="w-5 h-5 text-indigo-500" />
            Stronghold
          </h2>
          <p class="text-xs text-slate-500 mt-1">据点管理系统</p>
        </div>

        <!-- Facilities Tabs (Horizontal or Vertical Icons) -->
        <div
          class="flex overflow-x-auto p-2 gap-2 bg-slate-50 dark:bg-slate-800/50 border-b border-slate-200 dark:border-slate-800"
        >
          <button
            v-for="fac in facilities"
            :key="fac.id"
            class="flex flex-col items-center justify-center p-2 rounded-lg min-w-[60px] transition-colors"
            :class="
              currentFacility?.id === fac.id
                ? 'bg-indigo-100 dark:bg-indigo-900/30 text-indigo-600 dark:text-indigo-400'
                : 'hover:bg-slate-200 dark:hover:bg-slate-800 text-slate-500'
            "
            @click="selectFacility(fac)"
          >
            <div class="w-6 h-6 rounded-full bg-current opacity-20 mb-1"></div>
            <span class="text-[10px] font-medium truncate w-full text-center">{{ fac.name }}</span>
          </button>
          <!-- Create Facility Button (Hidden by default, can be re-enabled if needed) -->
          <!-- 
        <button
          class="flex flex-col items-center justify-center p-2 rounded-lg min-w-[60px] text-slate-400 hover:bg-slate-200 dark:hover:bg-slate-800"
          @click="showCreateFacility = true"
        >
          <component :is="'Plus'" class="w-5 h-5" />
          <span class="text-[10px]">新建</span>
        </button>
        --></div>

        <!-- Rooms List -->
        <div class="flex-1 overflow-y-auto p-2 space-y-1">
          <div v-if="loading" class="text-center py-4 text-slate-400 text-xs">加载中...</div>
          <template v-else>
            <div
              v-for="room in rooms"
              :key="room.id"
              class="flex items-center gap-3 p-3 rounded-lg cursor-pointer transition-all group"
              :class="
                currentRoom?.id === room.id
                  ? 'bg-indigo-50 dark:bg-indigo-900/20 text-indigo-700 dark:text-indigo-300 shadow-sm'
                  : 'hover:bg-slate-100 dark:hover:bg-slate-800/50 text-slate-600 dark:text-slate-400'
              "
              @click="selectRoom(room)"
            >
              <div
                class="w-2 h-2 rounded-full"
                :class="
                  currentRoom?.id === room.id ? 'bg-indigo-500' : 'bg-slate-300 dark:bg-slate-600'
                "
              ></div>
              <div class="flex-1 min-w-0">
                <div class="font-medium text-sm truncate">{{ room.name }}</div>
                <div class="text-[10px] text-slate-400 truncate">{{ room.description }}</div>
              </div>
            </div>
          </template>
        </div>
      </div>

      <!-- Center: Chat Area -->
      <div
        class="flex-1 flex flex-col min-w-0 bg-slate-50/70 dark:bg-slate-900/70 backdrop-blur-md relative"
      >
        <!-- Background Gradient (Copied from ChatModeView) -->
        <div
          class="absolute inset-0 bg-gradient-to-br from-sky-200/20 via-sky-100/10 to-transparent pointer-events-none z-0"
        ></div>

        <div v-if="currentRoom" class="flex flex-col h-full relative z-10">
          <!-- Room Header -->
          <header
            class="bg-white/80 dark:bg-slate-900/80 backdrop-blur-md border-b border-slate-200 dark:border-slate-800 px-6 py-4 flex justify-between items-center shadow-sm z-20"
          >
            <div>
              <h1
                class="text-xl font-bold text-slate-800 dark:text-slate-100 flex items-center gap-2"
              >
                {{ currentRoom.name }}
                <span
                  class="px-2 py-0.5 rounded-full bg-slate-100 dark:bg-slate-800 text-xs text-slate-500 font-normal"
                >
                  {{ currentFacility?.name }}
                </span>
              </h1>
              <p class="text-xs text-slate-500 mt-0.5">{{ currentRoom.description }}</p>
            </div>
            <div class="flex items-center gap-2">
              <!-- Room Actions -->
              <button class="p-2 text-slate-400 hover:text-indigo-500 transition-colors">
                <component :is="'Setting'" class="w-5 h-5" />
              </button>
            </div>
          </header>

          <!-- Chat Interface Reuse -->
          <!-- Use key to force remount when room changes, ensuring history is fetched for the new room -->
          <ChatInterface
            :key="currentRoom.id"
            mode="group"
            :target-id="currentRoom.id.toString()"
            :agent-name="currentRoom.name"
            :work-mode="false"
            class="flex-1"
          />
        </div>

        <!-- No Room Selected State -->
        <div
          v-else
          class="flex flex-col items-center justify-center h-full text-slate-400 relative z-10"
        >
          <component :is="'OfficeBuilding'" class="w-16 h-16 mb-4 opacity-30" />
          <h3 class="text-lg font-medium text-slate-600 dark:text-slate-300">欢迎来到据点</h3>
          <p class="text-sm">请从左侧选择一个房间开始</p>
        </div>
      </div>

      <!-- Right Sidebar: Room Info & Agents -->
      <div
        class="w-72 border-l border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 hidden lg:flex flex-col"
      >
        <div
          class="p-4 border-b border-slate-200 dark:border-slate-800 flex justify-between items-center"
        >
          <h3 class="font-bold text-slate-700 dark:text-slate-200 text-sm uppercase tracking-wider">
            当前状态
          </h3>
          <!-- Call Butler Button -->
          <button
            class="text-xs bg-slate-100 dark:bg-slate-800 hover:bg-indigo-100 dark:hover:bg-indigo-900/50 text-slate-600 dark:text-slate-300 hover:text-indigo-600 dark:hover:text-indigo-400 px-2 py-1 rounded transition-colors flex items-center gap-1"
            @click="openButlerModal"
          >
            <component :is="'Service'" class="w-3 h-3" />
            呼叫管家
          </button>
        </div>

        <!-- Room Env -->
        <div v-if="currentRoom" class="p-4 border-b border-slate-200 dark:border-slate-800">
          <h4 class="text-xs font-bold text-slate-500 mb-2">环境参数</h4>
          <div
            class="bg-slate-50 dark:bg-slate-800 rounded-lg p-3 text-xs font-mono break-all text-slate-600 dark:text-slate-300"
          >
            <div v-if="currentRoom.environment_json" class="grid grid-cols-2 gap-y-1">
              <template v-for="(value, key) in JSON.parse(currentRoom.environment_json)" :key="key">
                <span class="text-slate-400">{{ key }}:</span>
                <span class="text-right">{{ value }}</span>
              </template>
            </div>
            <div v-else class="text-slate-400 text-center">无数据</div>
          </div>
        </div>

        <!-- Agents Lists -->
        <div class="flex-1 overflow-y-auto p-4 space-y-6">
          <!-- Section 1: In This Room -->
          <div>
            <h4 class="text-xs font-bold text-slate-500 mb-3 flex justify-between items-center">
              本房间
              <span
                class="bg-green-100 dark:bg-green-900/30 text-green-600 dark:text-green-400 px-1.5 py-0.5 rounded text-[10px]"
                >Active</span
              >
            </h4>
            <div class="space-y-3">
              <template v-if="currentRoomAgents.length > 0">
                <div
                  v-for="agent in currentRoomAgents"
                  :key="agent.name"
                  class="flex items-center gap-3"
                >
                  <div
                    class="w-8 h-8 rounded-full bg-slate-100 dark:bg-slate-800 flex items-center justify-center overflow-hidden border border-slate-200 dark:border-slate-700"
                  >
                    <!-- <img v-if="agent.avatar" :src="agent.avatar" class="w-full h-full object-cover" /> -->
                    <span class="text-xs font-bold text-slate-500">{{
                      agent.name[0].toUpperCase()
                    }}</span>
                  </div>
                  <div>
                    <div class="text-sm font-medium text-slate-700 dark:text-slate-200">
                      {{ agent.name }}
                    </div>
                    <div class="text-[10px] text-green-500 flex items-center gap-1">
                      <span class="w-1.5 h-1.5 rounded-full bg-green-500"></span>
                      Here
                    </div>
                  </div>
                </div>
              </template>
              <div v-else class="text-xs text-slate-400 italic py-2 text-center">空无一人</div>
            </div>
          </div>

          <!-- Section 2: All Residents -->
          <div>
            <h4 class="text-xs font-bold text-slate-500 mb-3 flex justify-between items-center">
              据点全员
              <span
                class="bg-slate-100 dark:bg-slate-800 text-slate-500 px-1.5 py-0.5 rounded text-[10px]"
                >Total</span
              >
            </h4>
            <div class="space-y-3">
              <div
                v-for="agent in agentsStatus"
                :key="agent.name"
                class="flex items-center gap-3 opacity-75 hover:opacity-100 transition-opacity cursor-pointer"
                title="点击呼叫此角色"
                @click="summonAgent(agent.name)"
              >
                <div
                  class="w-8 h-8 rounded-full bg-slate-100 dark:bg-slate-800 flex items-center justify-center overflow-hidden border border-slate-200 dark:border-slate-700"
                >
                  <!-- <img v-if="agent.avatar" :src="agent.avatar" class="w-full h-full object-cover" /> -->
                  <span class="text-xs font-bold text-slate-500">{{
                    agent.name[0].toUpperCase()
                  }}</span>
                </div>
                <div>
                  <div class="text-sm font-medium text-slate-700 dark:text-slate-200">
                    {{ agent.name }}
                  </div>
                  <div class="text-[10px] text-slate-400 flex items-center gap-1">
                    <component :is="'Location'" class="w-3 h-3" />
                    {{ agent.room_name }}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Butler Status -->
        <div
          class="p-4 bg-slate-50 dark:bg-slate-800 border-t border-slate-200 dark:border-slate-800"
        >
          <div class="flex items-center gap-2 mb-2">
            <component :is="'Service'" class="w-4 h-4 text-amber-500" />
            <span class="text-xs font-bold text-slate-700 dark:text-slate-300">管家系统</span>
          </div>
          <div class="text-[10px] text-slate-500 leading-relaxed line-clamp-2">
            {{ butlerConfig?.persona || '系统管家运行正常' }}
          </div>
          <div class="mt-1 text-[9px] text-slate-400 italic">
            [提示] 请使用 group/butler/persona.md 进行人设配置
          </div>
        </div>
      </div>
    </div>

    <!-- Butler Call Modal -->
    <div
      v-if="showButlerModal"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm"
    >
      <div
        class="bg-white dark:bg-slate-900 w-96 rounded-xl shadow-2xl border border-slate-200 dark:border-slate-700 overflow-hidden transform transition-all"
      >
        <div
          class="p-4 border-b border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-800/50 flex justify-between items-center"
        >
          <h3 class="font-bold text-slate-700 dark:text-slate-200 flex items-center gap-2">
            <component :is="'Service'" class="w-4 h-4 text-amber-500" />
            呼叫管家
          </h3>
          <button
            class="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200"
            @click="showButlerModal = false"
          >
            <component :is="'Close'" class="w-4 h-4" />
          </button>
        </div>
        <div class="p-4">
          <textarea
            v-model="butlerQuery"
            class="w-full h-32 bg-slate-100 dark:bg-slate-800 border-0 rounded-lg p-3 text-sm focus:ring-2 focus:ring-indigo-500 resize-none placeholder-slate-400 text-slate-700 dark:text-slate-200"
            placeholder="告诉管家你需要什么... 例如：&#10;“把客厅灯光调暗一点”&#10;“叫 Pero 过来”&#10;“建一个新房间叫‘书房’”"
            @keydown.enter.ctrl="submitButlerCall"
          ></textarea>
          <div class="flex justify-end mt-4 gap-2">
            <button
              class="px-3 py-1.5 text-xs text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800 rounded transition-colors"
              @click="showButlerModal = false"
            >
              取消
            </button>
            <button
              class="px-3 py-1.5 text-xs bg-indigo-600 hover:bg-indigo-700 text-white rounded shadow-sm transition-colors flex items-center gap-1 disabled:opacity-50 disabled:cursor-not-allowed"
              :disabled="!butlerQuery.trim() || callingButler"
              @click="submitButlerCall"
            >
              <component :is="'Loading'" v-if="callingButler" class="w-3 h-3 animate-spin" />
              <span v-else>发送指令</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, onUnmounted, ref, computed } from 'vue'
import { useStronghold } from '../composables/useStronghold'
import { isElectron } from '@/utils/ipcAdapter'
import ChatInterface from '../components/chat/ChatInterface.vue'
import CustomTitleBar from '../components/layout/CustomTitleBar.vue'

const {
  facilities,
  rooms,
  currentRoom,
  currentFacility,
  // butlerConfig,
  agentsStatus,
  // loading,
  fetchFacilities,
  fetchRooms,
  // selectFacility,
  selectRoom,
  fetchButler,
  fetchAgentsStatus,
  callButler
} = useStronghold()

// const showCreateFacility = ref(false)
// const showCreateRoom = ref(false)

// Butler Modal
const showButlerModal = ref(false)
const butlerQuery = ref('')
const callingButler = ref(false)

const openButlerModal = () => {
  butlerQuery.value = ''
  showButlerModal.value = true
}

const submitButlerCall = async () => {
  if (!butlerQuery.value.trim()) return

  callingButler.value = true
  try {
    await callButler(butlerQuery.value)
    showButlerModal.value = false
    butlerQuery.value = ''

    // Refresh room list and environment after butler action
    if (currentFacility.value) {
      await fetchRooms(currentFacility.value.id)
    }
    // Also re-fetch current room to get updated env json
    if (currentRoom.value) {
      // Small trick: re-select room to refresh its data
      // But better: useStronghold should expose a way to refresh current room
      // For now, fetchRooms updates the list, we just need to update currentRoom ref from list
      const updatedRoom = rooms.value.find((r) => r.id === currentRoom.value.id)
      if (updatedRoom) {
        selectRoom(updatedRoom)
      }
    }
  } catch (e) {
    console.error(e)
    // Error handling (maybe toast)
  } finally {
    callingButler.value = false
  }
}

// Helper to quickly summon agent via text
const summonAgent = (agentName) => {
  butlerQuery.value = `把 ${agentName} 叫到这里来`
  showButlerModal.value = true
}

// Computed: Filter agents in current room
const currentRoomAgents = computed(() => {
  if (!currentRoom.value || !agentsStatus.value) return []
  return agentsStatus.value.filter((a) => a.room_id === currentRoom.value.id)
})

// Poll agents status periodically
let pollTimer = null

onMounted(async () => {
  await fetchFacilities()
  await fetchButler()
  await fetchAgentsStatus()

  // Simple polling for status updates (every 5s)
  pollTimer = setInterval(fetchAgentsStatus, 5000)
})

onUnmounted(() => {
  if (pollTimer) {
    clearInterval(pollTimer)
  }
})
</script>

<style scoped>
/* Custom Scrollbar */
.custom-scrollbar::-webkit-scrollbar {
  width: 4px;
}
.custom-scrollbar::-webkit-scrollbar-track {
  background: transparent;
}
.custom-scrollbar::-webkit-scrollbar-thumb {
  background: #cbd5e1;
  border-radius: 4px;
}
.dark .custom-scrollbar::-webkit-scrollbar-thumb {
  background: #475569;
}
</style>
