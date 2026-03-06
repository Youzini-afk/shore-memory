<template>
  <div
    class="min-h-screen bg-sky-50 text-slate-800 selection:bg-sky-500/20 font-sans overflow-hidden"
  >
    <div v-once class="fixed top-0 left-0 w-full h-full overflow-hidden pointer-events-none z-0">
      <div
        class="absolute top-[-10%] left-[-10%] w-[60%] h-[60%] bg-sky-300/20 blur-[150px] rounded-full animate-pulse"
        style="will-change: transform, opacity"
      ></div>
      <div
        class="absolute bottom-[-10%] right-[-10%] w-[60%] h-[60%] bg-sky-300/20 blur-[150px] rounded-full animate-pulse"
        style="animation-delay: 2s; will-change: transform, opacity"
      ></div>
    </div>

    <CustomTitleBar v-if="isElectron()" :transparent="true" title="Pero Dashboard" />

    <div class="flex h-screen overflow-hidden relative z-10" :class="{ 'pt-8': isElectron() }">
      <!-- Sidebar -->
      <aside
        class="w-64 flex flex-col border-r-2 border-sky-100/50 glass-effect transition-all duration-300 z-20 relative"
      >
        <!-- Pixel Shadow Line on Right -->
        <div
          class="absolute right-[-2px] top-0 bottom-0 w-[2px] bg-sky-200/30 pointer-events-none"
        ></div>

        <!-- Brand -->
        <div class="p-6 pb-2 relative z-10">
          <div class="flex items-center gap-4 mb-6">
            <div
              class="relative w-12 h-12 pixel-border-sky overflow-hidden group cursor-pointer transition-transform duration-300 hover:scale-110 press-effect bg-sky-50 p-1.5"
            >
              <img
                :src="logoImg"
                class="w-full h-full object-cover transition-transform duration-500 group-hover:rotate-12"
                alt="Logo"
              />
              <div
                class="absolute inset-0 bg-gradient-to-tr from-sky-300/20 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300"
              ></div>
            </div>
            <div class="flex flex-col">
              <span class="text-[10px] text-slate-400 font-bold uppercase tracking-wider mb-0.5"
                >PeroperoChat</span
              >
              <h1
                class="text-lg font-black bg-clip-text text-transparent bg-gradient-to-r from-slate-800 to-sky-600 font-pixel"
              >
                萌动链接
              </h1>
              <PTooltip content="点击检查更新" placement="bottom">
                <div class="flex items-center gap-1.5 mt-1" @click="checkForUpdates">
                  <span
                    class="text-[9px] font-mono text-white bg-sky-400 px-1.5 py-[1px] pixel-border-sm cursor-pointer hover:bg-sky-500 transition-all press-effect"
                    >v{{ appVersion }}</span
                  >
                  <PixelIcon
                    v-if="isCheckingUpdate"
                    name="refresh"
                    size="xs"
                    animation="spin"
                    class="text-sky-500"
                  />
                </div>
              </PTooltip>
            </div>
          </div>
        </div>

        <!-- Menu -->
        <nav class="flex-1 overflow-y-auto px-4 space-y-6 scrollbar-hide py-2">
          <div v-for="(group, gIndex) in menuGroups" :key="gIndex">
            <div v-if="group.title" class="px-2 mb-3 mt-2 flex items-center gap-2">
              <div class="h-1 w-1 bg-slate-300 rounded-full"></div>
              <span class="text-[10px] font-bold text-slate-400 uppercase tracking-[0.15em]">{{
                group.title
              }}</span>
              <div class="flex-1 h-[1px] bg-slate-100"></div>
            </div>

            <div class="space-y-1.5">
              <button
                v-for="item in group.items"
                :key="item.id"
                :class="[
                  'w-full flex items-center gap-3 px-3 py-2.5 text-sm font-bold transition-all duration-300 group press-effect relative overflow-hidden rounded-xl hover-pixel-bounce',
                  currentTab === item.id
                    ? item.variant === 'danger'
                      ? 'bg-rose-50 text-rose-600 border-2 border-rose-200 translate-x-1 shadow-sm'
                      : 'bg-white text-sky-600 border-2 border-sky-100 translate-x-1 shadow-md shadow-sky-100/50'
                    : 'text-slate-500 hover:bg-sky-50/50 hover:text-sky-600 hover:translate-x-1 border border-transparent'
                ]"
                @click="handleTabSelect(item.id)"
              >
                <!-- Active Indicator -->
                <div
                  v-if="currentTab === item.id"
                  class="absolute left-0 top-2 bottom-2 w-1 rounded-full transition-all duration-500"
                  :class="item.variant === 'danger' ? 'bg-rose-400' : 'bg-sky-400'"
                ></div>

                <PixelIcon
                  :name="item.icon"
                  size="sm"
                  class="transition-colors relative z-10"
                  :class="[
                    currentTab === item.id
                      ? item.variant === 'danger'
                        ? 'text-rose-500'
                        : 'text-sky-500'
                      : item.variant === 'danger'
                        ? 'text-slate-400 group-hover:text-rose-500'
                        : 'text-slate-400 group-hover:text-sky-500'
                  ]"
                />
                <span class="relative z-10">{{ item.label }}</span>

                <!-- Pixel Arrow for Active -->
                <div
                  v-if="currentTab === item.id"
                  class="ml-auto opacity-0 group-hover:opacity-100 transition-opacity"
                >
                  <div class="w-1.5 h-1.5 bg-current transform rotate-45"></div>
                </div>
              </button>
            </div>
          </div>
        </nav>

        <!-- Footer -->
        <div class="p-4 border-t-2 border-sky-100/50 bg-sky-50/30 relative">
          <!-- Pixel Decoration -->
          <div class="absolute top-[-2px] left-4 right-4 h-[2px] bg-white"></div>

          <button
            class="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-rose-50 hover:bg-rose-100 text-rose-500 hover:text-rose-600 pixel-border-pink transition-all duration-200 group mb-4 press-effect shadow-sm"
            @click="handleQuitApp"
          >
            <PixelIcon
              name="logout"
              size="sm"
              class="group-hover:-translate-x-1 transition-transform"
            />
            <span class="text-xs font-black tracking-widest">退出系统</span>
          </button>

          <div
            class="flex items-center justify-between px-2 py-1 bg-white/50 rounded border border-sky-100"
          >
            <div class="flex items-center gap-2.5">
              <span class="relative flex h-2.5 w-2.5">
                <span
                  v-if="isBackendOnline"
                  class="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"
                ></span>
                <span
                  class="relative inline-flex rounded-full h-2.5 w-2.5 border-2 border-white shadow-sm"
                  :class="isBackendOnline ? 'bg-emerald-500' : 'bg-rose-500'"
                ></span>
              </span>
              <div class="flex flex-col">
                <span class="text-[10px] text-slate-400 font-bold uppercase leading-none"
                  >Status</span
                >
                <span
                  class="text-[10px] font-bold"
                  :class="isBackendOnline ? 'text-emerald-600' : 'text-rose-600'"
                  >{{ isBackendOnline ? 'SYSTEM ONLINE' : 'OFFLINE' }}</span
                >
              </div>
            </div>
            <PTooltip content="刷新数据" placement="top">
              <button
                class="p-1.5 bg-white pixel-border-sm hover:bg-sky-50 text-slate-400 hover:text-sky-500 transition-all press-effect"
                @click="fetchAllData(false)"
              >
                <PixelIcon name="refresh" size="xs" :animation="isGlobalRefreshing ? 'spin' : ''" />
              </button>
            </PTooltip>
          </div>
        </div>
      </aside>

      <!-- Main Content -->
      <main class="flex-1 overflow-hidden relative flex flex-col min-w-0 bg-transparent">
        <!-- ✨ Background Ambient Light & Particles ✨ -->
        <div
          class="absolute inset-0 pointer-events-none transition-all duration-1000 z-0"
          :style="ambientLightStyle"
        ></div>

        <!-- 🐾 Floating Background Particles -->
        <div class="absolute inset-0 pointer-events-none z-0 overflow-hidden">
          <div
            v-for="p in particles"
            :key="p.id"
            class="absolute animate-float-slow opacity-20"
            :style="p.style"
          >
            <PixelIcon :name="p.icon" :size="p.size" class="text-sky-300" />
          </div>
        </div>

        <div
          class="view-container-wrapper relative z-10 flex-1"
          :style="
            ['logs', 'terminal', 'napcat'].includes(currentTab)
              ? 'height: 100%; overflow: hidden;'
              : 'min-height: 100%;'
          "
        >
          <Transition name="fade-slide" mode="out-in">
            <!-- 1. 仪表盘概览 -->
            <div
              v-if="currentTab === 'overview'"
              key="overview"
              class="p-6 space-y-6 overflow-y-auto h-full custom-scrollbar"
            >
              <!-- 统计卡片 (Overview Cards) -->
              <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
                <PCard pixel hoverable variant="purple" glow class="group">
                  <div class="flex items-center gap-4 relative">
                    <div
                      class="p-4 bg-purple-100 pixel-border-pink text-purple-500 group-hover:scale-110 group-hover:rotate-6 transition-transform duration-500"
                    >
                      <PixelIcon name="brain" size="xl" animation="bounce" />
                    </div>
                    <div class="relative z-10">
                      <h3 class="text-sm font-bold text-slate-600 flex items-center gap-1.5">
                        核心记忆
                        <span class="text-[10px] text-purple-400 font-mono">Core</span>
                      </h3>
                      <div class="text-2xl font-black text-slate-800">
                        {{ stats.total_memories || memories.length }}
                      </div>
                      <button
                        class="mt-1 text-xs text-purple-500 hover:text-purple-600 font-medium flex items-center gap-1 transition-colors group/btn"
                        @click="showImportStoryDialog = true"
                      >
                        <PixelIcon
                          name="download"
                          size="xs"
                          class="rotate-180 group-hover/btn:-translate-y-0.5 transition-transform"
                        />
                        导入故事 <PixelIcon name="thought" size="xs" class="ml-0.5" />
                      </button>
                    </div>
                    <!-- Decorative element -->
                    <div
                      class="absolute -right-4 -bottom-4 text-purple-200/20 group-hover:opacity-10 group-hover:scale-150 transition-all duration-700 pointer-events-none"
                    >
                      <PixelIcon name="paw" size="3xl" />
                    </div>
                  </div>
                </PCard>

                <PCard pixel hoverable variant="sky" glow class="group">
                  <div class="flex items-center gap-4 relative">
                    <div
                      class="p-4 bg-sky-100 pixel-border-sky text-sky-500 group-hover:scale-110 group-hover:-rotate-6 transition-transform duration-500"
                    >
                      <PixelIcon name="chat" size="xl" animation="bounce" />
                    </div>
                    <div class="relative z-10">
                      <h3 class="text-sm font-bold text-slate-600 flex items-center gap-1.5">
                        近期对话
                        <span class="text-[10px] text-sky-400 font-mono">Logs</span>
                      </h3>
                      <div class="text-2xl font-black text-slate-800">
                        {{ stats.total_logs || logs.length }}
                      </div>
                    </div>
                    <!-- Decorative element -->
                    <div
                      class="absolute -right-4 -bottom-4 text-sky-200/20 group-hover:opacity-10 group-hover:scale-150 transition-all duration-700 pointer-events-none"
                    >
                      <PixelIcon name="thought" size="3xl" />
                    </div>
                  </div>
                </PCard>

                <PCard pixel hoverable variant="orange" glow class="group">
                  <div class="flex items-center gap-4 relative">
                    <div
                      class="p-4 bg-orange-100 pixel-border-orange text-orange-500 group-hover:scale-110 group-hover:rotate-6 transition-transform duration-500"
                    >
                      <PixelIcon name="flash" size="xl" animation="bounce" />
                    </div>
                    <div class="relative z-10">
                      <h3 class="text-sm font-bold text-slate-600 flex items-center gap-1.5">
                        待办任务
                        <span class="text-[10px] text-orange-400 font-mono">Tasks</span>
                      </h3>
                      <div class="text-2xl font-black text-slate-800">
                        {{ stats.total_tasks || tasks.length }}
                      </div>
                    </div>
                    <!-- Decorative element -->
                    <div
                      class="absolute -right-4 -bottom-4 text-orange-200/20 group-hover:opacity-10 group-hover:scale-150 transition-all duration-700 pointer-events-none"
                    >
                      <PixelIcon name="sparkle" size="3xl" />
                    </div>
                  </div>
                </PCard>
              </div>

              <!-- 当前状态 -->
              <PCard pixel overflow-visible class="z-30">
                <template #header>
                  <div class="flex items-center justify-between">
                    <span class="font-bold text-lg text-slate-800 flex items-center gap-2">
                      当前状态
                      <span class="text-xs font-normal text-slate-400 font-mono">Status</span>
                    </span>
                    <div class="flex items-center gap-4">
                      <!-- NapCat Status -->
                      <PTooltip
                        v-if="!napCatStatus.disabled"
                        :content="
                          napCatStatus.ws_connected
                            ? napCatStatus.api_responsive
                              ? `延迟: ${napCatStatus.latency_ms}ms`
                              : 'API 无响应'
                            : '未连接'
                        "
                        placement="bottom"
                      >
                        <div class="flex items-center gap-2 px-3 py-1.5 bg-sky-50 pixel-border-sky">
                          <span class="text-xs text-sky-400 font-bold font-mono">NAPCAT</span>
                          <div class="flex items-center gap-1.5">
                            <span class="relative flex h-2 w-2">
                              <span
                                v-if="napCatStatus.ws_connected && napCatStatus.api_responsive"
                                class="animate-ping absolute inline-flex h-full w-full rounded-full bg-sky-400 opacity-75"
                              ></span>
                              <span
                                class="relative inline-flex rounded-full h-2 w-2"
                                :class="
                                  napCatStatus.ws_connected && napCatStatus.api_responsive
                                    ? 'bg-sky-500'
                                    : napCatStatus.ws_connected
                                      ? 'bg-amber-500'
                                      : 'bg-rose-500'
                                "
                              ></span>
                            </span>
                            <span
                              v-if="napCatStatus.ws_connected && napCatStatus.api_responsive"
                              class="text-xs font-mono font-bold text-sky-600"
                              >{{ napCatStatus.latency_ms }}ms</span
                            >
                          </div>
                        </div>
                      </PTooltip>

                      <!-- 角色选择 (Agent Selector) -->
                      <div class="flex flex-col gap-1.5 min-w-[160px]">
                        <label
                          class="text-[10px] font-bold text-slate-400 flex items-center gap-1.5 ml-1 uppercase tracking-wider"
                        >
                          <span class="w-1.5 h-1.5 rounded-full bg-sky-500 animate-pulse"></span>
                          当前角色 <span class="opacity-50 font-normal">Agent</span>
                        </label>
                        <div class="relative group/agent">
                          <button
                            class="w-full flex items-center justify-between px-4 py-2.5 bg-white hover:bg-sky-50 pixel-border-sky text-sm transition-all press-effect group/btn"
                            :class="isSwitchingAgent ? 'opacity-50 cursor-not-allowed' : ''"
                          >
                            <span class="text-sky-600 font-bold flex items-center gap-2">
                              <span
                                class="opacity-0 group-hover/btn:opacity-100 transition-all duration-300 -translate-x-2 group-hover:translate-x-0"
                              >
                                <PixelIcon name="paw" size="xs" />
                              </span>
                              {{ activeAgent?.name || '未知' }}
                              <span class="opacity-40 group-hover:opacity-100 transition-opacity">
                                <PixelIcon name="sparkle" size="xs" />
                              </span>
                            </span>
                            <PixelIcon
                              name="chevron-down"
                              size="xs"
                              class="text-slate-400 group-hover/agent:rotate-180 transition-transform duration-500"
                            />
                          </button>

                          <!-- 下拉菜单 (Dropdown Menu) -->
                          <div
                            class="absolute right-0 top-full mt-2 w-full py-2 bg-white/70 backdrop-blur-xl border border-sky-100 rounded-2xl shadow-2xl opacity-0 invisible group-hover/agent:opacity-100 group-hover/agent:visible transition-all duration-300 z-50 transform origin-top scale-95 group-hover/agent:scale-100"
                          >
                            <div class="px-3 py-1.5 mb-1 border-b border-sky-50">
                              <span
                                class="text-[10px] font-bold text-slate-400 uppercase tracking-widest flex items-center gap-1"
                              >
                                切换角色
                                <PixelIcon name="sparkle" size="xs" class="animate-bounce" />
                              </span>
                            </div>
                            <button
                              v-for="agent in availableAgents"
                              :key="agent.id"
                              class="w-full text-left px-4 py-2.5 text-sm hover:bg-sky-50 transition-all flex items-center justify-between group/item"
                              :class="{
                                'text-sky-600 font-bold bg-sky-50/50': agent.id === activeAgent?.id,
                                'text-slate-500': agent.id !== activeAgent?.id,
                                'opacity-50 cursor-not-allowed': !agent.is_enabled
                              }"
                              :disabled="agent.id === activeAgent?.id || !agent.is_enabled"
                              @click="switchAgent(agent.id)"
                            >
                              <div class="flex items-center gap-2">
                                <span
                                  class="opacity-0 group-hover/item:opacity-100 transition-opacity"
                                >
                                  <PixelIcon name="paw" size="xs" />
                                </span>
                                <span>{{ agent.name }}</span>
                              </div>
                              <span
                                v-if="!agent.is_enabled"
                                class="text-[10px] text-slate-400 font-bold px-1.5 py-0.5 bg-sky-50 rounded-md"
                                >DISABLED</span
                              >
                            </button>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                </template>

                <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div
                    class="bg-sky-50/40 pixel-border-sky p-5 transition-all hover:bg-white hover:pixel-border-pink group relative"
                  >
                    <div
                      class="text-xs text-slate-500 font-bold uppercase tracking-wider mb-3 flex items-center justify-between relative z-10"
                    >
                      心情 <span class="text-[10px] text-sky-400/60 font-mono">Mood</span>
                      <span
                        class="opacity-0 group-hover:opacity-100 transition-all duration-500 transform group-hover:scale-125 group-hover:rotate-12 text-sky-500"
                        ><PixelIcon name="paw" size="xs"
                      /></span>
                    </div>
                    <div
                      class="text-2xl font-black text-sky-500 mb-4 relative z-10 group-hover:scale-105 transition-transform origin-left"
                    >
                      {{ petState.mood || '未知' }}
                    </div>
                    <div
                      class="h-1.5 bg-sky-100/50 rounded-full overflow-hidden relative z-10 shadow-inner"
                    >
                      <div
                        class="h-full bg-gradient-to-r from-sky-400 to-sky-300 rounded-full transition-all duration-1000 group-hover:shadow-[0_0_12px_rgba(14,165,233,0.3)]"
                        :style="{ width: '80%' }"
                      ></div>
                    </div>
                    <!-- Decoration -->
                    <div
                      class="absolute -right-2 -bottom-2 opacity-[0.05] group-hover:opacity-[0.1] transition-all duration-700 pointer-events-none"
                    >
                      <PixelIcon name="paw" size="3xl" />
                    </div>
                  </div>

                  <div
                    class="bg-sky-50/40 pixel-border-sky p-5 transition-all hover:bg-white hover:pixel-border-pink group relative"
                  >
                    <div
                      class="text-xs text-slate-500 font-bold uppercase tracking-wider mb-3 flex items-center justify-between relative z-10"
                    >
                      氛围 <span class="text-[10px] text-sky-400/60 font-mono">Vibe</span>
                      <span
                        class="opacity-0 group-hover:opacity-100 transition-all duration-500 transform group-hover:scale-125 group-hover:-rotate-12 text-sky-500"
                        ><PixelIcon name="sparkle" size="xs"
                      /></span>
                    </div>
                    <div
                      class="text-2xl font-black text-sky-500 mb-4 relative z-10 group-hover:scale-105 transition-transform origin-left"
                    >
                      {{ petState.vibe || '未知' }}
                    </div>
                    <div
                      class="h-1.5 bg-sky-100/50 rounded-full overflow-hidden relative z-10 shadow-inner"
                    >
                      <div
                        class="h-full bg-gradient-to-r from-sky-400 to-sky-300 rounded-full transition-all duration-1000 group-hover:shadow-[0_0_12px_rgba(14,165,233,0.3)]"
                        :style="{ width: '60%' }"
                      ></div>
                    </div>
                    <!-- Decoration -->
                    <div
                      class="absolute -right-2 -bottom-2 opacity-[0.05] group-hover:opacity-[0.1] transition-all duration-700 pointer-events-none"
                    >
                      <PixelIcon name="thought" size="3xl" />
                    </div>
                  </div>

                  <div
                    class="bg-sky-50/40 pixel-border-sky p-5 transition-all hover:bg-white hover:pixel-border-pink group relative"
                  >
                    <div
                      class="text-xs text-slate-500 font-bold uppercase tracking-wider mb-3 flex items-center justify-between relative z-10"
                    >
                      想法 <span class="text-[10px] text-sky-400/60 font-mono">Mind</span>
                      <span
                        class="opacity-0 group-hover:opacity-100 transition-all duration-500 transform group-hover:scale-125 group-hover:rotate-12 text-sky-500"
                        ><PixelIcon name="thought" size="xs"
                      /></span>
                    </div>
                    <div
                      class="text-2xl font-black text-sky-500 mb-4 relative z-10 group-hover:scale-105 transition-transform origin-left"
                    >
                      {{ petState.mind || '未知' }}
                    </div>
                    <div
                      class="h-1.5 bg-sky-100/50 rounded-full overflow-hidden relative z-10 shadow-inner"
                    >
                      <div
                        class="h-full bg-gradient-to-r from-sky-400 to-sky-300 rounded-full transition-all duration-1000 group-hover:shadow-[0_0_12px_rgba(14,165,233,0.3)]"
                        :style="{ width: '90%' }"
                      ></div>
                    </div>
                    <!-- Decoration -->
                    <div
                      class="absolute -right-2 -bottom-2 opacity-[0.05] group-hover:opacity-[0.1] transition-all duration-700 pointer-events-none"
                    >
                      <PixelIcon name="sparkle" size="3xl" />
                    </div>
                  </div>
                </div>
              </PCard>

              <!-- NIT Status -->
              <PCard
                v-if="nitStatus"
                pixel
                class="hover:pixel-border-pink transition-all group/nit"
              >
                <div class="flex items-center justify-between">
                  <div class="flex items-center gap-3">
                    <div class="p-3 bg-sky-100 pixel-border-sm text-sky-500 group">
                      <PixelIcon
                        name="chart"
                        size="md"
                        class="group-hover:scale-110 transition-transform"
                      />
                    </div>
                    <div>
                      <div class="flex items-center gap-2">
                        <span class="font-bold text-slate-800">NapCat 协议状态</span>
                        <span
                          class="px-2 py-0.5 bg-sky-100 text-sky-600 text-[10px] font-bold pixel-border-sm border-sky-200 uppercase"
                          >Active</span
                        >
                      </div>
                      <div class="text-sm text-slate-500 mt-0.5 flex items-center gap-3">
                        <span
                          ><strong class="text-sky-600 font-mono">{{
                            nitStatus.plugins_count
                          }}</strong>
                          <span class="text-slate-400 ml-1">插件已加载</span></span
                        >
                        <span class="w-px h-3 bg-sky-100"></span>
                        <span
                          ><strong class="text-sky-600 font-mono">{{
                            nitStatus.active_mcp_count
                          }}</strong>
                          <span class="text-slate-400 ml-1">MCP 服务已连接</span></span
                        >
                      </div>
                    </div>
                  </div>
                </div>
                <div v-if="nitStatus.plugins?.length" class="mt-4 flex flex-wrap gap-2">
                  <span
                    v-for="p in nitStatus.plugins.slice(0, 8)"
                    :key="p.name"
                    class="px-2.5 py-1 bg-sky-50 pixel-border-sm text-[10px] font-bold text-sky-500 hover:bg-sky-100 transition-all cursor-default hover:scale-105"
                  >
                    {{ p.name }}
                  </span>
                  <span
                    v-if="nitStatus.plugins.length > 8"
                    class="px-2 py-1 text-xs text-slate-400 font-medium italic"
                    >...及其他 {{ nitStatus.plugins.length - 8 }} 个</span
                  >
                </div>
              </PCard>

              <!-- 功能开关卡片组 -->
              <div class="space-y-4">
                <!-- 轻量模式 -->
                <PCard pixel class="group/switch">
                  <div class="flex items-center justify-between">
                    <div class="flex items-center gap-4">
                      <div
                        class="text-2xl group-hover/switch:scale-110 transition-transform duration-300"
                      >
                        <PixelIcon name="leaf" size="lg" />
                      </div>
                      <div>
                        <div class="font-bold text-slate-800 flex items-center gap-2">
                          轻量聊天模式
                          <span class="text-[10px] text-sky-400/60 font-mono font-normal"
                            >Lightweight</span
                          >
                        </div>
                        <div class="text-sm text-slate-500 mt-0.5 leading-relaxed">
                          开启后，将禁用大部分高级工具以节省资源。仅保留视觉感知、记忆管理和基础管理功能。
                        </div>
                      </div>
                    </div>
                    <PSwitch
                      v-model="isLightweightEnabled"
                      :loading="isTogglingLightweight"
                      @update:model-value="toggleLightweight"
                    />
                  </div>
                </PCard>

                <!-- 视觉感应 -->
                <PCard pixel class="group/switch">
                  <div class="flex items-center justify-between">
                    <div class="flex items-center gap-4">
                      <div
                        class="text-2xl group-hover/switch:scale-110 transition-transform duration-300"
                      >
                        <PixelIcon name="crystal" size="lg" />
                      </div>
                      <div>
                        <div class="font-bold text-slate-800 flex items-center gap-2">
                          主动视觉感应
                          <span class="text-[10px] text-sky-400/60 font-mono font-normal"
                            >AuraVision</span
                          >
                        </div>
                        <div class="text-sm text-slate-500 mt-0.5 leading-relaxed">
                          开启后，{{ activeAgent?.name || 'Pero' }}
                          将通过屏幕主动感知你的存在并触发互动。
                        </div>
                      </div>
                    </div>
                    <PSwitch
                      v-model="isAuraVisionEnabled"
                      :loading="isTogglingAuraVision"
                      @update:model-value="toggleAuraVision"
                    />
                  </div>
                </PCard>

                <!-- 陪伴模式 -->
                <PCard
                  pixel
                  class="group/switch"
                  :class="{ 'opacity-50 pointer-events-none': !isLightweightEnabled }"
                >
                  <div class="flex items-center justify-between">
                    <div class="flex items-center gap-4">
                      <div
                        class="text-2xl group-hover/switch:scale-110 transition-transform duration-300"
                      >
                        <PixelIcon name="eye" size="lg" />
                      </div>
                      <div>
                        <div class="font-bold text-slate-800 flex items-center gap-2">
                          智能陪伴模式
                          <span class="text-[10px] text-sky-400/60 font-mono font-normal"
                            >Companion</span
                          >
                        </div>
                        <div class="text-sm text-slate-500 mt-0.5 leading-relaxed">
                          {{ activeAgent?.name || 'Pero' }} 将自动观察你的屏幕动态并进行互动。
                          <span
                            v-if="!isLightweightEnabled"
                            class="text-rose-500 font-bold ml-2 text-xs"
                            >(需要先开启“轻量模式”)</span
                          >
                        </div>
                      </div>
                    </div>
                    <PSwitch
                      v-model="isCompanionEnabled"
                      :loading="isTogglingCompanion"
                      :disabled="!isLightweightEnabled || !isCurrentModelVisionEnabled"
                      @update:model-value="toggleCompanion"
                    />
                  </div>
                </PCard>
              </div>

              <!-- 记忆系统配置 -->
              <PCard pixel>
                <template #header>
                  <div class="flex items-center justify-between">
                    <div class="flex items-center gap-3">
                      <div class="text-2xl text-sky-500">
                        <PixelIcon name="brain" size="lg" />
                      </div>
                      <div>
                        <div class="font-bold text-slate-800 flex items-center gap-2 text-lg">
                          记忆系统配置
                          <span class="text-xs font-normal text-slate-400 font-mono"
                            >Memory System</span
                          >
                          <span class="text-xs animate-pulse">
                            <PixelIcon name="sparkle" size="xs" />
                          </span>
                        </div>
                        <div class="text-sm text-slate-500 font-medium flex items-center gap-1.5">
                          配置不同模式下的记忆召回与上下文长度 <PixelIcon name="paw" size="xs" />
                        </div>
                      </div>
                    </div>
                    <PButton
                      variant="primary"
                      size="sm"
                      :loading="isSavingMemoryConfig"
                      class="shadow-lg shadow-sky-300/30"
                      @click="saveMemoryConfig"
                      >保存配置</PButton
                    >
                  </div>
                </template>

                <!-- 模式切换 (Mode Tabs) -->
                <div
                  class="border-b border-sky-100 flex gap-8 mb-8 overflow-x-auto pb-1 custom-scrollbar group/tabs"
                >
                  <button
                    v-for="tab in [
                      { id: 'desktop', label: '桌面模式', icon: 'desktop' },
                      { id: 'work', label: '工作模式', icon: 'desktop' },
                      { id: 'social', label: '社交模式', icon: 'chat' }
                    ]"
                    :key="tab.id"
                    class="pb-4 text-sm font-bold transition-all relative active:scale-95 flex items-center gap-2 group/tab hover-pixel-bounce"
                    :class="
                      activeMemoryTab === tab.id
                        ? 'text-sky-600'
                        : 'text-slate-500 hover:text-sky-500'
                    "
                    @click="activeMemoryTab = tab.id"
                  >
                    <span class="relative z-10 flex items-center gap-2">
                      <span class="group-hover/tab:scale-125 transition-transform duration-300"
                        ><PixelIcon :name="tab.icon" size="sm"
                      /></span>
                      {{ tab.label }}
                      <span v-if="activeMemoryTab === tab.id" class="animate-bounce"
                        ><PixelIcon name="sparkle" size="xs"
                      /></span>
                    </span>

                    <!-- 🐾 Hover indicator -->
                    <span
                      class="absolute -top-1 left-1/2 -translate-x-1/2 opacity-0 group-hover/tab:opacity-100 transition-all duration-300 -translate-y-2 group-hover/tab:translate-y-0 pointer-events-none"
                    >
                      <PixelIcon name="paw" size="xs" />
                    </span>

                    <div
                      v-if="activeMemoryTab === tab.id"
                      class="absolute bottom-0 left-0 w-full h-1 bg-gradient-to-r from-sky-500 to-sky-300 rounded-full shadow-[0_0_12px_rgba(56,189,248,0.3)]"
                    ></div>
                  </button>
                </div>

                <!-- Tab Content -->
                <div class="space-y-6">
                  <!-- 桌面模式 (Desktop Mode) -->
                  <div v-if="activeMemoryTab === 'desktop'" class="space-y-6">
                    <div class="grid grid-cols-1 md:grid-cols-2 gap-8">
                      <div
                        class="bg-sky-50/50 p-6 pixel-border-sky transition-all duration-300 group/mconfig hover:pixel-border-pink"
                      >
                        <div class="flex justify-between items-center mb-4">
                          <label class="text-sm font-bold text-slate-700 flex items-center gap-2">
                            <span
                              class="w-2 h-2 rounded-full bg-sky-500 group-hover/mconfig:animate-pulse"
                            ></span>
                            短期记忆上下文
                            <span class="text-[10px] text-sky-400 font-bold font-mono"
                              >Context</span
                            >
                          </label>
                          <span
                            class="px-2 py-0.5 bg-sky-100 text-sky-600 rounded-lg text-xs font-mono font-bold border border-sky-200"
                            >{{ memoryConfig.modes.desktop.context_limit }}</span
                          >
                        </div>
                        <PSlider
                          v-model="memoryConfig.modes.desktop.context_limit"
                          :min="5"
                          :max="50"
                        />
                        <div
                          class="mt-4 text-xs text-slate-500 font-medium flex items-start gap-2 bg-sky-100/30 p-3 rounded-xl border border-sky-100/50"
                        >
                          <span class="text-base group-hover/mconfig:rotate-12 transition-transform"
                            ><PixelIcon name="thought" size="sm"
                          /></span>
                          <p class="leading-relaxed">
                            最近对话的条数，用于维持对话连贯性。建议设置在 10-20 条左右。<PixelIcon
                              name="sparkle"
                              size="xs"
                            />
                          </p>
                        </div>
                      </div>
                      <div
                        class="bg-sky-50/50 p-6 pixel-border-sky transition-all duration-300 group/mconfig hover:pixel-border-pink"
                      >
                        <div class="flex justify-between items-center mb-4">
                          <label class="text-sm font-bold text-slate-700 flex items-center gap-2">
                            <span
                              class="w-2 h-2 rounded-full bg-sky-500 group-hover/mconfig:animate-pulse"
                            ></span>
                            RAG 召回数量
                            <span class="text-[10px] text-slate-400 font-bold">Retrieval</span>
                          </label>
                          <span
                            class="px-2 py-0.5 bg-sky-500/10 text-sky-400 rounded-lg text-xs font-mono font-bold"
                            >{{ memoryConfig.modes.desktop.rag_limit }}</span
                          >
                        </div>
                        <PSlider
                          v-model="memoryConfig.modes.desktop.rag_limit"
                          :min="0"
                          :max="30"
                        />
                        <div
                          class="mt-4 text-xs text-slate-500 flex items-start gap-2 bg-sky-50/50 p-3 rounded-xl border border-sky-100/50"
                        >
                          <span class="text-base group-hover/mconfig:scale-110 transition-transform"
                            ><PixelIcon name="book" size="sm"
                          /></span>
                          <p class="leading-relaxed">
                            从长期记忆库中检索的相关记忆条数。召回越多，回复内容越精准。<PixelIcon
                              name="paw"
                              size="xs"
                            />
                          </p>
                        </div>
                      </div>
                    </div>
                  </div>

                  <!-- 工作模式 (Work Mode) -->
                  <div v-if="activeMemoryTab === 'work'" class="space-y-6">
                    <div class="grid grid-cols-1 md:grid-cols-2 gap-8">
                      <div
                        class="bg-sky-50/50 p-5 pixel-border-sky transition-all duration-300 group/mconfig hover:pixel-border-pink"
                      >
                        <div class="flex justify-between items-center mb-4">
                          <label class="text-sm font-bold text-slate-700 flex items-center gap-2">
                            <span
                              class="w-2 h-2 rounded-full bg-sky-500 group-hover/mconfig:animate-pulse"
                            ></span>
                            短期记忆上下文
                            <span class="text-[10px] text-slate-400 font-bold">Context</span>
                          </label>
                          <span
                            class="px-2 py-0.5 bg-sky-100 text-sky-600 rounded-lg text-xs font-mono font-bold border border-sky-200"
                            >{{ memoryConfig.modes.work.context_limit }}</span
                          >
                        </div>
                        <PSlider
                          v-model="memoryConfig.modes.work.context_limit"
                          :min="10"
                          :max="100"
                        />
                        <div
                          class="mt-4 text-xs text-slate-500 font-medium flex items-start gap-2 bg-sky-100/30 p-3 rounded-xl border border-sky-100/50"
                        >
                          <span class="text-base group-hover/mconfig:rotate-12 transition-transform"
                            ><PixelIcon name="desktop" size="sm"
                          /></span>
                          <p class="leading-relaxed">
                            工作模式通常需要更长的上下文以理解代码或任务背景。建议设置在 30-50
                            条左右。<PixelIcon name="sparkle" size="xs" />
                          </p>
                        </div>
                      </div>
                      <div
                        class="bg-sky-50/50 p-5 pixel-border-sky transition-all duration-300 group/mconfig hover:pixel-border-pink"
                      >
                        <div class="flex justify-between items-center mb-4">
                          <label class="text-sm font-bold text-slate-700 flex items-center gap-2">
                            <span
                              class="w-2 h-2 rounded-full bg-sky-500 group-hover/mconfig:animate-pulse"
                            ></span>
                            RAG 召回数量
                            <span class="text-[10px] text-slate-400 font-bold">Retrieval</span>
                          </label>
                          <span
                            class="px-2 py-0.5 bg-sky-100 text-sky-600 rounded-lg text-xs font-mono font-bold border border-sky-200"
                            >{{ memoryConfig.modes.work.rag_limit }}</span
                          >
                        </div>
                        <PSlider v-model="memoryConfig.modes.work.rag_limit" :min="0" :max="50" />
                        <div
                          class="mt-4 text-xs text-slate-500 font-medium flex items-start gap-2 bg-sky-100/30 p-3 rounded-xl border border-sky-100/50"
                        >
                          <span class="text-base group-hover/mconfig:scale-110 transition-transform"
                            ><PixelIcon name="search" size="sm"
                          /></span>
                          <p class="leading-relaxed">
                            从长期记忆库中检索的相关记忆条数。工作模式建议召回更多事实。<PixelIcon
                              name="paw"
                              size="xs"
                            />
                          </p>
                        </div>
                      </div>
                    </div>
                  </div>

                  <!-- 社交模式 (Social Mode) -->
                  <div v-if="activeMemoryTab === 'social'" class="space-y-6">
                    <div class="grid grid-cols-1 md:grid-cols-2 gap-8">
                      <div
                        class="bg-sky-50/50 p-5 rounded-[2rem] border border-sky-100/50 hover:border-sky-300 transition-all duration-300 group/mconfig shadow-sm"
                      >
                        <div class="flex justify-between items-center mb-4">
                          <label class="text-sm font-bold text-slate-700 flex items-center gap-2">
                            <span
                              class="w-2 h-2 rounded-full bg-sky-500 group-hover/mconfig:animate-pulse"
                            ></span>
                            决策上下文长度
                            <span class="text-[10px] text-slate-400 font-bold">Context</span>
                          </label>
                          <span
                            class="px-2 py-0.5 bg-sky-100 text-sky-600 rounded-lg text-xs font-mono font-bold border border-sky-200"
                            >{{ memoryConfig.modes.social.context_limit }}</span
                          >
                        </div>
                        <PSlider
                          v-model="memoryConfig.modes.social.context_limit"
                          :min="20"
                          :max="200"
                          :step="10"
                        />
                        <div
                          class="mt-4 text-xs text-slate-500 font-medium flex items-start gap-2 bg-sky-100/30 p-3 rounded-xl border border-sky-100/50"
                        >
                          <span class="text-base group-hover/mconfig:rotate-12 transition-transform"
                            ><PixelIcon name="thought" size="sm"
                          /></span>
                          <p class="leading-relaxed">
                            “秘书”决策和主动发言时参考的消息数量。社交模式需要更全面的视野。<PixelIcon
                              name="sparkle"
                              size="xs"
                            />
                          </p>
                        </div>
                      </div>
                      <div
                        class="bg-sky-50/50 p-5 rounded-[2rem] border border-sky-100/50 hover:border-sky-300 transition-all duration-300 group/mconfig shadow-sm"
                      >
                        <div class="flex justify-between items-center mb-4">
                          <label class="text-sm font-bold text-slate-700 flex items-center gap-2">
                            <span
                              class="w-2 h-2 rounded-full bg-sky-500 group-hover/mconfig:animate-pulse"
                            ></span>
                            RAG 召回数量
                            <span class="text-[10px] text-slate-400 font-bold">Retrieval</span>
                          </label>
                          <span
                            class="px-2 py-0.5 bg-sky-100 text-sky-600 rounded-lg text-xs font-mono font-bold border border-sky-200"
                            >{{ memoryConfig.modes.social.rag_limit }}</span
                          >
                        </div>
                        <PSlider v-model="memoryConfig.modes.social.rag_limit" :min="0" :max="30" />
                        <div
                          class="mt-4 text-xs text-slate-500 font-medium flex items-start gap-2 bg-sky-100/30 p-3 rounded-xl border border-sky-100/50"
                        >
                          <span class="text-base group-hover/mconfig:scale-110 transition-transform"
                            ><PixelIcon name="heart" size="sm"
                          /></span>
                          <p class="leading-relaxed">
                            从长期记忆库中检索的相关记忆条数。用于在群聊中识别熟人和往事。<PixelIcon
                              name="paw"
                              size="xs"
                            />
                          </p>
                        </div>
                      </div>
                    </div>

                    <div class="border-t border-sky-100 pt-8">
                      <h4
                        class="text-xs font-bold text-slate-500 mb-6 uppercase tracking-widest flex items-center gap-2"
                      >
                        <span class="w-1.5 h-1.5 rounded-full bg-amber-500 animate-ping"></span>
                        高级配置 <span class="opacity-50 font-normal">Advanced Settings</span>
                      </h4>
                      <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
                        <div
                          class="bg-white/60 p-5 rounded-3xl border border-sky-100 hover:border-sky-300 transition-all group/adv shadow-sm"
                        >
                          <label
                            class="text-sm font-bold text-slate-700 block mb-3 flex items-center gap-2"
                          >
                            图片感知上限
                            <span
                              class="text-[10px] text-slate-400 font-normal opacity-0 group-hover/adv:opacity-100 transition-opacity"
                              ># Image Limit</span
                            >
                          </label>
                          <PInputNumber
                            v-model="memoryConfig.modes.social.advanced.image_limit"
                            :min="0"
                            :max="4"
                            class="!bg-sky-50/50 !border-sky-100 focus:!border-sky-300"
                          />
                          <div class="mt-3 text-[11px] text-slate-500 font-medium leading-relaxed">
                            每次处理消息时最多查看的最近图片数量。<PixelIcon name="eye" size="xs" />
                          </div>
                        </div>
                        <div
                          class="bg-white/60 p-5 rounded-3xl border border-sky-100 hover:border-sky-300 transition-all group/adv shadow-sm"
                        >
                          <label
                            class="text-sm font-bold text-slate-700 block mb-3 flex items-center gap-2"
                          >
                            跨会话感知人数
                            <span
                              class="text-[10px] text-slate-400 font-normal opacity-0 group-hover/adv:opacity-100 transition-opacity"
                              ># User Count</span
                            >
                          </label>
                          <PInputNumber
                            v-model="memoryConfig.modes.social.advanced.cross_context_users"
                            :min="0"
                            :max="10"
                            class="!bg-sky-50/50 !border-sky-100 focus:!border-sky-300"
                          />
                          <div class="mt-3 text-[11px] text-slate-500 font-medium leading-relaxed">
                            在群聊中同时关注的相关活跃用户数量。<PixelIcon name="users" size="xs" />
                          </div>
                        </div>
                        <div
                          class="bg-white/60 p-5 rounded-3xl border border-sky-100 hover:border-sky-300 transition-all group/adv shadow-sm"
                        >
                          <label
                            class="text-sm font-bold text-slate-700 block mb-3 flex items-center gap-2"
                          >
                            跨会话历史深度
                            <span
                              class="text-[10px] text-slate-400 font-normal opacity-0 group-hover/adv:opacity-100 transition-opacity"
                              ># History Depth</span
                            >
                          </label>
                          <PInputNumber
                            v-model="memoryConfig.modes.social.advanced.cross_context_history"
                            :min="0"
                            :max="50"
                            class="!bg-sky-50/50 !border-sky-100 focus:!border-sky-300"
                          />
                          <div class="mt-3 text-[11px] text-slate-500 font-medium leading-relaxed">
                            为每个相关用户/群组拉取的背景消息条数。<PixelIcon
                              name="book"
                              size="xs"
                            />
                          </div>
                        </div>
                      </div>
                      <div
                        class="mt-6 p-4 bg-sky-50/80 border border-sky-100 rounded-[1.5rem] flex items-start gap-4 backdrop-blur-md group/notice shadow-sm"
                      >
                        <div
                          class="p-2 bg-sky-100 rounded-xl text-sky-500 group-hover/notice:scale-110 transition-transform"
                        >
                          <PixelIcon name="alert" size="md" />
                        </div>
                        <p class="text-[11px] text-slate-500 font-medium leading-relaxed py-1">
                          注意：调高高级配置参数可能会显著增加
                          <span class="text-sky-600 font-bold">Token 消耗</span>
                          及响应延迟，建议根据实际性能情况进行微调哦~
                          <PixelIcon name="sparkle" size="xs" /> <PixelIcon name="paw" size="xs" />
                        </p>
                      </div>
                    </div>
                  </div>
                </div>
              </PCard>
            </div>

            <!-- 2. 对话日志 (重构版) -->
            <div
              v-else-if="currentTab === 'logs'"
              key="logs"
              class="h-full flex flex-col overflow-hidden"
            >
              <!-- Toolbar -->
              <div class="p-6 pb-0 flex-none">
                <PCard
                  glass
                  soft3d
                  overflow-visible
                  class="mb-4 !p-4 rounded-[2rem] relative group/toolbar z-30"
                >
                  <!-- 背景装饰 ✨ -->
                  <div
                    class="absolute -right-20 -top-20 w-40 h-40 bg-sky-400/10 blur-[60px] rounded-full pointer-events-none group-hover/toolbar:bg-sky-400/20 transition-all duration-1000"
                  ></div>
                  <div
                    class="absolute -left-10 -bottom-10 w-32 h-32 bg-sky-300/5 blur-[50px] rounded-full pointer-events-none group-hover/toolbar:bg-sky-300/15 transition-all duration-1000 delay-150"
                  ></div>

                  <div class="flex flex-wrap items-end gap-5 relative z-10">
                    <!-- Agent Selector -->
                    <div class="flex flex-col gap-2 min-w-[150px]">
                      <label
                        class="text-[11px] font-bold text-slate-500 flex items-center gap-1.5 ml-1 uppercase tracking-wider"
                      >
                        <span class="w-1.5 h-1.5 rounded-full bg-sky-500 animate-pulse"></span> 角色
                        <span class="opacity-50 font-normal">Agent</span>
                      </label>
                      <div class="relative group/agent">
                        <button
                          class="w-full flex items-center justify-between px-4 py-2.5 bg-white hover:bg-sky-50 border border-sky-100 rounded-2xl text-sm transition-all active:scale-95 shadow-lg shadow-black/30 backdrop-blur-md group/btn"
                          :class="isSwitchingAgent ? 'opacity-50 cursor-not-allowed' : ''"
                        >
                          <span class="text-sky-600 font-bold flex items-center gap-2">
                            <span
                              class="text-xs opacity-0 group-hover/btn:opacity-100 transition-all duration-300 -translate-x-2 group-hover:translate-x-0"
                              ><PixelIcon name="paw" size="xs"
                            /></span>
                            {{ activeAgent?.name || '未知' }}
                            <span
                              class="text-[10px] font-normal opacity-40 group-hover:opacity-100 transition-opacity"
                              ><PixelIcon name="sparkle" size="xs"
                            /></span>
                          </span>
                          <PixelIcon
                            name="chevron-down"
                            size="xs"
                            class="text-slate-400 group-hover/agent:rotate-180 transition-transform duration-500"
                          />
                        </button>
                        <!-- Dropdown -->
                        <div
                          class="absolute left-0 top-full mt-3 w-full py-2 bg-white/70 backdrop-blur-2xl border border-sky-100 rounded-2xl shadow-2xl shadow-sky-200/40 opacity-0 invisible group-hover/agent:opacity-100 group-hover/agent:visible transition-all duration-500 z-50 transform origin-top scale-90 group-hover/agent:scale-100 ring-1 ring-sky-100/5"
                        >
                          <button
                            v-for="agent in availableAgents"
                            :key="agent.id"
                            class="w-full text-left px-4 py-2.5 text-sm hover:bg-sky-50 transition-all flex items-center justify-between group/item"
                            :class="{
                              'text-sky-600 font-bold bg-sky-50': agent.id === activeAgent?.id,
                              'text-slate-500': agent.id !== activeAgent?.id
                            }"
                            :disabled="agent.id === activeAgent?.id || !agent.is_enabled"
                            @click="switchAgent(agent.id)"
                          >
                            <span
                              class="group-hover/item:translate-x-1.5 transition-transform flex items-center gap-2"
                            >
                              <span v-if="agent.id === activeAgent?.id" class="text-xs"
                                ><PixelIcon name="paw" size="xs"
                              /></span>
                              {{ agent.name }}
                            </span>
                            <div class="flex items-center gap-2">
                              <span
                                v-if="!agent.is_enabled"
                                class="text-[10px] text-slate-500 font-normal bg-sky-100 px-1.5 py-0.5 rounded-lg border border-sky-200"
                                >禁用</span
                              >
                              <span
                                v-if="agent.id === activeAgent?.id"
                                class="text-sky-400 drop-shadow-[0_0_8px_rgba(14,165,233,0.5)]"
                                ><PixelIcon name="heart" size="xs"
                              /></span>
                            </div>
                          </button>
                        </div>
                      </div>
                    </div>

                    <!-- Source -->
                    <div class="flex flex-col gap-2 w-[140px] relative z-40">
                      <label
                        class="text-[11px] font-bold text-slate-500 flex items-center gap-1.5 ml-1 uppercase tracking-wider"
                      >
                        <span class="w-1.5 h-1.5 rounded-full bg-sky-500"></span> 来源
                        <span class="opacity-50 font-normal">Source</span>
                      </label>
                      <PSelect
                        v-model="selectedSource"
                        :options="[
                          { label: '全部来源', value: 'all', icon: 'sparkle' },
                          { label: 'Desktop', value: 'desktop', icon: 'desktop' },
                          { label: 'Mobile', value: 'mobile', icon: 'mobile' }
                        ]"
                        class="!rounded-2xl shadow-lg shadow-black/30 backdrop-blur-md"
                        size="md"
                        @change="fetchLogs"
                      >
                        <template #option="{ option }">
                          <div class="flex items-center gap-2">
                            <PixelIcon
                              v-if="option.icon"
                              :name="option.icon"
                              size="xs"
                              class="opacity-70"
                            />
                            <span>{{ option.label }}</span>
                          </div>
                        </template>
                      </PSelect>
                    </div>

                    <!-- Session -->
                    <div class="flex flex-col gap-2 w-[160px] relative z-30">
                      <label
                        class="text-[11px] font-bold text-slate-500 flex items-center gap-1.5 ml-1 uppercase tracking-wider"
                      >
                        <span class="w-1.5 h-1.5 rounded-full bg-sky-500"></span> 会话
                        <span class="opacity-50 font-normal">Session</span>
                      </label>
                      <PSelect
                        v-model="selectedSessionId"
                        :options="[
                          { label: '全部会话', value: 'all', icon: 'chat' },
                          { label: '默认会话 (Text)', value: 'default', icon: 'thought' },
                          { label: '语音会话 (Voice)', value: 'voice_session', icon: 'sparkle' }
                        ]"
                        class="!rounded-2xl shadow-lg shadow-black/30 backdrop-blur-md"
                        size="md"
                        @change="fetchLogs"
                      >
                        <template #option="{ option }">
                          <div class="flex items-center gap-2">
                            <PixelIcon
                              v-if="option.icon"
                              :name="option.icon"
                              size="xs"
                              class="opacity-70"
                            />
                            <span>{{ option.label }}</span>
                          </div>
                        </template>
                      </PSelect>
                    </div>

                    <!-- Date -->
                    <div class="flex flex-col gap-2 w-[160px] relative z-20">
                      <label
                        class="text-[11px] font-bold text-slate-500 flex items-center gap-1.5 ml-1 uppercase tracking-wider"
                      >
                        <span class="w-1.5 h-1.5 rounded-full bg-sky-500"></span> 日期
                        <span class="opacity-50 font-normal">Date</span>
                      </label>
                      <div class="relative group/datepicker">
                        <PDatePicker
                          v-model="selectedDate"
                          placeholder="选择日期"
                          class="!rounded-2xl shadow-lg shadow-black/30 backdrop-blur-md"
                          @update:model-value="fetchLogs"
                        />
                        <div
                          class="absolute right-4 top-1/2 -translate-y-1/2 pointer-events-none opacity-50 group-hover/datepicker:opacity-100 transition-opacity"
                        >
                          <PixelIcon name="calendar" size="xs" />
                        </div>
                      </div>
                    </div>

                    <!-- Sort -->
                    <div class="flex flex-col gap-2 w-[120px] relative z-10">
                      <label
                        class="text-[11px] font-bold text-slate-500 flex items-center gap-1.5 ml-1 uppercase tracking-wider"
                      >
                        <span class="w-1.5 h-1.5 rounded-full bg-sky-500"></span> 排序
                        <span class="opacity-50 font-normal">Sort</span>
                      </label>
                      <PSelect
                        v-model="selectedSort"
                        :options="[
                          { label: '最新在前', value: 'desc', icon: 'hourglass' },
                          { label: '最早在前', value: 'asc', icon: 'clock' }
                        ]"
                        class="!rounded-2xl shadow-lg shadow-black/30 backdrop-blur-md"
                        size="md"
                        @change="fetchLogs"
                      >
                        <template #option="{ option }">
                          <div class="flex items-center gap-2 text-xs">
                            <PixelIcon
                              v-if="option.icon"
                              :name="option.icon"
                              size="xs"
                              class="opacity-70"
                            />
                            <span>{{ option.label }}</span>
                          </div>
                        </template>
                      </PSelect>
                    </div>

                    <!-- Refresh -->
                    <div class="pb-0.5 ml-auto">
                      <PButton
                        variant="secondary"
                        :loading="isLogsFetching"
                        class="!rounded-2xl shadow-xl shadow-black/30 hover:scale-110 active:scale-95 transition-all px-6 group/refresh"
                        @click="fetchLogs"
                      >
                        <span
                          class="group-hover/refresh:rotate-180 transition-transform duration-700"
                          >刷新</span
                        >
                        <PixelIcon name="refresh" size="xs" />
                      </PButton>
                    </div>
                  </div>
                </PCard>
              </div>

              <!-- Chat List -->
              <div class="flex-1 overflow-y-auto px-6 pb-6 custom-scrollbar">
                <PEmpty v-if="logs.length === 0">
                  <template #description>
                    <div class="flex items-center gap-2 justify-center">
                      暂无对话记录 <PixelIcon name="thought" size="xs" />
                    </div>
                  </template>
                </PEmpty>

                <div v-else class="space-y-8 max-w-4xl mx-auto pt-4">
                  <div
                    v-for="log in logs"
                    :key="log.id"
                    class="flex gap-4 group"
                    :class="log.role === 'user' ? 'flex-row-reverse' : ''"
                  >
                    <!-- Avatar -->
                    <div
                      class="flex-none w-14 h-14 rounded-2xl flex items-center justify-center text-lg shadow-xl border transition-all duration-500 group-hover:scale-110 group-hover:rotate-6 group-hover:shadow-sky-200/50 relative overflow-hidden"
                      :class="
                        log.role === 'user'
                          ? 'bg-sky-50 text-sky-600 border-sky-200 shadow-sky-100/30'
                          : 'bg-white text-purple-500 border-purple-100 shadow-purple-100/20'
                      "
                    >
                      <div
                        class="absolute inset-0 bg-gradient-to-tr from-white/20 to-transparent"
                      ></div>
                      <PixelIcon
                        v-if="log.role === 'user'"
                        name="user"
                        size="xl"
                        class="relative z-10"
                      />
                      <PixelIcon v-else name="robot" size="xl" class="relative z-10" />
                      <!-- 🐾 小脚印装饰 -->
                      <div
                        class="absolute -bottom-1 -right-1 text-[10px] opacity-0 group-hover:opacity-100 transition-opacity duration-500 z-20"
                      >
                        <PixelIcon name="paw" size="xs" animation="bounce" />
                      </div>
                    </div>

                    <!-- Bubble Content -->
                    <div
                      class="flex flex-col max-w-[85%] relative"
                      :class="log.role === 'user' ? 'items-end' : 'items-start'"
                    >
                      <!-- Meta -->
                      <div
                        class="flex items-center gap-2 mb-2 text-[11px] text-slate-400 px-3 font-bold"
                      >
                        <span
                          class="tracking-widest uppercase flex items-center gap-1.5"
                          :class="log.role === 'user' ? 'text-sky-600/70' : 'text-purple-500'"
                        >
                          <PixelIcon
                            v-if="log.role !== 'user'"
                            name="sparkle"
                            size="xs"
                            animation="spin"
                          />
                          {{ log.role === 'user' ? '主人' : activeAgent?.name || 'Pero' }}
                          <PixelIcon
                            v-if="log.role === 'user'"
                            name="heart"
                            size="xs"
                            animation="pulse"
                          />
                        </span>
                        <span class="opacity-40 font-mono text-[9px]">{{ log.displayTime }}</span>

                        <!-- Tags -->
                        <div class="flex items-center gap-2">
                          <PTooltip
                            v-if="log.sentiment && log.sentiment !== 'neutral'"
                            :content="`情感: ${getSentimentLabel(log.sentiment)}`"
                          >
                            <span
                              class="px-2.5 py-0.5 rounded-full bg-sky-50 text-sky-600 border border-sky-100 shadow-sm backdrop-blur-md flex items-center gap-1.5 hover:scale-105 transition-transform"
                            >
                              <PixelIcon :name="getSentimentEmoji(log.sentiment)" size="xs" />
                              <span class="text-[10px] font-bold">{{
                                getSentimentLabel(log.sentiment)
                              }}</span>
                            </span>
                          </PTooltip>
                          <span
                            v-if="log.importance > 1"
                            class="px-2.5 py-0.5 rounded-full bg-amber-50 text-amber-600 font-bold border border-amber-100 shadow-sm backdrop-blur-md flex items-center gap-1 hover:scale-105 transition-transform"
                          >
                            <PixelIcon name="star" size="xs" />
                            {{ log.importance }}
                          </span>
                          <PTooltip
                            v-if="log.metadata?.memory_extracted || log.memory_id"
                            content="已提取记忆"
                          >
                            <span
                              class="px-2.5 py-0.5 rounded-full bg-sky-50 text-sky-500 border border-sky-100 shadow-sm flex items-center gap-1.5 backdrop-blur-md hover:scale-105 transition-transform"
                            >
                              <PixelIcon name="brain" size="xs" />
                              <span class="text-[10px] font-bold flex items-center gap-1"
                                >已记下 <PixelIcon name="paw" size="xs"
                              /></span>
                            </span>
                          </PTooltip>
                          <span
                            v-if="log.analysis_status === 'processing'"
                            class="px-2.5 py-0.5 rounded-full bg-sky-50 text-sky-500 animate-pulse border border-sky-100 shadow-sm backdrop-blur-md"
                          >
                            <PixelIcon name="refresh" size="xs" animation="spin" />
                          </span>
                          <PTooltip
                            v-if="log.analysis_status === 'failed'"
                            :content="log.last_error"
                          >
                            <span
                              class="px-2.5 py-0.5 rounded-full bg-rose-50 text-rose-500 cursor-help border border-rose-100 shadow-sm backdrop-blur-md"
                            >
                              <PixelIcon name="alert" size="xs" />
                            </span>
                          </PTooltip>
                        </div>
                      </div>

                      <!-- Bubble -->
                      <div
                        class="relative px-7 py-5 rounded-[2.5rem] text-[14.5px] leading-relaxed shadow-xl transition-all duration-500 border group/bubble backdrop-blur-xl"
                        :class="[
                          log.role === 'user'
                            ? 'bg-sky-50/80 text-slate-700 rounded-tr-none border-sky-100 hover:border-sky-300 hover:bg-sky-100/90 shadow-sky-100/30'
                            : 'bg-white/80 text-slate-700 rounded-tl-none border-purple-100 hover:border-purple-300 hover:shadow-purple-100/50 shadow-purple-100/20',
                          editingLogId === log.id ? 'w-full min-w-[400px]' : ''
                        ]"
                      >
                        <!-- Floating Icons for Bot ✨ -->
                        <div
                          v-if="log.role !== 'user' && !editingLogId"
                          class="absolute -right-5 -top-5 opacity-0 group-hover/bubble:opacity-100 transition-all duration-700 transform scale-0 group-hover/bubble:scale-125 rotate-12 group-hover/bubble:rotate-0 drop-shadow-[0_0_12px_rgba(192,132,252,0.4)] flex flex-col gap-1"
                        >
                          <PixelIcon name="sparkle" size="lg" animation="spin" />
                          <PixelIcon
                            name="heart"
                            size="xs"
                            animation="pulse"
                            class="text-pink-400 ml-2"
                          />
                        </div>

                        <!-- Floating Paw for User 🐾 -->
                        <div
                          v-if="log.role === 'user' && !editingLogId"
                          class="absolute -left-5 -top-5 opacity-0 group-hover/bubble:opacity-100 transition-all duration-700 transform scale-0 group-hover/bubble:scale-125 -rotate-12 group-hover/bubble:rotate-0 drop-shadow-[0_0_12px_rgba(14,165,233,0.3)]"
                        >
                          <PixelIcon name="paw" size="lg" animation="bounce" />
                        </div>

                        <!-- Edit Mode -->
                        <div v-if="editingLogId === log.id" class="space-y-4">
                          <PTextarea
                            v-model="editingContent"
                            :rows="4"
                            placeholder="编辑内容..."
                            class="!rounded-2xl border-sky-200 focus:border-sky-400 transition-all"
                          />
                          <div class="flex items-center gap-3 justify-end">
                            <PButton
                              size="sm"
                              variant="ghost"
                              class="rounded-xl"
                              @click="cancelLogEdit"
                              >取消</PButton
                            >
                            <PButton
                              size="sm"
                              variant="primary"
                              class="rounded-xl px-6"
                              @click="saveLogEdit(log.id)"
                              >保存 💭</PButton
                            >
                          </div>
                        </div>

                        <!-- Display Mode -->
                        <div v-else class="relative z-10">
                          <!-- Images -->
                          <div
                            v-if="log.images && log.images.length > 0"
                            class="flex flex-wrap gap-3 mb-3"
                          >
                            <div
                              v-for="(img, idx) in log.images"
                              :key="idx"
                              class="relative w-32 h-32 rounded-2xl overflow-hidden border border-sky-100 cursor-zoom-in group/img shadow-lg shadow-sky-100/40 hover:scale-105 transition-transform duration-500"
                              @click="openImageViewer(log.images, idx)"
                            >
                              <img :src="img" class="w-full h-full object-cover" />
                              <div
                                class="absolute inset-0 bg-sky-500/20 opacity-0 group-hover/img:opacity-100 transition-opacity flex items-center justify-center backdrop-blur-[2px]"
                              >
                                <PixelIcon name="eye" size="lg" class="text-white drop-shadow-md" />
                              </div>
                            </div>
                          </div>

                          <!-- Text Content -->
                          <AsyncMarkdown
                            :content="formatLogContent(log.content)"
                            class="prose prose-sky prose-sm max-w-none"
                          />
                        </div>
                      </div>

                      <!-- Actions -->
                      <div
                        class="flex items-center gap-3 mt-2 opacity-0 group-hover:opacity-100 transition-all duration-300 px-2"
                      >
                        <PTooltip v-if="log.analysis_status === 'failed'" content="重试分析">
                          <button
                            class="p-1.5 text-amber-500 hover:bg-amber-500/15 rounded-xl transition-colors active:scale-90"
                            @click="retryLogAnalysis(log)"
                          >
                            <PixelIcon name="refresh" size="xs" />
                          </button>
                        </PTooltip>
                        <PTooltip content="编辑">
                          <button
                            class="p-1.5 text-slate-500 hover:text-sky-400 hover:bg-sky-500/15 rounded-xl transition-all active:scale-90"
                            @click="startLogEdit(log)"
                          >
                            <PixelIcon name="pencil" size="xs" />
                          </button>
                        </PTooltip>
                        <PTooltip content="调试信息">
                          <button
                            class="p-1.5 text-slate-500 hover:text-sky-400 hover:bg-sky-500/15 rounded-xl transition-all active:scale-90"
                            @click="openDebugDialog(log)"
                          >
                            <PixelIcon name="terminal" size="xs" />
                          </button>
                        </PTooltip>
                        <PTooltip content="删除">
                          <button
                            class="p-1.5 text-slate-500 hover:text-rose-400 hover:bg-rose-500/15 rounded-xl transition-all active:scale-90"
                            @click="deleteLog(log.id)"
                          >
                            <PixelIcon name="trash" size="xs" />
                          </button>
                        </PTooltip>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <!-- 3. 核心记忆 (重构版) -->
            <div
              v-else-if="currentTab === 'memories'"
              key="memories"
              class="h-full flex flex-col overflow-hidden"
            >
              <!-- Toolbar -->
              <div class="p-6 pb-0 flex-none">
                <PCard
                  glass
                  soft3d
                  variant="purple"
                  overflow-visible
                  class="mb-4 !p-5 rounded-[2rem] relative group/mtoolbar z-30"
                >
                  <!-- 背景装饰 ✨ -->
                  <div
                    class="absolute -right-20 -top-20 w-40 h-40 bg-purple-400/10 blur-[60px] rounded-full pointer-events-none group-hover/mtoolbar:bg-purple-400/20 transition-all duration-1000"
                  ></div>

                  <div class="flex flex-wrap items-end gap-5 relative z-10">
                    <!-- Agent Selector -->
                    <div class="flex flex-col gap-2 min-w-[160px]">
                      <label
                        class="text-[11px] font-bold text-slate-500 flex items-center gap-1.5 ml-1 uppercase tracking-wider"
                      >
                        <span class="w-1.5 h-1.5 rounded-full bg-purple-500 animate-pulse"></span>
                        角色
                        <span class="opacity-50 font-normal">Agent</span>
                      </label>
                      <div class="relative group/magent">
                        <button
                          class="w-full flex items-center justify-between px-4 py-2.5 bg-purple-50/50 hover:bg-purple-100/50 border border-purple-100/50 hover:border-purple-300 rounded-2xl text-sm transition-all active:scale-95 shadow-lg shadow-black/30 backdrop-blur-md group/mbtn hover-pixel-bounce"
                          :class="isSwitchingAgent ? 'opacity-50 cursor-not-allowed' : ''"
                        >
                          <span class="text-purple-600 font-bold flex items-center gap-2">
                            <span
                              class="text-xs opacity-0 group-hover/mbtn:opacity-100 transition-all duration-300 -translate-x-2 group-hover:translate-x-0"
                              ><PixelIcon name="paw" size="xs" animation="bounce"
                            /></span>
                            {{ activeAgent?.name || '未知' }}
                          </span>
                          <PixelIcon
                            name="chevron-down"
                            size="xs"
                            class="text-slate-400 group-hover/magent:rotate-180 transition-transform duration-500"
                          />
                        </button>
                        <div
                          class="absolute left-0 top-full mt-3 w-full py-2 bg-white/70 backdrop-blur-2xl border border-purple-100 rounded-2xl shadow-2xl shadow-purple-200/40 opacity-0 invisible group-hover/magent:opacity-100 group-hover/magent:visible transition-all duration-500 z-50 transform origin-top scale-90 group-hover/magent:scale-100 ring-1 ring-purple-100/5"
                        >
                          <button
                            v-for="agent in availableAgents"
                            :key="agent.id"
                            class="w-full text-left px-4 py-2.5 text-sm hover:bg-purple-50 transition-all flex items-center justify-between group/mitem"
                            :class="{
                              'text-purple-600 font-bold bg-purple-50':
                                agent.id === activeAgent?.id,
                              'text-slate-500': agent.id !== activeAgent?.id
                            }"
                            :disabled="agent.id === activeAgent?.id || !agent.is_enabled"
                            @click="switchAgent(agent.id)"
                          >
                            <span
                              class="group-hover/mitem:translate-x-1.5 transition-transform flex items-center gap-2"
                            >
                              <span v-if="agent.id === activeAgent?.id" class="text-xs"
                                ><PixelIcon name="paw" size="xs"
                              /></span>
                              {{ agent.name }}
                            </span>
                            <div class="flex items-center gap-2">
                              <span
                                v-if="!agent.is_enabled"
                                class="text-[10px] text-slate-400 font-bold bg-slate-50 px-1.5 py-0.5 rounded-lg border border-slate-200"
                                >禁用</span
                              >
                              <span v-if="agent.id === activeAgent?.id" class="text-purple-400"
                                ><PixelIcon name="heart" size="xs"
                              /></span>
                            </div>
                          </button>
                        </div>
                      </div>
                    </div>

                    <!-- Filter Type -->
                    <div class="flex flex-col gap-2 w-[160px]">
                      <label
                        class="text-[11px] font-bold text-slate-500 flex items-center gap-1.5 ml-1 uppercase tracking-wider"
                      >
                        <span class="w-1.5 h-1.5 rounded-full bg-purple-500"></span> 类型
                        <span class="opacity-50 font-normal">Type</span>
                      </label>
                      <PSelect
                        v-model="memoryFilterType"
                        :options="[
                          { label: '全部类型', value: '', icon: 'sparkle' },
                          { label: '记忆块 (Event)', value: 'event', icon: 'puzzle' },
                          { label: '事实 (Fact)', value: 'fact', icon: 'brain' },
                          { label: '誓言 (Promise)', value: 'promise', icon: 'handshake' },
                          { label: '偏好 (Preference)', value: 'preference', icon: 'heart' },
                          { label: '工作日志 (Log)', value: 'work_log', icon: 'pencil' },
                          { label: '归档 (Archived)', value: 'archived_event', icon: 'archive' }
                        ]"
                        size="md"
                        class="!rounded-2xl shadow-lg shadow-black/30 backdrop-blur-md"
                        @change="fetchMemories"
                      >
                        <template #option="{ option }">
                          <div class="flex items-center gap-2 text-xs">
                            <PixelIcon
                              v-if="option.icon"
                              :name="option.icon"
                              size="xs"
                              class="opacity-70"
                            />
                            <span>{{ option.label }}</span>
                          </div>
                        </template>
                      </PSelect>
                    </div>

                    <!-- Date Filter -->
                    <div class="flex flex-col gap-2 w-[160px]">
                      <label
                        class="text-[11px] font-bold text-slate-500 flex items-center gap-1.5 ml-1 uppercase tracking-wider"
                      >
                        <span class="w-1.5 h-1.5 rounded-full bg-purple-500"></span> 日期
                        <span class="opacity-50 font-normal">Date</span>
                      </label>
                      <div class="relative group/mdate">
                        <PDatePicker
                          v-model="memoryFilterDate"
                          placeholder="选择日期"
                          class="!rounded-2xl shadow-lg shadow-black/30 backdrop-blur-md"
                          @update:model-value="fetchMemories"
                        />
                        <div
                          class="absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none opacity-40 group-hover/mdate:opacity-100 transition-opacity"
                        >
                          <PixelIcon name="calendar" size="xs" />
                        </div>
                      </div>
                    </div>

                    <!-- View Mode -->
                    <div
                      class="flex bg-purple-50/50 p-1 rounded-2xl border border-purple-100 self-end h-[42px] items-center relative group/vmode shadow-lg shadow-black/30 backdrop-blur-md"
                    >
                      <!-- 🐾 Floating decoration -->
                      <div
                        class="absolute -top-6 left-1/2 -translate-x-1/2 text-[10px] opacity-0 group-hover/vmode:opacity-60 transition-all duration-500 translate-y-2 group-hover/vmode:translate-y-0"
                      >
                        <PixelIcon name="paw" size="xs" animation="bounce" />
                      </div>

                      <div
                        class="absolute h-[34px] bg-white border border-purple-200 rounded-xl transition-all duration-500 ease-out pointer-events-none shadow-sm shadow-purple-100/50"
                        :style="{
                          left: memoryViewMode === 'list' ? '4px' : '56px',
                          width: memoryViewMode === 'list' ? '48px' : '48px'
                        }"
                      ></div>
                      <PTooltip
                        v-for="mode in [
                          { id: 'list', icon: 'list', label: '列表' },
                          { id: 'graph', icon: 'chart', label: '图谱' }
                        ]"
                        :key="mode.id"
                        :content="mode.label"
                      >
                        <button
                          class="relative flex items-center justify-center w-12 py-1.5 rounded-xl text-xs font-medium transition-all z-10 hover:scale-110 active:scale-90 group/vbtn"
                          :class="
                            memoryViewMode === mode.id
                              ? 'text-purple-600 font-bold'
                              : 'text-slate-400 hover:text-purple-500'
                          "
                          @click="
                            () => {
                              memoryViewMode = mode.id
                              if (mode.id === 'graph') fetchMemoryGraph()
                            }
                          "
                        >
                          <PixelIcon
                            :name="mode.icon"
                            size="sm"
                            class="transition-transform duration-500 group-hover/vbtn:rotate-12"
                          />
                        </button>
                      </PTooltip>
                    </div>

                    <!-- Actions -->
                    <div class="flex items-center gap-3 pb-0.5 ml-auto">
                      <PTooltip content="清除无效连线">
                        <PButton
                          variant="danger"
                          size="sm"
                          :loading="isClearingEdges"
                          class="!rounded-xl flat-action-btn"
                          @click="clearOrphanedEdges"
                          ><div class="flex items-center gap-1.5">
                            <PixelIcon name="trash" size="xs" />清理
                          </div></PButton
                        >
                      </PTooltip>
                      <PTooltip content="扫描孤立记忆">
                        <PButton
                          variant="primary"
                          size="sm"
                          :loading="isScanningLonely"
                          class="!rounded-xl flat-action-btn"
                          @click="triggerScanLonely"
                          ><div class="flex items-center gap-1.5">
                            <PixelIcon name="search" size="xs" />扫描
                          </div></PButton
                        >
                      </PTooltip>
                      <PTooltip content="每日深度维护">
                        <PButton
                          variant="warning"
                          size="sm"
                          :loading="isRunningMaintenance"
                          class="!rounded-xl flat-action-btn"
                          @click="triggerMaintenance"
                          ><div class="flex items-center gap-1.5">
                            <PixelIcon name="settings" size="xs" />维护
                          </div></PButton
                        >
                      </PTooltip>
                      <PTooltip content="触发梦境联想">
                        <PButton
                          variant="success"
                          size="sm"
                          :loading="isDreaming"
                          class="!rounded-xl flat-action-btn"
                          @click="triggerDream"
                          ><div class="flex items-center gap-1.5">
                            <PixelIcon name="sparkle" size="xs" />梦境
                          </div></PButton
                        >
                      </PTooltip>
                    </div>
                  </div>

                  <!-- Tags -->
                  <div
                    v-if="topTags.length"
                    class="mt-5 flex items-center gap-3 overflow-x-auto pb-1.5 custom-scrollbar group/tags"
                  >
                    <span
                      class="text-[11px] font-bold text-slate-500 shrink-0 flex items-center gap-2 uppercase tracking-wider"
                    >
                      <span
                        class="text-xs opacity-0 group-hover/tags:opacity-100 transition-all duration-500 -translate-x-2 group-hover/tags:translate-x-0"
                        >🐾</span
                      >
                      热门标签 <span class="opacity-40 font-normal">Tags</span>:
                    </span>
                    <div class="flex items-center gap-2">
                      <button
                        v-for="{ tag, count } in topTags"
                        :key="tag"
                        class="px-4 py-1.5 rounded-full text-[10px] font-bold transition-all border shrink-0 active:scale-90 flex items-center gap-2 group/tag backdrop-blur-md"
                        :class="
                          memoryFilterTags.includes(tag)
                            ? 'bg-sky-500/20 text-sky-600 border-sky-500/40 shadow-lg shadow-sky-500/20'
                            : 'bg-sky-50/50 text-slate-500 border-sky-100 hover:bg-sky-100/50 hover:border-sky-300 hover:text-sky-600'
                        "
                        @click="
                          () => {
                            if (memoryFilterTags.includes(tag))
                              memoryFilterTags = memoryFilterTags.filter((t) => t !== tag)
                            else memoryFilterTags.push(tag)
                            fetchMemories()
                          }
                        "
                      >
                        <span
                          class="opacity-0 w-0 group-hover/tag:w-auto group-hover/tag:opacity-100 transition-all duration-500 overflow-hidden"
                          >✨</span
                        >
                        # {{ tag }}
                        <span
                          v-if="count > 1"
                          class="text-[9px] opacity-40 group-hover:opacity-100 transition-opacity"
                          >({{ count }})</span
                        >
                      </button>
                    </div>
                  </div>
                </PCard>
              </div>

              <!-- List Mode -->
              <div
                v-show="memoryViewMode === 'list'"
                class="flex-1 overflow-y-auto px-6 pb-6 custom-scrollbar"
              >
                <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
                  <div
                    v-for="m in memories"
                    :key="m.id"
                    class="group relative bg-white/80 hover:bg-sky-50/50 border border-sky-100 hover:border-sky-300 rounded-2xl p-4 transition-all duration-300 flex flex-col h-[280px] hover:-translate-y-1 hover:shadow-xl hover:shadow-sky-100/30"
                  >
                    <!-- Hover Effect ✨ -->
                    <div
                      class="absolute -top-1.5 -right-1.5 opacity-0 group-hover:opacity-100 transition-all duration-300 scale-0 group-hover:scale-110 z-20"
                    >
                      <div class="bg-sky-500 shadow-lg shadow-sky-500/40 rounded-full p-1.5">
                        <PixelIcon name="sparkle" size="xs" class="text-white" />
                      </div>
                    </div>

                    <!-- Header -->
                    <div class="flex items-start justify-between mb-3">
                      <div class="flex flex-wrap gap-2">
                        <span
                          class="px-2 py-0.5 rounded-full text-[10px] uppercase font-bold tracking-wider bg-sky-100 text-sky-600 border border-sky-200 shadow-sm shadow-sky-100/10"
                        >
                          {{ getMemoryTypeLabel(m.type) }}
                        </span>
                        <span
                          v-if="m.sentiment && m.sentiment !== 'neutral'"
                          class="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full bg-white/50 border border-sky-100 shadow-sm animate-bounce"
                          style="animation-duration: 3s"
                        >
                          <PixelIcon
                            :name="getSentimentEmoji(m.sentiment)"
                            size="xs"
                            class="text-sky-500"
                          />
                          <span class="text-[10px] font-bold text-sky-600">{{
                            getSentimentLabel(m.sentiment)
                          }}</span>
                        </span>
                      </div>
                      <button
                        class="p-1.5 rounded-lg text-slate-400 hover:text-rose-500 hover:bg-rose-50 transition-all opacity-0 group-hover:opacity-100 active:scale-90"
                        @click="deleteMemory(m.id)"
                      >
                        <PixelIcon name="trash" size="xs" />
                      </button>
                    </div>

                    <!-- Content -->
                    <div
                      class="flex-1 overflow-y-auto custom-scrollbar mb-3 text-sm text-slate-600 leading-relaxed group-hover:text-slate-700 transition-colors"
                    >
                      {{ m.content }}
                    </div>

                    <!-- Footer -->
                    <div class="mt-auto pt-3 border-t border-sky-100/50 flex flex-col gap-2">
                      <div class="flex flex-wrap gap-1">
                        <span
                          v-for="c in m.clusters ? m.clusters.split(',') : []"
                          :key="c"
                          class="px-1.5 py-0.5 rounded-full text-[10px] bg-amber-50 text-amber-600 border border-amber-100"
                        >
                          {{ c.replace(/[\[\]]/g, '') }}
                        </span>
                        <span
                          v-for="t in m.tags ? m.tags.split(',') : []"
                          :key="t"
                          class="px-1.5 py-0.5 rounded-full text-[10px] bg-sky-50 text-sky-600 border border-sky-100"
                        >
                          #{{ t }}
                        </span>
                      </div>

                      <div
                        class="flex items-center justify-between text-[10px] text-slate-400 font-mono"
                      >
                        <div class="flex gap-2">
                          <PTooltip content="重要度">
                            <span class="flex items-center gap-0.5">
                              ⭐ <span class="text-amber-500/80">{{ m.importance }}</span>
                            </span>
                          </PTooltip>
                          <PTooltip content="活跃度">
                            <span class="flex items-center gap-0.5">
                              🔥
                              <span class="text-rose-500/80">{{ m.access_count || 0 }}</span>
                            </span>
                          </PTooltip>
                        </div>
                        <span class="group-hover:text-slate-500 transition-colors">{{
                          m.realTime
                        }}</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <!-- Graph Mode -->
              <div
                v-show="memoryViewMode === 'graph'"
                v-loading="isLoadingGraph"
                class="flex-1 flex gap-4 p-6 pt-0 overflow-hidden"
              >
                <div
                  v-if="memoryGraphData.nodes.length === 0"
                  class="flex-1 flex items-center justify-center"
                >
                  <PEmpty description="暂无关联数据或数据量过少" />
                </div>
                <div v-else class="flex-1 flex gap-4 h-full">
                  <!-- Chart -->
                  <div
                    ref="graphRef"
                    class="flex-1 h-full bg-sky-50/30 border border-sky-100 rounded-xl overflow-hidden"
                  ></div>

                  <!-- Legend -->
                  <div
                    class="w-64 bg-white/90 backdrop-blur border border-sky-100 rounded-xl p-4 overflow-y-auto custom-scrollbar"
                  >
                    <h4 class="text-sm font-bold text-slate-700 mb-4 flex items-center gap-2">
                      <PixelIcon name="chart" size="xs" class="text-sky-400" /> 图谱图例 🎨✨
                    </h4>

                    <div class="space-y-4">
                      <div class="group/item cursor-help transition-all hover:translate-x-1">
                        <div class="text-xs font-bold text-slate-500 mb-1 flex items-center gap-1">
                          <span class="w-1.5 h-1.5 rounded-full bg-sky-400 animate-pulse"></span> 🧠
                          节点 (Node)
                        </div>
                        <p
                          class="text-[10px] text-slate-400 leading-relaxed group-hover/item:text-slate-500"
                        >
                          代表独立的记忆片段。颜色代表情感，大小代表重要度。🐾
                        </p>
                      </div>

                      <div class="group/item cursor-help transition-all hover:translate-x-1">
                        <div class="text-xs font-bold text-slate-500 mb-1 flex items-center gap-1">
                          <span class="w-3 h-[1.5px] bg-sky-500/50"></span> 🔗 连线 (Edge)
                        </div>
                        <p
                          class="text-[10px] text-slate-400 leading-relaxed group-hover/item:text-slate-500"
                        >
                          代表记忆之间的逻辑关联。🤝
                        </p>
                      </div>

                      <div>
                        <div class="text-xs font-bold text-slate-500 mb-2 flex items-center gap-1">
                          🎨 情感 (Sentiment)
                          <span class="text-[10px] opacity-50 font-normal">颜色参考</span>
                        </div>
                        <div class="flex gap-2 flex-wrap">
                          <span
                            class="px-2 py-0.5 rounded-full text-[10px] bg-sky-50 text-sky-600 border border-sky-100 hover:bg-sky-100 transition-colors"
                            >正面 😊</span
                          >
                          <span
                            class="px-2 py-0.5 rounded-full text-[10px] bg-rose-50 text-rose-600 border border-rose-100 hover:bg-rose-100 transition-colors"
                            >负面 😟</span
                          >
                          <span
                            class="px-2 py-0.5 rounded-full text-[10px] bg-sky-50 text-slate-500 border border-sky-100 hover:bg-sky-100 transition-colors"
                            >中性 😐</span
                          >
                        </div>
                      </div>

                      <div class="pt-4 border-t border-sky-100">
                        <p class="text-[10px] text-slate-400 flex justify-between">
                          <span>当前节点:</span>
                          <span class="text-slate-600 font-mono">{{
                            memoryGraphData.nodes.length
                          }}</span>
                        </p>
                        <p class="text-[10px] text-slate-400 flex justify-between mt-1">
                          <span>当前连线:</span>
                          <PTooltip content="记忆强度">
                            <span class="text-slate-600 font-mono cursor-help">{{
                              memoryGraphData.edges.length
                            }}</span>
                          </PTooltip>
                        </p>
                        <p class="text-[10px] text-slate-400 flex justify-between mt-1">
                          <span>上次激活:</span>
                          <PTooltip content="上次激活时间">
                            <span class="text-slate-600 font-mono cursor-help">{{
                              memoryGraphData.lastActive
                                ? new Date(memoryGraphData.lastActive).toLocaleTimeString()
                                : '-'
                            }}</span>
                          </PTooltip>
                        </p>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <!-- 4. 待办任务 -->
            <div
              v-else-if="currentTab === 'tasks'"
              key="tasks"
              class="h-full flex flex-col overflow-hidden"
            >
              <!-- Toolbar -->
              <div class="p-6 pb-4 flex-none">
                <PCard
                  glass
                  soft3d
                  variant="orange"
                  overflow-visible
                  class="flex items-center justify-between !p-5 rounded-[2rem] relative group/ttoolbar z-30"
                >
                  <!-- 背景装饰 ✨ -->
                  <div
                    class="absolute -right-20 -top-20 w-40 h-40 bg-orange-400/10 blur-[60px] rounded-full pointer-events-none group-hover/ttoolbar:bg-orange-400/20 transition-all duration-1000"
                  ></div>

                  <div class="flex items-center gap-4 relative z-10">
                    <div
                      class="p-3 bg-orange-50 rounded-2xl text-orange-500 border border-orange-100 shadow-sm shadow-orange-200/20 group-hover/ttoolbar:scale-110 group-hover/ttoolbar:rotate-6 transition-all duration-500"
                    >
                      <PixelIcon name="list" size="md" animation="bounce" />
                    </div>
                    <div>
                      <h3 class="text-xl font-bold text-slate-800 flex items-center gap-2">
                        待办与计划
                        <span
                          class="text-xs font-normal text-slate-400 tracking-widest uppercase ml-1 opacity-50 group-hover/ttoolbar:opacity-100 transition-opacity"
                          ># Tasks</span
                        >
                      </h3>
                      <p class="text-xs text-slate-500 flex items-center gap-1.5 mt-0.5">
                        管理 AI 生成的提醒事项与话题
                        <span class="group-hover/ttoolbar:animate-pulse">✨ 🐾</span>
                      </p>
                    </div>
                  </div>

                  <!-- 角色选择 (Agent Selector) -->
                  <div class="flex items-center gap-4 relative z-10">
                    <div class="flex flex-col gap-1 min-w-[150px]">
                      <label
                        class="text-[10px] font-bold text-slate-400 flex items-center gap-1.5 ml-1 uppercase tracking-wider"
                      >
                        <span class="w-1 h-1 rounded-full bg-orange-400 animate-pulse"></span>
                        归属角色
                      </label>
                      <div class="relative group/tagent">
                        <button
                          class="w-full flex items-center justify-between px-4 py-2 bg-white/60 hover:bg-white/90 border border-orange-100/50 hover:border-orange-300 rounded-xl text-sm transition-all active:scale-95 shadow-lg shadow-black/30 backdrop-blur-md group/btn hover-pixel-bounce"
                          :class="isSwitchingAgent ? 'opacity-50 cursor-not-allowed' : ''"
                        >
                          <span class="text-orange-600 font-bold flex items-center gap-2">
                            <span
                              class="text-xs opacity-0 group-hover/btn:opacity-100 transition-all duration-300 -translate-x-2 group-hover:translate-x-0"
                              ><PixelIcon name="paw" size="xs"
                            /></span>
                            {{ activeAgent?.name || '未知' }}
                          </span>
                          <PixelIcon
                            name="chevron-down"
                            size="xs"
                            class="text-slate-400 group-hover/tagent:rotate-180 transition-transform duration-500"
                          />
                        </button>

                        <!-- 下拉菜单 (Dropdown Menu) -->
                        <div
                          class="absolute right-0 top-full mt-2 w-full py-2 bg-white/70 backdrop-blur-xl border border-orange-100 rounded-2xl shadow-xl shadow-orange-200/30 opacity-0 invisible group-hover/tagent:opacity-100 group-hover/tagent:visible transition-all duration-300 z-50 transform origin-top scale-95 group-hover/tagent:scale-100"
                        >
                          <div class="px-3 py-1.5 mb-1 border-b border-orange-50">
                            <span
                              class="text-[10px] font-bold text-slate-400 uppercase tracking-widest flex items-center gap-1"
                            >
                              切换角色 <span class="animate-bounce">✨</span>
                            </span>
                          </div>
                          <button
                            v-for="agent in availableAgents"
                            :key="agent.id"
                            class="w-full text-left px-4 py-2.5 text-sm hover:bg-orange-50 transition-all flex items-center justify-between group/item"
                            :class="{
                              'text-orange-600 font-bold bg-orange-50':
                                agent.id === activeAgent?.id,
                              'text-slate-600': agent.id !== activeAgent?.id,
                              'opacity-50 cursor-not-allowed': !agent.is_enabled
                            }"
                            :disabled="agent.id === activeAgent?.id || !agent.is_enabled"
                            @click="switchAgent(agent.id)"
                          >
                            <div class="flex items-center gap-2">
                              <span
                                class="text-xs opacity-0 group-hover/item:opacity-100 transition-opacity"
                                ><PixelIcon name="paw" size="xs"
                              /></span>
                              <span>{{ agent.name }}</span>
                            </div>
                            <span
                              v-if="!agent.is_enabled"
                              class="text-[10px] text-slate-400 font-bold px-1.5 py-0.5 bg-slate-50 rounded-md"
                              >DISABLED</span
                            >
                          </button>
                        </div>
                      </div>
                    </div>
                  </div>
                </PCard>
              </div>

              <!-- 任务列表 (Task List) -->
              <div class="flex-1 overflow-y-auto px-6 py-2 custom-scrollbar">
                <div
                  v-if="tasks.length"
                  class="columns-1 md:columns-2 lg:columns-3 xl:columns-4 gap-6 space-y-6 pb-8"
                >
                  <div v-for="task in taskList" :key="task.id" class="break-inside-avoid mb-6">
                    <PCard
                      glass
                      soft3d
                      hoverable
                      :variant="task.type === 'reminder' ? 'pink' : 'orange'"
                      class="group/tcard relative !p-6 !rounded-[2rem] transition-all duration-500 overflow-hidden"
                    >
                      <!-- 背景装饰 ✨ -->
                      <div
                        class="absolute -right-10 -top-10 w-24 h-24 blur-[40px] rounded-full pointer-events-none transition-opacity duration-500 opacity-10 group-hover/tcard:opacity-20"
                        :class="task.type === 'reminder' ? 'bg-pink-400' : 'bg-orange-400'"
                      ></div>

                      <!-- 🐾 Hover icon -->
                      <div
                        class="absolute -top-1 -right-1 opacity-0 group-hover/tcard:opacity-100 transition-all duration-500 scale-50 group-hover/tcard:scale-100 z-20"
                      >
                        <div
                          class="shadow-lg rounded-full p-2"
                          :class="
                            task.type === 'reminder'
                              ? 'bg-pink-400 shadow-pink-400/30'
                              : 'bg-orange-400 shadow-orange-400/30'
                          "
                        >
                          <PixelIcon name="sparkle" size="sm" class="text-white" />
                        </div>
                      </div>

                      <!-- Header -->
                      <div class="flex items-start justify-between mb-4 relative z-10">
                        <span
                          class="px-3 py-1 rounded-full text-[10px] font-bold uppercase tracking-widest border backdrop-blur-md transition-all duration-300"
                          :class="
                            task.type === 'reminder'
                              ? 'bg-pink-50 text-pink-500 border-pink-200 group-hover/tcard:bg-pink-100'
                              : 'bg-orange-50 text-orange-500 border-orange-200 group-hover/tcard:bg-orange-100'
                          "
                        >
                          <span class="mr-1">{{ task.type === 'reminder' ? '⏰' : '💡' }}</span>
                          {{ task.type === 'reminder' ? '提醒' : '话题' }}
                        </span>
                        <button
                          class="text-slate-400 hover:text-pink-500 transition-all opacity-0 group-hover/tcard:opacity-100 p-2 rounded-xl hover:bg-pink-50 active:scale-90"
                          @click="deleteTask(task.id)"
                        >
                          <PixelIcon name="trash" size="xs" />
                        </button>
                      </div>

                      <!-- Content -->
                      <div
                        class="text-[15px] text-slate-600 leading-relaxed mb-6 font-medium relative z-10 group-hover/tcard:text-slate-800 transition-colors"
                      >
                        {{ task.content }}
                      </div>

                      <!-- Footer -->
                      <div
                        class="flex items-center justify-between text-[11px] text-slate-400 font-mono border-t border-sky-100/30 pt-4 mt-auto relative z-10 group-hover/tcard:border-sky-200 transition-colors"
                      >
                        <div class="flex items-center gap-2">
                          <PixelIcon
                            name="calendar"
                            size="xs"
                            class="text-slate-300 group-hover/tcard:text-orange-500 transition-colors"
                          />
                          <span class="group-hover/tcard:text-slate-500 transition-colors">{{
                            new Date(task.time).toLocaleString('zh-CN', {
                              month: '2-digit',
                              day: '2-digit',
                              hour: '2-digit',
                              minute: '2-digit'
                            })
                          }}</span>
                        </div>
                        <span
                          class="opacity-0 group-hover/tcard:opacity-100 transition-opacity duration-700"
                          ><PixelIcon name="paw" size="xs"
                        /></span>
                      </div>
                    </PCard>
                  </div>
                </div>

                <!-- Empty State -->
                <PEmpty v-else description="暂无待办任务，Pero 正在休息中... 🐾" />
              </div>
            </div>

            <!-- 5. 模型配置 (重构版) -->
            <div
              v-else-if="currentTab === 'model_config'"
              key="model_config"
              class="h-full flex flex-col overflow-hidden"
            >
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
                  <div
                    class="absolute -left-10 -bottom-10 w-32 h-32 bg-sky-400/5 blur-[50px] rounded-full pointer-events-none group-hover/mtoolbar:bg-sky-400/15 transition-all duration-1000 delay-150"
                  ></div>

                  <div class="flex flex-wrap items-center justify-between gap-5 relative z-10">
                    <div class="flex items-center gap-4">
                      <div
                        class="p-3 bg-sky-50 rounded-2xl text-sky-500 border border-sky-100 shadow-sm shadow-sky-200/20 group-hover/mtoolbar:scale-110 group-hover/mtoolbar:rotate-6 transition-all duration-500"
                      >
                        <PixelIcon name="settings" size="md" animation="spin" />
                      </div>
                      <div>
                        <h3 class="text-xl font-bold text-slate-800 flex items-center gap-2">
                          模型配置
                          <span
                            class="text-xs font-normal text-slate-400 tracking-widest uppercase ml-1 opacity-50 group-hover/mtoolbar:opacity-100 transition-opacity"
                            ># Models</span
                          >
                        </h3>
                        <p class="text-xs text-slate-500 flex items-center gap-1.5 mt-0.5">
                          配置 Pero 的大脑，支持多模型协作
                          <span class="group-hover/mtoolbar:animate-pulse">✨ 🐾</span>
                        </p>
                      </div>
                    </div>

                    <div class="flex items-center gap-3">
                      <PButton
                        variant="secondary"
                        class="!rounded-2xl shadow-lg shadow-sky-200/20 hover:scale-105 active:scale-95 transition-all px-5 border-sky-100 hover:border-sky-300 hover-pixel-bounce"
                        @click="openGlobalSettings"
                      >
                        <div class="flex items-center gap-1.5">
                          <PixelIcon name="globe" size="xs" />
                          全局服务商 <span class="ml-1 opacity-60">Global</span>
                        </div>
                      </PButton>
                      <PButton
                        variant="primary"
                        class="!rounded-2xl shadow-lg shadow-sky-400/20 hover:scale-105 active:scale-95 transition-all px-6 hover-pixel-bounce"
                        @click="openModelEditor(null)"
                      >
                        <div class="flex items-center gap-1.5">
                          <PixelIcon name="plus" size="xs" />
                          添加模型 <span class="ml-1 opacity-80">Add New</span>
                        </div>
                      </PButton>
                    </div>
                  </div>
                </PCard>
              </div>

              <!-- Models Grid -->
              <div class="flex-1 overflow-y-auto px-6 py-4 custom-scrollbar">
                <div
                  class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6 pb-8"
                >
                  <div v-for="model in models" :key="model.id" class="group relative">
                    <!-- 卡片主体 -->
                    <PCard
                      glass
                      soft3d
                      hoverable
                      class="h-full !p-6 !rounded-[2rem] transition-all duration-500 overflow-hidden flex flex-col group/mcard"
                      :class="[
                        currentActiveModelId === model.id
                          ? 'border-sky-300 bg-sky-50/50 ring-1 ring-sky-200'
                          : '',
                        secretaryModelId === model.id ? 'border-amber-300 bg-amber-50/50' : '',
                        reflectionModelId === model.id ? 'border-rose-300 bg-rose-50/50' : ''
                      ]"
                    >
                      <!-- 背景装饰 ✨ -->
                      <div
                        class="absolute -right-10 -top-10 w-24 h-24 blur-[40px] rounded-full pointer-events-none transition-all duration-700 opacity-10 group-hover/mcard:opacity-30"
                        :class="[
                          currentActiveModelId === model.id ? 'bg-sky-400' : 'bg-sky-200',
                          secretaryModelId === model.id ? 'bg-amber-400' : '',
                          reflectionModelId === model.id ? 'bg-rose-400' : ''
                        ]"
                      ></div>

                      <!-- 头部信息 -->
                      <div class="flex items-start justify-between mb-5 relative z-10">
                        <div class="flex-1 min-w-0 pr-4">
                          <PTooltip :content="model.name">
                            <h3
                              class="text-lg font-bold text-slate-700 truncate group-hover/mcard:text-slate-900 transition-colors"
                            >
                              {{ model.name }}
                            </h3>
                          </PTooltip>
                          <div class="flex items-center gap-2 mt-1.5">
                            <span
                              class="text-[10px] font-mono text-slate-400 uppercase tracking-widest group-hover/mcard:text-slate-500"
                            >
                              {{ model.provider }}
                            </span>
                            <div
                              v-if="model.enable_vision"
                              class="flex items-center gap-1 px-1.5 py-0.5 rounded-md bg-sky-50 text-sky-500 border border-sky-100 text-[9px] font-bold"
                            >
                              <PixelIcon name="eye" size="xs" /> VISION
                            </div>
                          </div>
                        </div>

                        <!-- 角色指示器 (图标) -->
                        <div class="flex -space-x-2">
                          <PTooltip
                            v-if="currentActiveModelId === model.id"
                            content="主模型 (Main)"
                          >
                            <div
                              class="w-8 h-8 rounded-full bg-sky-400 flex items-center justify-center text-white shadow-lg shadow-sky-400/30 border-2 border-white z-30"
                            >
                              <PixelIcon name="terminal" size="sm" />
                            </div>
                          </PTooltip>
                          <PTooltip
                            v-if="secretaryModelId === model.id"
                            content="秘书模型 (Secretary)"
                          >
                            <div
                              class="w-8 h-8 rounded-full bg-amber-400 flex items-center justify-center text-white shadow-lg shadow-amber-400/30 border-2 border-white z-20"
                            >
                              <PixelIcon name="chat" size="sm" />
                            </div>
                          </PTooltip>
                          <PTooltip
                            v-if="reflectionModelId === model.id"
                            content="反思模型 (Reflection)"
                          >
                            <div
                              class="w-8 h-8 rounded-full bg-rose-400 flex items-center justify-center text-white shadow-lg shadow-rose-400/30 border-2 border-white z-10"
                            >
                              <PixelIcon name="brain" size="sm" />
                            </div>
                          </PTooltip>
                          <PTooltip v-if="auxModelId === model.id" content="辅助模型 (Aux)">
                            <div
                              class="w-8 h-8 rounded-full bg-indigo-400 flex items-center justify-center text-white shadow-lg shadow-indigo-400/30 border-2 border-white z-0"
                            >
                              <PixelIcon name="sparkle" size="sm" />
                            </div>
                          </PTooltip>
                        </div>
                      </div>

                      <!-- 统计 / 信息 -->
                      <div class="space-y-3 mb-6 relative z-10">
                        <div class="flex items-center justify-between text-[11px]">
                          <span class="text-slate-400">模型 ID</span>
                          <span class="text-slate-500 font-mono truncate max-w-[120px]">{{
                            model.model_id
                          }}</span>
                        </div>
                        <div class="flex items-center justify-between text-[11px]">
                          <span class="text-slate-400">上下文窗口</span>
                          <span class="text-slate-500 font-mono">{{
                            model.max_tokens ? (model.max_tokens / 1024).toFixed(0) + 'K' : '自动'
                          }}</span>
                        </div>
                      </div>

                      <!-- 操作按钮 (常驻但带主题色) -->
                      <div
                        class="mt-auto pt-4 border-t border-sky-100/30 flex items-center justify-end gap-2 relative z-30"
                      >
                        <PTooltip content="编辑模型" placement="top">
                          <button
                            class="p-2 rounded-xl text-slate-400 hover:text-sky-500 hover:bg-sky-50 transition-all active:scale-90 group/btn-edit"
                            @click="openModelEditor(model)"
                          >
                            <PixelIcon
                              name="pencil"
                              size="xs"
                              class="group-hover/btn-edit:rotate-12 transition-transform"
                            />
                          </button>
                        </PTooltip>
                        <PTooltip content="删除模型" placement="top">
                          <button
                            class="p-2 rounded-xl text-slate-400 hover:text-rose-500 hover:bg-rose-50 transition-all active:scale-90 group/btn-del"
                            @click="deleteModel(model.id)"
                          >
                            <PixelIcon
                              name="trash"
                              size="xs"
                              class="group-hover/btn-del:shake transition-transform"
                            />
                          </button>
                        </PTooltip>
                      </div>

                      <!-- 快速切换角色操作 (仅悬停显示) - 优化后的设计 ✨ -->
                      <div
                        class="absolute left-1/2 -translate-x-1/2 bottom-12 bg-white/90 backdrop-blur-2xl p-2.5 rounded-2xl border border-sky-100/50 opacity-0 group-hover/mcard:opacity-100 translate-y-2 group-hover/mcard:translate-y-0 transition-all duration-500 z-40 flex gap-1.5 justify-center shadow-2xl shadow-sky-200/40 pointer-events-none group-hover/mcard:pointer-events-auto border-b-2 border-b-sky-200/50"
                      >
                        <div
                          class="absolute -top-2 left-1/2 -translate-x-1/2 px-2 py-0.5 bg-sky-500 rounded-full text-[7px] text-white font-black tracking-widest uppercase shadow-sm whitespace-nowrap"
                        >
                          Quick Roles
                        </div>
                        <PTooltip content="设为主模型" placement="top">
                          <button
                            class="p-2 rounded-xl transition-all active:scale-90"
                            :class="
                              currentActiveModelId === model.id
                                ? 'bg-sky-500 text-white shadow-lg shadow-sky-200 soft-3d-shadow'
                                : 'bg-sky-50/50 text-sky-500 hover:bg-sky-100 border border-sky-100/50'
                            "
                            @click="setActiveModel(model.id)"
                          >
                            <PixelIcon name="terminal" size="xs" />
                          </button>
                        </PTooltip>
                        <PTooltip content="设为秘书模型" placement="top">
                          <button
                            class="p-2 rounded-xl transition-all active:scale-90"
                            :class="
                              secretaryModelId === model.id
                                ? 'bg-amber-400 text-white shadow-lg shadow-amber-200 soft-3d-shadow'
                                : 'bg-amber-50/50 text-amber-500 hover:bg-amber-100 border border-amber-100/50'
                            "
                            @click="setSecretaryModel(model.id)"
                          >
                            <PixelIcon name="chat" size="xs" />
                          </button>
                        </PTooltip>
                        <PTooltip content="设为反思模型" placement="top">
                          <button
                            class="p-2 rounded-xl transition-all active:scale-90"
                            :class="
                              reflectionModelId === model.id
                                ? 'bg-rose-400 text-white shadow-lg shadow-rose-200 soft-3d-shadow'
                                : 'bg-rose-50/50 text-rose-500 hover:bg-rose-100 border border-rose-100/50'
                            "
                            @click="setReflectionModel(model.id)"
                          >
                            <PixelIcon name="brain" size="xs" />
                          </button>
                        </PTooltip>
                        <PTooltip content="设为辅助模型" placement="top">
                          <button
                            class="p-2 rounded-xl transition-all active:scale-90"
                            :class="
                              auxModelId === model.id
                                ? 'bg-indigo-400 text-white shadow-lg shadow-indigo-200 soft-3d-shadow'
                                : 'bg-indigo-50/50 text-indigo-500 hover:bg-indigo-100 border border-indigo-100/50'
                            "
                            @click="setAuxModel(model.id)"
                          >
                            <PixelIcon name="sparkle" size="xs" />
                          </button>
                        </PTooltip>
                      </div>
                    </PCard>
                  </div>
                </div>
              </div>
            </div>

            <!-- 6. 语音功能 -->
            <div
              v-else-if="currentTab === 'voice_config'"
              key="voice_config"
              class="view-container"
            >
              <VoiceConfigPanel />
            </div>

            <!-- 7. MCP 配置 (重构版) -->
            <div
              v-else-if="currentTab === 'mcp_config'"
              key="mcp_config"
              class="h-full flex flex-col overflow-hidden"
            >
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
                <div
                  class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6 pb-8"
                >
                  <div v-for="mcp in mcps" :key="mcp.id" class="group/mcp-container relative">
                    <!-- 卡片主体 -->
                    <PCard
                      glass
                      soft3d
                      hoverable
                      variant="sky"
                      class="h-full !p-6 !rounded-[2rem] transition-all duration-500 overflow-hidden flex flex-col group/mcard"
                      :class="[
                        mcp.enabled
                          ? 'border-sky-300/30 hover:shadow-sky-100/50'
                          : 'opacity-60 grayscale'
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
                          <span
                            class="text-[10px] font-black text-slate-400 uppercase tracking-widest ml-1"
                          >
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

            <!-- 8. 用户设定 (重构版) -->
            <div
              v-else-if="currentTab === 'user_settings'"
              key="user_settings"
              class="h-full overflow-y-auto custom-scrollbar p-6"
            >
              <div class="max-w-2xl mx-auto pb-12">
                <!-- Header -->
                <div class="flex items-center gap-4 mb-8">
                  <div
                    class="p-3 bg-sky-50 rounded-2xl text-sky-500 border border-sky-100 shadow-sm shadow-sky-200/20"
                  >
                    <PixelIcon name="user" size="md" animation="bounce" />
                  </div>
                  <div>
                    <h3 class="text-2xl font-bold text-slate-800 flex items-center gap-2">
                      主人身份设定
                      <span
                        class="text-xs font-normal text-slate-400 tracking-widest uppercase ml-1"
                        ># Owner Persona</span
                      >
                    </h3>
                    <p class="text-sm text-slate-500 flex items-center gap-1">
                      让 {{ activeAgent?.name || 'Pero' }} 更好地认识主人吧
                      <PixelIcon name="sparkle" size="xs" animation="pulse" />
                      <PixelIcon name="paw" size="xs" />
                    </p>
                  </div>
                </div>

                <PCard
                  glass
                  soft3d
                  pixel
                  variant="sky"
                  class="relative overflow-hidden border-sky-100 hover:border-sky-300 transition-all duration-700 rounded-[2.5rem] shadow-xl shadow-sky-100/30 group/settings-card bg-white/80"
                >
                  <!-- 背景装饰 ✨ -->
                  <div
                    class="absolute -right-20 -top-20 w-60 h-60 bg-sky-400/5 blur-[80px] rounded-full pointer-events-none group-hover/settings-card:bg-sky-400/10 transition-all duration-1000"
                  ></div>
                  <div
                    class="absolute -left-10 -bottom-10 w-40 h-40 bg-sky-400/5 blur-[60px] rounded-full pointer-events-none group-hover/settings-card:bg-sky-400/10 transition-all duration-1000 delay-300"
                  ></div>

                  <div class="p-4 space-y-8 relative z-10">
                    <!-- Name & QQ -->
                    <div class="grid grid-cols-1 md:grid-cols-2 gap-8">
                      <div class="space-y-3">
                        <label
                          class="text-sm font-bold text-slate-600 flex items-center gap-2 ml-1"
                        >
                          <span class="w-1.5 h-1.5 rounded-full bg-sky-400 animate-pulse"></span>
                          主人的名字
                          <span class="text-[10px] text-slate-400 font-normal uppercase"
                            >Owner Name</span
                          >
                        </label>
                        <PInput
                          v-model="userSettings.owner_name"
                          class="!rounded-2xl !bg-white/80 !border-sky-100 focus:!border-sky-300 transition-all shadow-sm"
                          :placeholder="(activeAgent?.name || 'Pero') + ' 对你的称呼'"
                        />
                      </div>
                      <div class="space-y-3">
                        <label
                          class="text-sm font-bold text-slate-600 flex items-center gap-2 ml-1"
                        >
                          <span class="w-1.5 h-1.5 rounded-full bg-sky-400 animate-pulse"></span>
                          主人的 QQ 号
                          <span class="text-[10px] text-slate-400 font-normal uppercase"
                            >Owner QQ</span
                          >
                        </label>
                        <PInput
                          v-model="userSettings.owner_qq"
                          class="!rounded-2xl !bg-white/80 !border-sky-100 focus:!border-sky-300 transition-all shadow-sm"
                          :placeholder="'用于 ' + (activeAgent?.name || 'Pero') + ' 主动联系你'"
                        />
                      </div>
                    </div>

                    <!-- Persona -->
                    <div class="space-y-3">
                      <label class="text-sm font-bold text-slate-600 flex items-center gap-2 ml-1">
                        <span class="w-1.5 h-1.5 rounded-full bg-sky-400 animate-pulse"></span>
                        主人的人设信息
                        <span class="text-[10px] text-slate-400 font-normal uppercase"
                          >Owner Persona</span
                        >
                      </label>
                      <PTextarea
                        v-model="userSettings.user_persona"
                        class="!rounded-[2rem] !bg-white/80 !border-sky-100 focus:!border-sky-300 transition-all shadow-sm leading-relaxed"
                        :rows="10"
                        placeholder="描述一下你自己，比如你的性格、职业、与 Pero 的关系等。这些信息会帮助 Pero 更好地了解你并调整交流方式。🐾"
                      />
                      <p class="text-[11px] text-slate-400 px-2 flex items-center gap-1.5">
                        💡 完善的人设能让对话更具个性化和沉浸感哦~
                      </p>
                    </div>

                    <!-- Actions -->
                    <div class="pt-4 flex justify-end">
                      <PButton
                        variant="primary"
                        size="lg"
                        class="!rounded-2xl px-10 py-6 shadow-lg shadow-sky-400/20 hover:scale-105 active:scale-95 transition-all group/save-btn hover-pixel-bounce"
                        :loading="isSaving"
                        @click="saveUserSettings"
                      >
                        <span class="flex items-center gap-2">
                          保存设定
                          <span class="text-lg group-hover/save-btn:scale-125 transition-transform"
                            ><PixelIcon name="thought" size="sm"
                          /></span>
                        </span>
                      </PButton>
                    </div>
                  </div>
                </PCard>
              </div>
            </div>

            <!-- 9. 恢复出厂设置 (重构版) -->
            <div
              v-else-if="currentTab === 'system_reset'"
              key="system_reset"
              class="h-full overflow-y-auto custom-scrollbar p-6 flex items-center justify-center"
            >
              <PCard
                glass
                soft3d
                pixel
                variant="rose"
                class="max-w-lg w-full !p-8 !rounded-[2.5rem] relative overflow-hidden group/reset-card"
              >
                <!-- 背景装饰 ✨ -->
                <div
                  class="absolute -right-20 -top-20 w-60 h-60 bg-rose-400/10 blur-[80px] rounded-full pointer-events-none group-hover/reset-card:bg-rose-400/20 transition-all duration-1000"
                ></div>
                <div
                  class="absolute -left-20 -bottom-20 w-40 h-40 bg-amber-400/5 blur-[60px] rounded-full pointer-events-none group-hover/reset-card:bg-amber-400/10 transition-all duration-1000 delay-300"
                ></div>

                <div class="relative z-10">
                  <div class="flex items-center gap-4 mb-8">
                    <div
                      class="p-4 bg-rose-50 rounded-2xl text-rose-500 border border-rose-100 shadow-sm shadow-rose-100/30 group-hover/reset-card:scale-110 group-hover/reset-card:rotate-6 transition-all duration-500 soft-3d-shadow"
                    >
                      <PixelIcon name="alert" size="lg" animation="pulse" />
                    </div>
                    <div>
                      <h3 class="text-xl font-black text-slate-800">恢复出厂设置</h3>
                      <p
                        class="text-[10px] text-slate-400 mt-1 uppercase tracking-widest font-bold"
                      >
                        # System Factory Reset
                      </p>
                    </div>
                  </div>

                  <div class="space-y-6">
                    <div
                      class="bg-white/40 backdrop-blur-md rounded-[2rem] p-6 border border-rose-100/50 soft-3d-shadow"
                    >
                      <p class="text-sm font-bold text-slate-700 mb-4 flex items-center gap-2">
                        <span class="w-1.5 h-1.5 rounded-full bg-rose-500 animate-pulse"></span>
                        此操作将执行以下清理：
                      </p>
                      <ul class="space-y-3 text-slate-500 text-xs font-medium">
                        <li
                          class="flex items-center gap-3 group/item hover:text-slate-800 transition-colors"
                        >
                          <span
                            class="w-1 h-1 rounded-full bg-rose-200 group-hover/item:bg-rose-500 transition-colors"
                          ></span>
                          清除所有 <strong class="text-rose-500">长期记忆</strong> (Memories)
                        </li>
                        <li
                          class="flex items-center gap-3 group/item hover:text-slate-800 transition-colors"
                        >
                          <span
                            class="w-1 h-1 rounded-full bg-rose-200 group-hover/item:bg-rose-500 transition-colors"
                          ></span>
                          清除所有 <strong class="text-rose-500">对话历史</strong> (Logs)
                        </li>
                        <li
                          class="flex items-center gap-3 group/item hover:text-slate-800 transition-colors"
                        >
                          <span
                            class="w-1 h-1 rounded-full bg-rose-200 group-hover/item:bg-rose-500 transition-colors"
                          ></span>
                          重置 Pero 的 <strong class="text-rose-500">状态与情绪</strong> (Pet State)
                        </li>
                        <li
                          class="flex items-center gap-3 group/item hover:text-slate-800 transition-colors"
                        >
                          <span
                            class="w-1 h-1 rounded-full bg-rose-200 group-hover/item:bg-rose-500 transition-colors"
                          ></span>
                          清除所有 <strong class="text-rose-500">待办提醒与话题</strong> (Tasks)
                        </li>
                        <li
                          class="flex items-center gap-3 group/item hover:text-slate-800 transition-colors"
                        >
                          <span
                            class="w-1 h-1 rounded-full bg-rose-200 group-hover/item:bg-rose-500 transition-colors"
                          ></span>
                          重置 <strong class="text-rose-500">主人设定</strong> (Owner Persona)
                        </li>
                      </ul>
                    </div>

                    <div
                      class="p-4 bg-amber-50/50 backdrop-blur-md border border-amber-100 rounded-2xl text-[11px] text-amber-600 font-medium leading-relaxed soft-3d-shadow"
                    >
                      <span class="mr-1">💡</span>
                      注：模型 API 配置、语音配置、MCP 配置将被保留，不用担心重新配置服务器哦~ ✨
                    </div>

                    <div class="pt-4 flex justify-center">
                      <PButton
                        variant="danger"
                        size="lg"
                        class="!rounded-2xl px-10 py-7 shadow-xl shadow-rose-400/20 hover:scale-105 active:scale-95 transition-all group/reset-btn relative overflow-hidden hover-pixel-bounce"
                        :loading="isSaving"
                        @click="handleSystemReset"
                      >
                        <div class="flex items-center gap-3 relative z-10">
                          <PixelIcon
                            name="trash"
                            size="md"
                            class="group-hover/reset-btn:shake transition-transform"
                          />
                          <span class="font-black tracking-widest text-base">立即执行深度重置</span>
                          <span class="text-xl group-hover/reset-btn:rotate-12 transition-transform"
                            ><PixelIcon name="firecracker" size="md"
                          /></span>
                        </div>
                        <!-- Button gloss effect -->
                        <div
                          class="absolute inset-0 bg-gradient-to-r from-transparent via-white/20 to-transparent -translate-x-full group-hover:translate-x-full transition-transform duration-1000"
                        ></div>
                      </PButton>
                    </div>
                  </div>
                </div>
              </PCard>
            </div>

            <!-- 10. NapCat Terminal -->
            <!-- 10. NapCat 终端 -->
            <div
              v-else-if="currentTab === 'napcat'"
              key="napcat"
              class="h-full flex flex-col p-6 overflow-hidden relative"
            >
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

            <!-- 11. 系统终端 -->
            <div
              v-else-if="currentTab === 'terminal'"
              key="terminal"
              class="h-full flex flex-col p-6 overflow-hidden relative"
            >
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
          </Transition>
        </div>
      </main>
    </div>

    <!-- Dialogs -->
    <!-- Story Import Dialog -->
    <PModal
      v-model="showImportStoryDialog"
      title="导入故事生成记忆"
      width="600px"
      class="backdrop-blur-2xl bg-white/80 border-sky-100 shadow-2xl shadow-sky-100/40"
    >
      <div class="space-y-4">
        <div class="text-sm text-slate-600 leading-relaxed">
          <p>你可以将小说设定、人物背景、日记或长篇回忆录粘贴在这里。</p>
          <p>
            Pero 将会阅读这些内容，并将其拆解为一系列关键记忆节点存入数据库，作为它的“长期记忆”。
          </p>
          <p
            class="mt-2 text-amber-600 text-xs font-bold flex items-center gap-1.5 bg-amber-50 px-3 py-2 rounded-lg border border-amber-200"
          >
            <PixelIcon name="alert" size="xs" />
            注意：这是一个耗时操作，且会消耗较多 Token。
          </p>
        </div>
        <PTextarea
          v-model="importStoryText"
          :rows="10"
          placeholder="在此粘贴长文本..."
          class="bg-sky-50/50 border-sky-100 focus:border-sky-300 transition-all duration-300"
        />
        <div class="flex justify-end gap-3 pt-2">
          <PButton variant="ghost" @click="showImportStoryDialog = false">取消</PButton>
          <PButton
            variant="primary"
            :loading="isImportingStory"
            class="shadow-lg shadow-sky-400/20"
            @click="handleImportStory"
          >
            开始生成
          </PButton>
        </div>
      </div>
    </PModal>

    <!-- Global Settings Dialog -->
    <PModal
      v-model="showGlobalSettings"
      title="全局服务商配置"
      width="500px"
      overflow-visible
      class="backdrop-blur-2xl bg-white/80 border-sky-100 shadow-2xl shadow-sky-100/40"
    >
      <div class="space-y-5">
        <div class="space-y-2 relative z-20">
          <label class="text-sm font-medium text-slate-600">服务商 (Provider)</label>
          <PSelect
            v-model="globalConfig.provider"
            :options="providerOptions"
            placeholder="选择服务商"
            class="bg-white/80 border-sky-100 !rounded-2xl shadow-lg shadow-black/30 backdrop-blur-md"
            @change="handleGlobalProviderChange"
          />
        </div>
        <div class="space-y-2 relative z-10">
          <label class="text-sm font-medium text-slate-600">API Key</label>
          <PInput
            v-model="globalConfig.global_llm_api_key"
            type="password"
            placeholder="sk-..."
            class="bg-white/80 border-sky-100"
          />
        </div>
        <div class="space-y-2">
          <label class="text-sm font-medium text-slate-600">API Base URL</label>
          <PInput
            v-model="globalConfig.global_llm_api_base"
            placeholder="https://api.openai.com"
            :disabled="globalConfig.provider === 'deepseek'"
            class="bg-white/80 border-sky-100"
          />
        </div>
        <div class="flex justify-end gap-3 pt-4 border-t border-sky-100 mt-6">
          <PButton variant="ghost" @click="showGlobalSettings = false">取消</PButton>
          <PButton
            variant="primary"
            :loading="isSaving"
            class="shadow-lg shadow-sky-400/20"
            @click="saveGlobalSettings"
            >保存</PButton
          >
        </div>
      </div>
    </PModal>

    <!-- Model Editor Dialog -->
    <PModal
      v-model="showModelEditor"
      :title="currentEditingModel.id ? '编辑模型' : '添加模型'"
      width="600px"
      overflow-visible
      class="backdrop-blur-2xl bg-white/80 border-sky-100 shadow-2xl shadow-sky-100/40"
    >
      <div class="space-y-5">
        <!-- Display Name -->
        <div class="space-y-2 relative z-30">
          <label class="text-sm font-medium text-slate-600">显示名称</label>
          <PInput
            v-model="currentEditingModel.name"
            placeholder="例如：GPT-4o"
            class="bg-white/80 border-sky-100"
          />
        </div>

        <!-- Provider -->
        <div class="space-y-2 relative z-20">
          <label class="text-sm font-medium text-slate-600">服务商 (Provider)</label>
          <PSelect
            v-model="currentEditingModel.provider"
            :options="providerOptions"
            placeholder="选择服务商"
            class="bg-white/80 border-sky-100 !rounded-2xl shadow-lg shadow-black/30 backdrop-blur-md"
            @change="handleProviderChange"
          />
        </div>

        <!-- Model ID -->
        <div class="space-y-2 relative z-10">
          <label class="text-sm font-medium text-slate-600">Model ID</label>
          <div class="flex gap-2">
            <PInput
              v-model="currentEditingModel.model_id"
              placeholder="gpt-4"
              class="flex-1 bg-white/80 border-sky-100"
            />
            <PButton
              :loading="isFetchingRemote"
              class="bg-sky-50 text-sky-600 border-sky-100 hover:bg-sky-100"
              @click="fetchRemoteModels"
              >获取列表</PButton
            >
          </div>
          <PSelect
            v-if="remoteModels.length"
            v-model="currentEditingModel.model_id"
            :options="remoteModels.map((m) => ({ label: m, value: m }))"
            placeholder="选择获取到的模型"
            class="mt-1 bg-white/80 border-sky-100 !rounded-2xl shadow-lg shadow-black/30 backdrop-blur-md"
          />
        </div>

        <!-- Configuration Source -->
        <div class="space-y-2 relative z-5">
          <label class="text-sm font-medium text-slate-600">配置来源</label>
          <div class="flex items-center gap-6">
            <label class="flex items-center gap-2 cursor-pointer group">
              <input
                v-model="currentEditingModel.provider_type"
                type="radio"
                value="global"
                class="hidden"
              />
              <div
                class="w-4 h-4 rounded-full border-2 flex items-center justify-center transition-all duration-200"
                :class="
                  currentEditingModel.provider_type === 'global'
                    ? 'border-sky-500 shadow-lg shadow-sky-500/20'
                    : 'border-slate-300 group-hover:border-sky-300'
                "
              >
                <div
                  class="w-2 h-2 rounded-full bg-sky-500 transform transition-transform duration-200"
                  :class="currentEditingModel.provider_type === 'global' ? 'scale-100' : 'scale-0'"
                ></div>
              </div>
              <span
                class="text-sm text-slate-600 group-hover:text-sky-600 flex items-center gap-1.5"
                >全局继承 <PixelIcon name="sparkle" size="xs"
              /></span>
            </label>

            <label class="flex items-center gap-2 cursor-pointer group">
              <input
                v-model="currentEditingModel.provider_type"
                type="radio"
                value="custom"
                class="hidden"
              />
              <div
                class="w-4 h-4 rounded-full border-2 flex items-center justify-center transition-all duration-200"
                :class="
                  currentEditingModel.provider_type === 'custom'
                    ? 'border-sky-500 shadow-lg shadow-sky-500/20'
                    : 'border-slate-300 group-hover:border-sky-300'
                "
              >
                <div
                  class="w-2 h-2 rounded-full bg-sky-500 transform transition-transform duration-200"
                  :class="currentEditingModel.provider_type === 'custom' ? 'scale-100' : 'scale-0'"
                ></div>
              </div>
              <span
                class="text-sm text-slate-600 group-hover:text-sky-600 flex items-center gap-1.5"
                >独立配置 <PixelIcon name="thought" size="xs"
              /></span>
            </label>
          </div>
        </div>

        <!-- Custom Config Fields -->
        <div
          v-if="currentEditingModel.provider_type === 'custom'"
          class="space-y-4 p-4 rounded-2xl bg-sky-50/30 border border-sky-100 shadow-inner"
        >
          <div class="space-y-2">
            <label class="text-sm font-medium text-slate-600 flex items-center gap-2">
              <span class="w-1 h-1 rounded-full bg-sky-400"></span>
              API Key
            </label>
            <PInput
              v-model="currentEditingModel.api_key"
              type="password"
              class="!rounded-xl bg-white border-sky-100"
            />
          </div>
          <div
            v-if="!['gemini', 'anthropic'].includes(currentEditingModel.provider)"
            class="space-y-2"
          >
            <label class="text-sm font-medium text-slate-600 flex items-center gap-2">
              <span class="w-1 h-1 rounded-full bg-sky-400"></span>
              Base URL
            </label>
            <PInput
              v-model="currentEditingModel.api_base"
              class="!rounded-xl bg-white border-sky-100"
              :disabled="!!providerDefaults[currentEditingModel.provider]"
            />
          </div>
        </div>

        <div class="w-full h-px bg-sky-100 my-4"></div>
        <h4
          class="text-xs font-bold text-slate-400 uppercase tracking-wider mb-4 flex items-center gap-2"
        >
          参数设置 <span class="text-[10px] font-normal opacity-50"># Parameters</span>
        </h4>

        <div class="grid grid-cols-2 gap-4">
          <div class="space-y-2">
            <label class="text-sm font-medium text-slate-600">Temperature</label>
            <PInputNumber
              v-model="currentEditingModel.temperature"
              :step="0.1"
              :min="0"
              :max="2"
              class="!rounded-xl bg-white/80 border-sky-100"
            />
          </div>
          <div class="space-y-2">
            <label class="text-sm font-medium text-slate-600">Max Tokens</label>
            <PInputNumber
              v-model="currentEditingModel.max_tokens"
              :step="100"
              class="!rounded-xl bg-white/80 border-sky-100"
            />
          </div>
        </div>

        <div class="space-y-3 pt-2">
          <PCheckbox v-model="currentEditingModel.stream" label="开启流式传输 (Stream)" />
          <div class="flex flex-wrap gap-4">
            <PCheckbox v-model="currentEditingModel.enable_vision" label="视觉模态" />
            <PCheckbox v-model="currentEditingModel.enable_voice" label="语音模态 (Input)" />
            <PCheckbox v-model="currentEditingModel.enable_video" label="视频模态" />
          </div>
        </div>

        <div class="flex justify-end gap-3 pt-6 border-t border-sky-100 mt-6">
          <PButton variant="ghost" class="!rounded-xl" @click="showModelEditor = false"
            >取消</PButton
          >
          <PButton
            variant="primary"
            class="!rounded-xl px-8 shadow-lg shadow-sky-400/20"
            :loading="isSaving"
            @click="saveModel"
            >保存设定 <PixelIcon name="thought" size="xs" class="ml-1"
          /></PButton>
        </div>
      </div>
    </PModal>

    <!-- MCP Editor Dialog -->
    <PModal
      v-model="showMcpEditor"
      :title="currentEditingMcp.id ? '编辑 MCP' : '添加 MCP'"
      width="600px"
      overflow-visible
      class="backdrop-blur-2xl bg-white/70 border-sky-100 shadow-2xl shadow-sky-200/40"
    >
      <div class="space-y-5">
        <div class="space-y-2 relative z-20">
          <label class="text-sm font-medium text-slate-600">名称</label>
          <PInput v-model="currentEditingMcp.name" class="bg-sky-50/50 border-sky-100" />
        </div>
        <div class="space-y-2 relative z-10">
          <label class="text-sm font-medium text-slate-600">类型</label>
          <PSelect
            v-model="currentEditingMcp.type"
            :options="mcpTypeOptions"
            class="bg-sky-50/50 border-sky-100 !rounded-2xl shadow-lg shadow-black/30 backdrop-blur-md"
          />
        </div>

        <template v-if="currentEditingMcp.type === 'stdio'">
          <div class="space-y-2">
            <label class="text-sm font-medium text-slate-600">命令</label>
            <PInput
              v-model="currentEditingMcp.command"
              placeholder="node, python..."
              class="bg-sky-50/50 border-sky-100"
            />
          </div>
          <div class="space-y-2">
            <label class="text-sm font-medium text-slate-600">参数 (JSON)</label>
            <PTextarea
              v-model="currentEditingMcp.args"
              :rows="2"
              placeholder='["arg1", "arg2"]'
              class="bg-sky-50/50 border-sky-100"
            />
          </div>
          <div class="space-y-2">
            <label class="text-sm font-medium text-slate-600">环境变量 (JSON)</label>
            <PTextarea
              v-model="currentEditingMcp.env"
              :rows="2"
              placeholder='{"KEY": "VALUE"}'
              class="bg-sky-50/50 border-sky-100"
            />
          </div>
        </template>

        <template v-if="currentEditingMcp.type === 'sse'">
          <div class="space-y-2">
            <label class="text-sm font-medium text-slate-600">URL</label>
            <PInput v-model="currentEditingMcp.url" class="bg-sky-50/50 border-sky-100" />
          </div>
        </template>

        <div class="pt-2 flex items-center gap-3">
          <PSwitch v-model="currentEditingMcp.enabled" />
          <span class="text-sm text-slate-600">启用此 MCP 服务器</span>
        </div>

        <div class="flex justify-end gap-3 pt-4 border-t border-sky-100 mt-6">
          <PButton variant="ghost" @click="showMcpEditor = false">取消</PButton>
          <PButton
            variant="primary"
            :loading="isSaving"
            class="shadow-lg shadow-sky-400/20"
            @click="saveMcp"
            >保存</PButton
          >
        </div>
      </div>
    </PModal>

    <!-- 调试日志弹窗 -->
    <PModal
      v-model="showDebugDialog"
      title="对话调试详情 (Debug View)"
      width="900px"
      class="backdrop-blur-2xl bg-white/70 border-sky-100 shadow-2xl shadow-sky-200/40"
    >
      <div v-if="currentDebugLog" class="h-[70vh] flex flex-col">
        <!-- 顶部控制栏 -->
        <div
          class="flex justify-center mb-4 bg-sky-50/50 p-1 rounded-lg self-center border border-sky-100 shrink-0"
        >
          <button
            v-for="mode in [
              { label: '回复记录解析 (Response)', value: 'response' },
              { label: '完整提示词 & ReAct (Prompt)', value: 'prompt' }
            ]"
            :key="mode.value"
            class="px-4 py-1.5 text-xs font-medium rounded-md transition-all duration-200 focus:outline-none"
            :class="[
              debugViewMode === mode.value
                ? 'bg-sky-500 text-white shadow-lg shadow-sky-400/20'
                : 'text-slate-500 hover:text-sky-600 hover:bg-sky-100'
            ]"
            @click="
              () => {
                handleDebugModeChange(mode.value)
                debugViewMode = mode.value
              }
            "
          >
            {{ mode.label }}
          </button>
        </div>

        <div class="flex-1 overflow-y-auto pr-2 custom-scrollbar">
          <!-- 模式 1: 回复记录解析 -->
          <template v-if="debugViewMode === 'response'">
            <div
              class="bg-white/80 border border-sky-200 rounded-lg p-4 mb-4 text-xs text-slate-500 space-y-1 shadow-sm shadow-sky-100/20"
            >
              <p><strong class="text-slate-700">Log ID:</strong> {{ currentDebugLog.id }}</p>
              <p><strong class="text-slate-700">Role:</strong> {{ currentDebugLog.role }}</p>
              <p>
                <strong class="text-slate-700">Raw Content Length:</strong>
                {{ (currentDebugLog.raw_content || currentDebugLog.content || '').length }} chars
              </p>
            </div>

            <div class="space-y-3">
              <div
                v-for="(segment, index) in debugSegments"
                :key="index"
                class="rounded-lg border overflow-hidden transition-colors duration-200"
                :class="{
                  'bg-amber-50 border-amber-200': segment.type === 'thinking',
                  'bg-sky-50 border-sky-200': segment.type === 'monologue',
                  'bg-cyan-50 border-cyan-200': segment.type === 'nit',
                  'bg-white border-sky-100 shadow-sm': !['thinking', 'monologue', 'nit'].includes(
                    segment.type
                  )
                }"
              >
                <div
                  v-if="segment.type === 'thinking'"
                  class="px-3 py-1.5 bg-amber-100/50 text-amber-700 text-xs font-bold border-b border-amber-200 flex items-center gap-2"
                >
                  <PixelIcon name="brain" size="xs" />
                  Thinking Chain (思维链)
                </div>
                <div
                  v-else-if="segment.type === 'monologue'"
                  class="px-3 py-1.5 bg-sky-100/50 text-sky-700 text-xs font-bold border-b border-sky-200 flex items-center gap-2"
                >
                  <PixelIcon name="chat" size="xs" />
                  Inner Monologue (内心独白)
                </div>
                <div
                  v-else-if="segment.type === 'nit'"
                  class="px-3 py-1.5 bg-cyan-100/50 text-cyan-700 text-xs font-bold border-b border-cyan-200 flex items-center gap-2"
                >
                  <PixelIcon name="terminal" size="xs" />
                  NIT Script (工具调用)
                </div>

                <div class="p-3 text-sm leading-relaxed overflow-x-auto">
                  <div
                    v-if="segment.type === 'thinking'"
                    class="text-slate-600 font-mono text-xs whitespace-pre-wrap"
                  >
                    {{ segment.content }}
                  </div>
                  <div v-else-if="segment.type === 'monologue'" class="text-slate-600 italic">
                    {{ segment.content }}
                  </div>
                  <div
                    v-else-if="segment.type === 'nit'"
                    class="font-mono text-xs text-cyan-700 bg-sky-50/50 p-2 rounded border border-cyan-100"
                  >
                    <pre>{{ segment.content }}</pre>
                  </div>
                  <div v-else class="text-slate-700 prose prose-slate max-w-none prose-sm">
                    <AsyncMarkdown :content="segment.content" />
                  </div>
                </div>
              </div>
            </div>
          </template>

          <!-- 模式 2: 完整提示词 & ReAct -->
          <template v-else-if="debugViewMode === 'prompt'">
            <div
              v-if="isLoadingPrompt"
              class="flex flex-col items-center justify-center h-full text-slate-400 min-h-[300px]"
            >
              <PixelIcon name="refresh" size="xl" animation="spin" class="text-sky-500 mb-3" />
              <p>正在从后端获取完整 Context... <PixelIcon name="sparkle" size="xs" /></p>
            </div>

            <div v-else class="space-y-4">
              <!-- 统计信息 -->
              <div
                class="bg-sky-50 border border-sky-100 rounded-lg p-3 flex gap-6 text-xs text-sky-600 mb-4"
              >
                <div>
                  <strong class="text-sky-700">Total Messages:</strong>
                  {{ currentPromptMessages.length }}
                </div>
                <div>
                  <strong class="text-sky-700">Total Length (Chars):</strong>
                  {{ totalPromptLength }}
                </div>
                <div>
                  <strong class="text-sky-700">Est. Tokens:</strong> ~{{
                    Math.ceil(totalPromptLength / 3.5)
                  }}
                </div>
              </div>

              <!-- 消息列表 -->
              <div class="space-y-3">
                <div
                  v-for="(msg, idx) in currentPromptMessages"
                  :key="idx"
                  class="rounded-lg overflow-hidden border border-sky-100 bg-white shadow-sm"
                >
                  <div
                    class="px-3 py-1.5 text-xs font-bold uppercase flex justify-between items-center border-b border-sky-100"
                    :class="{
                      'bg-sky-50 text-sky-600': msg.role === 'user',
                      'bg-sky-100 text-sky-700 font-bold': msg.role === 'assistant',
                      'bg-rose-50 text-rose-600': msg.role === 'system',
                      'bg-sky-50 text-slate-500': !['user', 'assistant', 'system'].includes(
                        msg.role
                      )
                    }"
                  >
                    <span>{{ msg.role }}</span>
                    <span class="font-normal opacity-50 font-mono"
                      >{{ (msg.content || '').length }} chars</span
                    >
                  </div>
                  <pre
                    class="p-3 font-mono text-xs text-slate-600 whitespace-pre-wrap overflow-x-auto max-h-[400px] custom-scrollbar"
                    >{{ msg.content }}</pre
                  >
                </div>
              </div>
            </div>
          </template>
        </div>
      </div>
    </PModal>

    <!-- Confirm Dialog -->
    <PModal
      v-model="showConfirmModal"
      :title="confirmModalTitle"
      width="400px"
      class="backdrop-blur-2xl bg-white/70 border-sky-100 shadow-2xl shadow-sky-200/40"
      @close="handleCancel"
    >
      <div class="p-4">
        <div class="flex items-start gap-4">
          <div
            class="w-10 h-10 rounded-full flex items-center justify-center shrink-0"
            :class="{
              'bg-amber-100 text-amber-600': confirmType === 'warning',
              'bg-sky-100 text-sky-600': confirmType === 'info',
              'bg-rose-100 text-rose-600': confirmType === 'error'
            }"
          >
            <PixelIcon v-if="confirmType === 'warning'" name="alert" size="md" />
            <PixelIcon v-else-if="confirmType === 'info'" name="info" size="md" />
            <PixelIcon v-else name="alert" size="md" />
          </div>
          <div class="flex-1">
            <p class="text-slate-600 text-sm leading-relaxed" v-html="confirmModalContent"></p>
            <PInput
              v-if="isPrompt"
              v-model="promptValue"
              :placeholder="promptPlaceholder"
              class="mt-4 w-full bg-sky-50/50 border-sky-100"
            />
          </div>
        </div>
      </div>
      <template #footer>
        <div class="flex justify-end gap-3">
          <PButton variant="ghost" @click="handleCancel">取消</PButton>
          <PButton
            :variant="confirmType === 'error' ? 'danger' : 'primary'"
            class="shadow-lg"
            :class="confirmType === 'error' ? 'shadow-rose-400/20' : 'shadow-sky-400/20'"
            @click="handleConfirm"
          >
            确定
          </PButton>
        </div>
      </template>
    </PModal>
  </div>
</template>

<script setup>
import { ref, shallowRef, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import CustomTitleBar from '../components/layout/CustomTitleBar.vue'
import { listen, invoke, isElectron } from '@/utils/ipcAdapter'
import VoiceConfigPanel from '../components/settings/VoiceConfigPanel.vue'
import AsyncMarkdown from '../components/markdown/AsyncMarkdown.vue'
import * as echarts from 'echarts'
import PButton from '../components/ui/PButton.vue'
import PSwitch from '../components/ui/PSwitch.vue'
import PCard from '../components/ui/PCard.vue'
import PModal from '../components/ui/PModal.vue'
import PCheckbox from '../components/ui/PCheckbox.vue'
import PSlider from '../components/ui/PSlider.vue'
import PInputNumber from '../components/ui/PInputNumber.vue'
import PInput from '../components/ui/PInput.vue'
import PSelect from '../components/ui/PSelect.vue'
import PDatePicker from '../components/ui/PDatePicker.vue'
import PEmpty from '../components/ui/PEmpty.vue'
import PTextarea from '../components/ui/PTextarea.vue'
import PTooltip from '../components/ui/PTooltip.vue'
import PixelIcon from '../components/ui/PixelIcon.vue'
import TerminalPanel from '../components/terminal/TerminalPanel.vue'
import NapCatTerminal from '../components/terminal/NapCatTerminal.vue'
import logoImg from '../assets/logo.png'
import { gatewayClient } from '../api/gateway'

const menuGroups = [
  {
    title: null,
    items: [
      { id: 'overview', label: '总览', icon: 'desktop' },
      { id: 'logs', label: '对话日志', icon: 'chat' },
      { id: 'memories', label: '核心记忆', icon: 'brain' },
      { id: 'tasks', label: '待办任务', icon: 'list' }
    ]
  },
  {
    title: 'CONFIGURATION',
    items: [
      { id: 'user_settings', label: '用户设定', icon: 'user' },
      { id: 'model_config', label: '模型配置', icon: 'settings' },
      { id: 'voice_config', label: '语音功能', icon: 'mic' },
      { id: 'mcp_config', label: 'MCP 配置', icon: 'terminal' }
    ]
  },
  {
    title: 'SYSTEM',
    items: [
      { id: 'napcat', label: 'NapCat 终端', icon: 'terminal' },
      { id: 'terminal', label: '系统终端', icon: 'desktop' },
      { id: 'system_reset', label: '危险区域', icon: 'alert', variant: 'danger' }
    ]
  }
]

const providerOptions = [
  { label: 'OpenAI (兼容)', value: 'openai' },
  { label: 'Gemini (原生)', value: 'gemini' },
  { label: 'Claude (Anthropic)', value: 'anthropic' },
  { label: 'SiliconFlow (硅基流动)', value: 'siliconflow' },
  { label: 'DeepSeek (深度求索)', value: 'deepseek' },
  { label: 'Moonshot (Kimi)', value: 'moonshot' },
  { label: 'DashScope (阿里百炼)', value: 'dashscope' },
  { label: 'Volcengine (火山引擎)', value: 'volcengine' },
  { label: 'Groq', value: 'groq' },
  { label: 'Zhipu (智谱GLM)', value: 'zhipu' },
  { label: 'MiniMax', value: 'minimax' },
  { label: 'Mistral', value: 'mistral' },
  { label: '01.AI (零一万物)', value: 'yi' },
  { label: 'xAI (Grok)', value: 'xai' },
  { label: 'StepFun (阶跃星辰)', value: 'stepfun' },
  { label: 'Hunyuan (腾讯混元)', value: 'hunyuan' }
]

const mcpTypeOptions = [
  { label: 'Stdio (本地)', value: 'stdio' },
  { label: 'SSE (远程)', value: 'sse' }
]

// 为了防止在非 Tauri 环境下报错，定义一个 fallback 的 listen
const listenSafe = (event, callback) => {
  return listen(event, callback)
}

// --- 状态管理 ---
const currentTab = ref('overview')
const handleTabSelect = (index) => {
  if (currentTab.value === index) return
  currentTab.value = index
}
const isBackendOnline = ref(false)
const isSaving = ref(false)
const isGlobalRefreshing = ref(false)
const isCompanionEnabled = ref(false)
const isTogglingCompanion = ref(false)

// --- Particles Optimization ---
// --- 粒子优化 ---
const particles = ref([])
const initParticles = () => {
  particles.value = Array.from({ length: 12 }, (_, i) => ({
    id: i,
    style: {
      top: `${Math.random() * 100}%`,
      left: `${Math.random() * 100}%`,
      animationDelay: `${Math.random() * 5}s`,
      animationDuration: `${10 + Math.random() * 15}s`,
      willChange: 'transform, opacity' // 显式开启 GPU 加速
    },
    icon: i % 2 === 0 ? 'sparkle' : 'heart',
    size: i % 3 === 0 ? 'sm' : 'xs'
  }))
}

// Memory Config
const activeMemoryTab = ref('desktop')
const isSavingMemoryConfig = ref(false)
const memoryConfig = ref({
  modes: {
    desktop: { context_limit: 20, rag_limit: 10 },
    work: { context_limit: 50, rag_limit: 15 },
    social: {
      context_limit: 100,
      rag_limit: 10,
      advanced: {
        image_limit: 2,
        cross_context_users: 3,
        cross_context_history: 10
      }
    }
  }
})
const isCurrentModelVisionEnabled = computed(() => {
  if (!currentActiveModelId.value || !models.value.length) return false
  const activeModel = models.value.find((m) => m.id === currentActiveModelId.value)
  return activeModel ? !!activeModel.enable_vision : false
})
const isSocialEnabled = ref(false)
const isLightweightEnabled = ref(false)
const isTogglingLightweight = ref(false)
const isAuraVisionEnabled = ref(false)
const isTogglingAuraVision = ref(false)
const isLogsFetching = ref(false)
const isClearingEdges = ref(false)
const isScanningLonely = ref(false)
const isRunningMaintenance = ref(false)
const isDreaming = ref(false)
const showDebugDialog = ref(false)
const currentDebugLog = ref(null)
const debugSegments = ref([])
const currentPromptMessages = ref([])
const isLoadingPrompt = ref(false)

// --- Story Import ---
const showImportStoryDialog = ref(false)
const importStoryText = ref('')
const isImportingStory = ref(false)

const handleImportStory = async () => {
  if (!importStoryText.value.trim()) {
    window.$notify('请输入内容', 'warning')
    return
  }

  isImportingStory.value = true
  try {
    const response = await fetch(`${API_BASE}/memory/import_story`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        story: importStoryText.value,
        agent_id: activeAgent.value?.id || 'pero'
      })
    })

    if (!response.ok) {
      const errData = await response.json()
      throw new Error(errData.detail || 'Import failed')
    }

    const result = await response.json()
    window.$notify(`导入成功！共生成 ${result.count} 条记忆。`, 'success')
    showImportStoryDialog.value = false
    importStoryText.value = ''
    // Refresh memories if function exists
    if (typeof fetchMemories === 'function') {
      fetchMemories()
    } else {
      // Fallback: fetch all data
      fetchAllData(true)
    }
  } catch (error) {
    window.$notify(`导入失败: ${error.message}`, 'error')
  } finally {
    isImportingStory.value = false
  }
}

// --- Confirm Modal State ---
const showConfirmModal = ref(false)
const confirmModalTitle = ref('')
const confirmModalContent = ref('')
const confirmCallback = ref(null)
const confirmCancelCallback = ref(null)
const confirmType = ref('warning') // warning, info, error
const isPrompt = ref(false)
const promptValue = ref('')
const promptPlaceholder = ref('')

const openConfirm = (title, content, options = {}) => {
  return new Promise((resolve, reject) => {
    confirmModalTitle.value = title
    confirmModalContent.value = content
    confirmType.value = options.type || 'warning'
    isPrompt.value = !!options.isPrompt
    promptValue.value = options.inputValue || ''
    promptPlaceholder.value = options.inputPlaceholder || ''

    confirmCallback.value = () => {
      if (isPrompt.value) {
        resolve({ value: promptValue.value, action: 'confirm' })
      } else {
        resolve()
      }
      showConfirmModal.value = false
    }

    confirmCancelCallback.value = () => {
      reject(new Error('User cancelled'))
      showConfirmModal.value = false
    }

    showConfirmModal.value = true
  })
}

const handleConfirm = () => {
  if (confirmCallback.value) confirmCallback.value()
}

const handleCancel = () => {
  if (confirmCancelCallback.value) confirmCancelCallback.value()
}

// --- Auto Updater ---
const appVersion = ref('0.5.4')
const updateStatus = ref({ type: 'idle' })
const isCheckingUpdate = ref(false)

const checkForUpdates = async () => {
  if (isCheckingUpdate.value) return
  isCheckingUpdate.value = true
  try {
    await invoke('check_update')
  } catch {
    window.$notify('检查更新失败', 'error')
    isCheckingUpdate.value = false
  }
}

const handleUpdateMessage = (data) => {
  console.log('Update Status:', data)
  updateStatus.value = data

  switch (data.type) {
    case 'checking':
      isCheckingUpdate.value = true
      break
    case 'available':
      isCheckingUpdate.value = false
      openConfirm('发现新版本', `检测到新版本 v${data.info.version}，是否立即更新？`, {
        type: 'info'
      })
        .then(() => {
          invoke('download_update')
        })
        .catch(() => {})
      break
    case 'not-available':
      isCheckingUpdate.value = false
      window.$notify('当前已是最新版本', 'success')
      break
    case 'error':
      isCheckingUpdate.value = false
      window.$notify(`更新错误: ${data.error}`, 'error')
      break
    case 'progress':
      // Can show progress notification or toast
      break
    case 'downloaded':
      openConfirm('更新就绪', '更新已下载完毕，是否立即重启以安装？', {
        type: 'success'
      })
        .then(() => {
          invoke('quit_and_install')
        })
        .catch(() => {})
      break
  }
}

// --- API 交互 ---
const API_BASE = window.electron ? 'http://localhost:9120/api' : '/api'

// 带超时的 fetch 包装函数
const fetchWithTimeout = async (url, options = {}, timeout = 5000) => {
  const controller = new AbortController()
  const id = setTimeout(() => controller.abort(), timeout)
  try {
    const response = await fetch(url, {
      ...options,
      signal: controller.signal
    })
    clearTimeout(id)
    return response
  } catch (error) {
    clearTimeout(id)

    let errorMsg = error.message

    // [增强] 错误信息本地化与提示
    if (error.name === 'AbortError') {
      errorMsg = `请求超时 (${timeout}ms)`
    } else if (error.message === 'Failed to fetch') {
      errorMsg = '无法连接到后端服务。请检查后端是否已启动 (Failed to fetch)'
    } else if (error.message.includes('NetworkError')) {
      errorMsg = '网络连接错误'
    }

    // 只有未开启 silent 模式时才弹窗提示
    if (!options.silent) {
      window.$notify(errorMsg, 'error')

      if (error.name !== 'AbortError') {
        console.warn(`[Fetch] 请求失败 ${url}:`, error.message)
      }
    }

    throw error
  }
}

// [增强] LLM 错误信息格式化助手
const formatLLMError = (error) => {
  if (error.name === 'AbortError') return '请求超时 (Timeout)'

  const msg = error.message || error.toString()

  if (msg.includes('401') || msg.includes('invalid_api_key') || msg.includes('Incorrect API key')) {
    return 'API Key 无效，请检查配置 (401 Unauthorized)'
  }
  if (msg.includes('404') || msg.includes('model_not_found')) {
    return '请求的模型不存在或端点错误 (404 Not Found)'
  }
  if (msg.includes('429') || msg.includes('rate_limit') || msg.includes('insufficient_quota')) {
    return '请求过于频繁或余额不足 (429 Rate Limit)'
  }
  if (msg.includes('500') || msg.includes('internal_server_error')) {
    return '服务商服务器内部错误 (500 Internal Server Error)'
  }
  if (msg.includes('503') || msg.includes('service_unavailable')) {
    return '服务暂时不可用 (503 Service Unavailable)'
  }
  if (msg.includes('timeout') || msg.includes('timed out')) {
    return '请求超时，请检查网络或代理设置'
  }
  if (msg.includes('Failed to fetch')) {
    return '无法连接到服务器，请检查网络 (Failed to fetch)'
  }

  return msg // 返回原始错误作为兜底
}

// 模型配置相关
const models = ref([])
const showGlobalSettings = ref(false)
const showModelEditor = ref(false)
const remoteModels = ref([])
const isFetchingRemote = ref(false)
const currentEditingModel = ref({})
const providerDefaults = {
  siliconflow: 'https://api.siliconflow.cn/v1',
  deepseek: 'https://api.deepseek.com',
  moonshot: 'https://api.moonshot.cn/v1',
  dashscope: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
  volcengine: 'https://ark.cn-beijing.volces.com/api/v3',
  groq: 'https://api.groq.com/openai/v1',
  zhipu: 'https://open.bigmodel.cn/api/paas/v4',
  minimax: 'https://api.minimax.chat/v1',
  mistral: 'https://api.mistral.ai/v1',
  yi: 'https://api.lingyiwanwu.com/v1',
  xai: 'https://api.x.ai/v1',
  stepfun: 'https://api.stepfun.com/v1',
  hunyuan: 'https://api.hunyuan.cloud.tencent.com/v1'
}

const globalConfig = ref({ global_llm_api_key: '', global_llm_api_base: '', provider: '' })

// MCP 配置相关
const mcps = ref([])
const showMcpEditor = ref(false)
const currentEditingMcp = ref({})
const currentActiveModelId = ref(null)
const secretaryModelId = ref(null)
const reflectionModelId = ref(null)
const auxModelId = ref(null)

// --- Agents Management ---
// --- 助手管理 ---
const availableAgents = ref([])
const activeAgent = ref(null)
const isSwitchingAgent = ref(false)
const napCatStatus = ref({
  ws_connected: false,
  api_responsive: false,
  latency_ms: -1,
  disabled: false
})

const openDebugDialog = (log) => {
  currentDebugLog.value = log
  showDebugDialog.value = true
  debugViewMode.value = 'response' // Reset to default mode
  parseDebugContent(log.raw_content || log.content || '')
}

const debugViewMode = ref('response')
const totalPromptLength = computed(() => {
  return currentPromptMessages.value.reduce((acc, msg) => acc + (msg.content || '').length, 0)
})

const handleDebugModeChange = async (val) => {
  if (val === 'prompt' && currentDebugLog.value) {
    // Reuse the logic from openPromptDialog
    isLoadingPrompt.value = true
    currentPromptMessages.value = []

    try {
      const log = currentDebugLog.value
      const res = await fetchWithTimeout(
        `${API_BASE}/agents/preview_prompt`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            session_id: log.session_id || selectedSessionId.value || 'default',
            source: log.source || selectedSource.value || 'desktop',
            log_id: log.id
          }),
          silent: true
        },
        10000
      )

      if (res.ok) {
        const data = await res.json()
        currentPromptMessages.value = data.messages
      } else {
        const err = await res.json()
        throw new Error(err.detail || '获取提示词失败')
      }
    } catch (e) {
      window.$notify(formatLLMError(e), 'error')
    } finally {
      isLoadingPrompt.value = false
    }
  }
}

const parseDebugContent = (content) => {
  if (!content) {
    debugSegments.value = []
    return
  }

  // Regex patterns
  // 正则表达式模式
  const patterns = [
    { type: 'nit', regex: /\[\[\[NIT_CALL\]\]\][\s\S]*?\[\[\[NIT_END\]\]\]/gi },
    { type: 'nit', regex: /<(nit(?:-[0-9a-fA-F]{4})?)>[\s\S]*?<\/\1>/gi },
    { type: 'thinking', regex: /【Thinking[\s\S]*?】/gi },
    { type: 'thinking', regex: /<think>[\s\S]*?<\/think>/gi },
    { type: 'monologue', regex: /【Monologue[\s\S]*?】/gi }
  ]

  let matches = []

  patterns.forEach((p) => {
    let match
    const regex = new RegExp(p.regex)
    while ((match = regex.exec(content)) !== null) {
      matches.push({
        type: p.type,
        start: match.index,
        end: match.index + match[0].length,
        content: match[0]
      })
    }
  })

  matches.sort((a, b) => a.start - b.start)

  const uniqueMatches = []
  if (matches.length > 0) {
    let current = matches[0]
    uniqueMatches.push(current)

    for (let i = 1; i < matches.length; i++) {
      const next = matches[i]
      if (next.start >= current.end) {
        uniqueMatches.push(next)
        current = next
      }
    }
  }

  const segments = []
  let lastIndex = 0

  uniqueMatches.forEach((match) => {
    if (match.start > lastIndex) {
      segments.push({
        type: 'text',
        content: content.substring(lastIndex, match.start)
      })
    }
    segments.push({
      type: match.type,
      content: match.content
    })
    lastIndex = match.end
  })

  if (lastIndex < content.length) {
    segments.push({
      type: 'text',
      content: content.substring(lastIndex)
    })
  }

  debugSegments.value = segments
}

const formatLogContent = (content) => {
  if (!content) return ''
  // Hide Thinking and Monologue blocks (but keep them in raw data)
  // 隐藏 Thinking 和 Monologue 块（但在原始数据中保留它们）
  // [兼容性保留] Monologue 为旧版格式，此处保留过滤以确保 UI 清洁
  return content.replace(/【(Thinking|Monologue)[\s\S]*?】/gi, '')
}

// 编辑日志状态
const editingLogId = ref(null)
const editingContent = ref('')

// 数据源
const memories = shallowRef([])
const logs = shallowRef([])
const tasks = shallowRef([])
const stats = ref({ total_memories: 0, total_logs: 0, total_tasks: 0 })
const petState = ref({})

// 🎨 背景氛围灯样式，随心情动态变化
const ambientLightStyle = computed(() => {
  const mood = petState.value?.mood || 'neutral'
  const colors = {
    happy: { primary: 'rgba(252, 165, 165, 0.2)', secondary: 'rgba(253, 224, 71, 0.15)' },
    sad: { primary: 'rgba(96, 165, 250, 0.2)', secondary: 'rgba(165, 180, 252, 0.15)' },
    angry: { primary: 'rgba(244, 63, 94, 0.2)', secondary: 'rgba(253, 186, 116, 0.15)' },
    surprised: { primary: 'rgba(192, 132, 252, 0.2)', secondary: 'rgba(240, 171, 252, 0.15)' },
    neutral: { primary: 'rgba(125, 211, 252, 0.2)', secondary: 'rgba(153, 246, 228, 0.15)' }
  }

  const color = colors[mood] || colors.neutral

  return {
    background: `radial-gradient(circle at 20% 30%, ${color.primary} 0%, transparent 70%),
                radial-gradient(circle at 80% 70%, ${color.secondary} 0%, transparent 70%)`,
    filter: 'blur(100px)',
    opacity: 0.8
  }
})
const userSettings = ref({
  owner_name: '主人',
  user_persona: '未设定',
  owner_qq: ''
})

// 筛选条件
const selectedSource = ref('all')
const selectedSessionId = ref('all')
const lastSyncedSessionId = ref(null) // Track last synced session from backend to prevent UI fighting
const selectedDate = ref('')
const selectedSort = ref('desc')

// --- Polling State ---
// --- 轮询状态 ---
const pollingInterval = ref(null)

// --- Refactored Memory Dashboard State ---
// --- 重构的记忆仪表板状态 ---
const nitStatus = ref(null)
const memoryViewMode = ref('list') // 'list' or 'graph'
// 'list' (列表) 或 'graph' (图谱)
const memoryGraphData = shallowRef({ nodes: [], edges: [] })
const tagCloud = ref({})
const memoryFilterTags = ref([])
const memoryFilterDate = ref(null)
const memoryFilterType = ref('') // New type filter
// 新的类型筛选
const isLoadingGraph = ref(false)
const graphRef = ref(null)
let chartInstance = null
let resizeHandler = null

watch(memoryViewMode, (val) => {
  if (val === 'graph') {
    nextTick(() => {
      if (memoryGraphData.value.nodes.length > 0) {
        initGraph()
      } else {
        fetchMemoryGraph()
      }
    })
  } else {
    // Dispose chart when switching back to list mode to save memory
    // 切换回列表模式时销毁图表以节省内存
    if (chartInstance) {
      chartInstance.dispose()
      chartInstance = null
    }
  }
})

// 监听标签页切换，动态加载数据
watch(currentTab, (newTab) => {
  if (newTab === 'logs') {
    // 每次切换到日志页都重新拉取，确保看到最新消息
    initSessionAndFetchLogs()
  } else if (newTab === 'memories') {
    if (memories.value.length === 0) {
      fetchMemories()
    }
  } else if (newTab === 'tasks') {
    if (tasks.value.length === 0) {
      fetchTasks()
    }
  }

  // Dispose graph when leaving memories tab
  // 离开记忆标签页时销毁图谱
  if (newTab !== 'memories' && chartInstance) {
    chartInstance.dispose()
    chartInstance = null
  }
})

// 监听日志筛选条件变化
watch([selectedSessionId, selectedSource, selectedSort, selectedDate], () => {
  if (currentTab.value === 'logs') {
    fetchLogs()
  }
})

// Watch active agent change to refresh data
// 监听活跃助手变化以刷新数据
watch(activeAgent, () => {
  // Clear existing data to force refresh
  // 清除现有数据以强制刷新
  memories.value = []
  logs.value = []
  tasks.value = []

  fetchStats() // Update overview stats
  // 更新概览统计

  if (currentTab.value === 'logs') fetchLogs()
  else if (currentTab.value === 'memories') fetchMemories()
  else if (currentTab.value === 'tasks') fetchTasks()
})

const topTags = computed(() => {
  if (!tagCloud.value) return []
  if (Array.isArray(tagCloud.value)) {
    return tagCloud.value
  }
  return Object.entries(tagCloud.value)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 15)
    .map(([tag, count]) => ({ tag, count }))
})

const getMemoryTypeLabel = (type) => {
  const map = {
    event: '🧩 记忆块',
    preference: '💖 偏好',
    summary: '🧩 记忆块',
    interaction_summary: '🧩 记忆块',
    archived_event: '🗄️ 归档',
    fact: '🧠 事实',
    promise: '🤝 誓言',
    work_log: '📝 工作日志'
  }
  return map[type] || type
}

const getSentimentEmoji = (sentiment) => {
  if (!sentiment) return 'mood-neutral'
  const map = {
    positive: 'mood-happy',
    negative: 'mood-sad',
    neutral: 'mood-neutral',
    happy: 'mood-happy',
    sad: 'mood-sad',
    angry: 'mood-angry',
    excited: 'mood-excited'
  }
  return map[sentiment.toLowerCase()] || 'mood-neutral'
}

const getSentimentLabel = (sentiment) => {
  if (!sentiment) return '平静'
  const map = {
    positive: '开心',
    negative: '忧郁',
    neutral: '平静',
    happy: '开心',
    sad: '忧郁',
    angry: '愤怒',
    excited: '激动'
  }
  return map[sentiment.toLowerCase()] || sentiment
}

const getLogMetadata = (log) => {
  if (!log) return {}
  try {
    return JSON.parse(log.metadata_json || '{}')
  } catch {
    return {}
  }
}

const fetchAgents = async () => {
  try {
    const res = await fetchWithTimeout(`${API_BASE}/agents`, {}, 2000)
    if (res.ok) {
      const agents = await res.json()
      availableAgents.value = agents
      const active = agents.find((a) => a.is_active)
      if (active) {
        activeAgent.value = active
      }
    }
  } catch (e) {
    console.error('获取助手列表失败:', e)
  }
}

const switchAgent = async (agentId) => {
  if (isSwitchingAgent.value || agentId === activeAgent.value?.id) return
  isSwitchingAgent.value = true
  try {
    // 1. Call API to switch active agent
    const res = await fetchWithTimeout(
      `${API_BASE}/agents/active`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ agent_id: agentId })
      },
      5000
    )

    if (!res.ok) {
      const err = await res.json()
      throw new Error(err.detail || 'Failed to switch agent')
    }

    // 2. Refresh list to update UI
    await fetchAgents()
    window.$notify(`已切换到角色: ${activeAgent.value?.name}`, 'success')

    // 3. Persist to launch config via Electron IPC (Fire and forget)
    // 3. 通过 Electron IPC 持久化启动配置（即发即弃）
    // Get current enabled list
    // 获取当前已启用的列表
    const enabled = availableAgents.value.filter((a) => a.is_enabled).map((a) => a.id)
    invoke('save_global_launch_config', {
      enabledAgents: enabled,
      activeAgent: agentId
    }).catch((e) => console.error('保存启动配置失败:', e))
  } catch (e) {
    window.$notify(e.message, 'error')
  } finally {
    isSwitchingAgent.value = false
  }
}

// --- Methods ---

const waitForBackend = async () => {
  // 启动时的轮询等待
  const maxRetries = 60 // 等待60秒
  let retries = 0

  const check = async () => {
    try {
      // 启动检测静默处理，避免控制台刷屏报错
      const res = await fetchWithTimeout(`${API_BASE}/pet/state`, { silent: true }, 2000)
      if (res.ok) {
        isBackendOnline.value = true
        await fetchAllData(true) // 后端上线后，拉取所有数据
        fetchMemoryConfig() // 拉取记忆配置
        return
      }
    } catch {
      // 忽略启动时的连接错误，静默重试
    }

    if (retries < maxRetries) {
      retries++
      isBackendOnline.value = false
      setTimeout(check, 1000)
    } else {
      window.$notify('无法连接到 Pero 后端，请检查后台进程是否运行。', 'error')
    }
  }

  check()
}

// [Feature] Listen for new messages via Gateway

onMounted(() => {
  initParticles() // Initialize particles with fixed random values
  waitForBackend() // 启动检测

  // [Fix] Only connect gateway when backend is confirmed online
  // Avoid log spamming during initial startup phase
  watch(
    isBackendOnline,
    (online) => {
      if (online) {
        console.log('[Dashboard] Backend online, connecting to Gateway...')
        gatewayClient.connect()
      }
    },
    { immediate: false }
  )

  // [Fix] Listen for agent changes to refresh all data
  gatewayClient.on('action:agent_changed', (payload) => {
    const agentId = payload.agent_id || (payload.params && payload.params.agent_id)
    if (agentId) {
      console.log('[Dashboard] Detected agent change:', agentId)
      // Refresh active agent info first
      fetchAgents().then(() => {
        // Then refresh all data dependent on agent
        fetchAllData(true)
      })
    }
  })

  gatewayClient.on('action:new_message', (payload) => {
    // Only update if logs tab is active or we want to update stats
    if (currentTab.value === 'logs') {
      // Check if log belongs to current view filter (session/agent)
      // Ideally we check payload.session_id and payload.agent_id

      // For now, just prepend to logs if it's not a duplicate
      const exists = logs.value.some((l) => l.id == payload.id)
      if (!exists) {
        // Construct log object compatible with UI
        const newLog = {
          id: payload.id,
          role: payload.role,
          content: payload.content,
          timestamp: payload.timestamp,
          displayTime: new Date(payload.timestamp).toLocaleString(),
          agent_id: payload.agent_id,
          session_id: payload.session_id,
          metadata: JSON.parse(payload.metadata || '{}'),
          // Default values for other fields
          sentiment: 'neutral',
          importance: 1,
          analysis_status: 'pending'
        }

        // Add to list
        logs.value.unshift(newLog)

        // Update stats locally
        stats.value.total_logs = (stats.value.total_logs || 0) + 1
      }
    }
  })
})

const fetchStats = async () => {
  try {
    let url = `${API_BASE}/stats/overview`
    if (activeAgent.value) {
      url += `?agent_id=${activeAgent.value.id}`
    }
    const res = await fetchWithTimeout(url, {}, 2000)
    const data = await res.json()
    stats.value = data
  } catch {
    console.error('获取统计信息失败')
  }
}

const fetchAllData = async (silent = false) => {
  if (!isBackendOnline.value || isGlobalRefreshing.value) return

  isGlobalRefreshing.value = true
  // 1. 先加载核心状态，确保 UI 基础信息立即可用
  try {
    await Promise.all([fetchPetState(), fetchConfig(), fetchStats(), fetchAgents()])
  } catch {
    console.error('核心数据获取错误')
  }

  // 2. 稍微延迟后加载次要配置，避免一次性涌入过多数据更新
  setTimeout(async () => {
    try {
      await Promise.all([
        fetchModels(),
        fetchMcps(),
        fetchCompanionStatus(),
        fetchSocialStatus(),
        fetchLightweightStatus(),
        fetchAuraVisionStatus(),
        fetchNitStatus()
      ])
    } catch {
      console.error('次要数据获取错误')
    }
  }, 100)

  // 3. 顺序加载所有标签页数据，确保 v-show 切换时内容已就绪
  setTimeout(async () => {
    try {
      // 1. 优先加载当前标签页数据
      if (currentTab.value === 'logs') await initSessionAndFetchLogs()
      if (currentTab.value === 'memories') await fetchMemories()
      if (currentTab.value === 'tasks') await fetchTasks()

      // 2. 异步加载其他标签页数据 (不使用 await 阻塞)
      if (currentTab.value !== 'logs') initSessionAndFetchLogs()
      if (currentTab.value !== 'memories') fetchMemories()
      if (currentTab.value !== 'tasks') fetchTasks()

      fetchTagCloud()
      if (!silent) {
        window.$notify('所有数据已同步', 'success')
      }
    } catch {
      console.error('标签页数据获取错误')
      if (!silent) {
        window.$notify('部分数据刷新失败', 'error')
      }
    } finally {
      isGlobalRefreshing.value = false
    }
  }, 200)
}

const fetchNitStatus = async () => {
  if (fetchNitStatus.isLoading) return
  fetchNitStatus.isLoading = true
  try {
    const res = await fetchWithTimeout(`${API_BASE}/nit/status`, {}, 2000)
    nitStatus.value = await res.json()
  } catch {
    console.error('NIT 状态获取错误')
  } finally {
    fetchNitStatus.isLoading = false
  }
}

const fetchTagCloud = async () => {
  if (fetchTagCloud.isLoading) return
  fetchTagCloud.isLoading = true
  try {
    const res = await fetchWithTimeout(`${API_BASE}/memories/tags`, {}, 3000)
    tagCloud.value = await res.json()
  } catch {
    console.error('标签云获取错误')
  } finally {
    fetchTagCloud.isLoading = false
  }
}

const fetchMemoryGraph = async () => {
  if (isLoadingGraph.value) return
  try {
    isLoadingGraph.value = true
    // 降低限制到 100 以提升性能，防止大规模节点渲染导致主线程阻塞
    let url = `${API_BASE}/memories/graph?limit=100`
    if (activeAgent.value) {
      url += `&agent_id=${activeAgent.value.id}`
    }
    const res = await fetchWithTimeout(url, {}, 8000)
    const data = await res.json()

    // 确保在数据拉取后，且仍然在 memory 标签页时才初始化图表
    if (currentTab.value === 'memories') {
      memoryGraphData.value = Object.freeze(data) // 冻结数据以避免 Vue 响应式开销 // 冻结数据以避免 Vue 响应式开销
      nextTick(() => {
        requestAnimationFrame(() => initGraph())
      })
    }
  } catch {
    console.error('记忆图谱获取错误')
  } finally {
    isLoadingGraph.value = false
  }
}

const clearOrphanedEdges = async () => {
  if (isClearingEdges.value) return
  try {
    await openConfirm('清理确认', '确定要清理数据库中所有无效的连线吗？这不会删除任何记忆节点。', {
      type: 'warning'
    })

    isClearingEdges.value = true
    const res = await fetchWithTimeout(
      `${API_BASE}/memories/orphaned_edges`,
      {
        method: 'DELETE'
      },
      10000
    )
    const data = await res.json()

    window.$notify(`清理完成，共移除 ${data.deleted_count} 条无效连线`, 'success')

    // Refresh graph if in graph mode
    // 如果在图谱模式下，刷新图谱
    if (memoryViewMode.value === 'graph') {
      fetchMemoryGraph()
    }
  } catch (e) {
    if (e.message !== 'User cancelled') {
      console.error('清理孤立连线错误:', e)
      window.$notify('清理失败: ' + e.message, 'error')
    }
  } finally {
    isClearingEdges.value = false
  }
}

const triggerScanLonely = async () => {
  if (isScanningLonely.value) return
  isScanningLonely.value = true
  try {
    const res = await fetchWithTimeout(`${API_BASE}/memories/scan_lonely?limit=5`, {
      method: 'POST'
    })
    const data = await res.json()
    if (data.status === 'success') {
      window.$notify(
        `扫描完成: 处理了 ${data.processed_count} 条记忆，发现了 ${data.connections_found} 个新关联`,
        'success'
      )
      fetchMemories() // Refresh list
      // 刷新列表
    } else if (data.status === 'skipped') {
      window.$notify(`扫描跳过: ${data.reason}`, 'warning')
    } else {
      window.$notify('扫描失败', 'error')
    }
  } catch (e) {
    console.error(e)
    window.$notify('请求出错: ' + e.message, 'error')
  } finally {
    isScanningLonely.value = false
  }
}

const triggerMaintenance = async () => {
  if (isRunningMaintenance.value) return
  try {
    await openConfirm(
      '执行确认',
      '深度维护可能需要较长时间，且会消耗一定的 Tokens。确定要立即执行吗？',
      {
        type: 'info'
      }
    )

    isRunningMaintenance.value = true
    const res = await fetchWithTimeout(
      `${API_BASE}/memories/maintenance`,
      {
        method: 'POST'
      },
      120000
    ) // Longer timeout for deep maintenance
    // 深度维护需要更长的超时时间
    const data = await res.json()
    if (data.status === 'success') {
      window.$notify(
        `维护完成: 标记重要性 ${data.important_tagged}, 记忆合并 ${data.consolidated}, 清理 ${data.cleaned_count}`,
        'success'
      )
      fetchMemories()
    } else {
      window.$notify(data.error || '维护失败', 'error')
    }
  } catch (e) {
    if (e.message !== 'User cancelled') {
      console.error(e)
      window.$notify('请求出错: ' + e.message, 'error')
    }
  } finally {
    isRunningMaintenance.value = false
  }
}

const triggerDream = async () => {
  if (isDreaming.value) return
  try {
    await openConfirm('执行确认', '梦境联想将扫描近期记忆并尝试建立新的关联。确定要执行吗？', {
      type: 'info'
    })

    isDreaming.value = true
    const res = await fetchWithTimeout(
      `${API_BASE}/memories/dream?limit=10`,
      {
        method: 'POST'
      },
      60000
    )
    const data = await res.json()
    if (data.status === 'success') {
      window.$notify(
        `梦境完成: 扫描 ${data.anchors_processed} 个锚点，发现 ${data.new_relations} 个新关联`,
        'success'
      )
      if (memoryViewMode.value === 'graph') fetchMemoryGraph()
    } else if (data.status === 'skipped') {
      window.$notify(`梦境跳过: ${data.reason}`, 'warning')
    } else {
      window.$notify('联想失败', 'error')
    }
  } catch (e) {
    if (e.message !== 'User cancelled') {
      console.error('梦境联想请求错误:', e)
      window.$notify('请求出错: ' + e.message, 'error')
    }
  } finally {
    isDreaming.value = false
  }
}

const initGraph = () => {
  if (!graphRef.value) return
  if (chartInstance) chartInstance.dispose()

  chartInstance = echarts.init(graphRef.value, null, { renderer: 'canvas' })

  const nodes = memoryGraphData.value.nodes.map((node) => ({
    ...node,
    name: String(node.id),
    category: getMemoryTypeLabel(node.category),
    symbolSize: Math.min(Math.max(node.value * 5, 15), 40), // 动态大小
    itemStyle: {
      color: getSentimentColor(node.sentiment),
      borderColor: '#fff',
      borderWidth: 2,
      shadowBlur: 15,
      shadowColor: getSentimentColor(node.sentiment)
    },
    label: {
      show: node.value > 5, // 仅重要节点显示标签
      fontSize: 10,
      color: '#64748b'
    }
  }))

  const links = memoryGraphData.value.edges.map((edge) => ({
    ...edge,
    lineStyle: {
      width: Math.max(edge.value * 0.5, 1),
      curveness: 0.2,
      color: '#e2e8f0' // slate-200
    }
  }))

  const categories = [...new Set(nodes.map((n) => n.category))].map((c) => ({ name: c }))

  const option = {
    backgroundColor: 'transparent', // 透明背景，透出应用底色
    title: {
      text: '✨ 核心记忆星云 ✨',
      subtext: 'Core Memory Nebula',
      top: '5%',
      left: 'center',
      textStyle: {
        color: '#8b5cf6', // violet-500
        fontSize: 20,
        fontWeight: 'bolder',
        fontFamily: "'Segoe UI Emoji', sans-serif"
      },
      subtextStyle: {
        color: '#cbd5e1'
      }
    },
    tooltip: {
      trigger: 'item',
      backgroundColor: 'rgba(255, 255, 255, 0.9)',
      borderColor: '#e2e8f0',
      borderWidth: 1,
      textStyle: { color: '#334155' },
      extraCssText: 'box-shadow: 0 8px 24px rgba(149, 157, 165, 0.2); border-radius: 16px;',
      formatter: (params) => {
        if (params.dataType === 'node') {
          const d = params.data
          const emoji = getSentimentEmoji(d.sentiment)
          return `
            <div style="padding: 4px;">
              <div style="font-weight:900; margin-bottom:6px; font-size:14px; color:#475569;">
                 ${emoji} 记忆片段 #${d.id}
              </div>
              <div style="font-size:13px; color:#64748b; margin-bottom:8px; line-height:1.5;">
                ${d.full_content.substring(0, 60)}${d.full_content.length > 60 ? '...' : ''}
              </div>
              <div style="display:flex; gap:8px; font-size:10px;">
                <span style="background:#f1f5f9; color:#64748b; padding:2px 6px; border-radius:4px;">${d.category}</span>
                <span style="background:#fff1f2; color:#e11d48; padding:2px 6px; border-radius:4px;">❤️ ${d.value}</span>
                <span style="background:#ecfeff; color:#0891b2; padding:2px 6px; border-radius:4px;">🔥 ${d.access_count}</span>
              </div>
            </div>
          `
        } else {
          return `
            <div style="padding: 4px;">
              <div style="font-weight:bold; color:#64748b; font-size:12px;">🔗 关联强度: ${params.data.value}</div>
              <div style="font-size:11px; color:#94a3b8;">${params.data.relation_type}</div>
            </div>
          `
        }
      }
    },
    legend: {
      data: categories.map((a) => a.name),
      bottom: '5%',
      left: 'center',
      icon: 'circle',
      itemWidth: 8,
      itemHeight: 8,
      textStyle: { color: '#64748b', fontSize: 11 }
    },
    series: [
      {
        type: 'graph',
        layout: 'force',
        data: nodes,
        links: links,
        categories: categories,
        roam: true,
        draggable: true,
        label: {
          show: true,
          position: 'bottom',
          formatter: '{b}',
          color: '#64748b',
          fontSize: 10
        },
        force: {
          repulsion: 250,
          gravity: 0.08,
          edgeLength: [60, 150],
          layoutAnimation: true,
          friction: 0.6
        },
        emphasis: {
          focus: 'adjacency',
          scale: true,
          itemStyle: {
            shadowBlur: 20,
            shadowColor: 'rgba(0,0,0,0.2)'
          }
        }
      }
    ]
  }

  chartInstance.setOption(option)

  // Resize handler
  if (resizeHandler) window.removeEventListener('resize', resizeHandler)
  resizeHandler = () => chartInstance && chartInstance.resize()
  window.addEventListener('resize', resizeHandler)
}

// Helper for colors
// 颜色助手
const getSentimentColor = (sentiment) => {
  const map = {
    positive: '#38bdf8', // sky-400
    negative: '#fb7185', // rose-400
    neutral: '#94a3b8', // slate-400
    happy: '#fbbf24', // amber-400
    sad: '#818cf8', // indigo-400
    angry: '#f87171', // red-400
    excited: '#e879f9' // fuchsia-400
  }
  return map[sentiment] || '#38bdf8'
}

const fetchCompanionStatus = async () => {
  try {
    const res = await fetchWithTimeout(`${API_BASE}/companion/status`, {}, 2000)
    if (res.ok) {
      const data = await res.json()
      isCompanionEnabled.value = data.enabled
    }
  } catch (e) {
    console.error('Failed to fetch companion status', e)
  }
}

const toggleCompanion = async (val) => {
  try {
    isTogglingCompanion.value = true
    const res = await fetchWithTimeout(
      `${API_BASE}/companion/toggle`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled: val })
      },
      5000
    )

    if (res.ok) {
      const data = await res.json()
      isCompanionEnabled.value = data.enabled
      window.$notify(data.enabled ? '已开启陪伴模式' : '已关闭陪伴模式', 'success')
    } else {
      const errorData = await res.json()
      isCompanionEnabled.value = !val // revert // 恢复
      window.$notify(errorData.detail || '切换失败', 'warning')
    }
  } catch {
    isCompanionEnabled.value = !val // revert // 恢复
    window.$notify('网络错误', 'error')
  } finally {
    isTogglingCompanion.value = false
  }
}

const fetchSocialStatus = async () => {
  try {
    const res = await fetchWithTimeout(`${API_BASE}/social/status`, {}, 2000)
    if (res.ok) {
      const data = await res.json()
      isSocialEnabled.value = data.enabled
    }
  } catch {
    console.error('Failed to fetch social status')
  }
}

const fetchLightweightStatus = async () => {
  try {
    const res = await fetchWithTimeout(`${API_BASE}/config/lightweight_mode`, {}, 2000)
    if (res.ok) {
      const data = await res.json()
      isLightweightEnabled.value = data.enabled
    }
  } catch {
    console.error('Failed to fetch lightweight status')
  }
}

const toggleLightweight = async (val) => {
  try {
    isTogglingLightweight.value = true
    const res = await fetchWithTimeout(
      `${API_BASE}/config/lightweight_mode`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled: val })
      },
      5000
    )

    if (res.ok) {
      const data = await res.json()
      isLightweightEnabled.value = data.enabled
      window.$notify(data.enabled ? '已开启轻量聊天模式' : '已关闭轻量聊天模式', 'success')
    } else {
      isLightweightEnabled.value = !val // revert // 恢复
      window.$notify('切换失败', 'error')
    }
  } catch {
    isLightweightEnabled.value = !val // revert // 恢复
    window.$notify('网络错误', 'error')
  } finally {
    isTogglingLightweight.value = false
  }
}

const fetchAuraVisionStatus = async () => {
  try {
    const res = await fetchWithTimeout(`${API_BASE}/config/aura_vision`, {}, 3000)
    if (res.ok) {
      const data = await res.json()
      isAuraVisionEnabled.value = data.enabled
    }
  } catch (e) {
    console.error('Failed to fetch AuraVision status', e)
  }
}

const toggleAuraVision = async (val) => {
  try {
    isTogglingAuraVision.value = true
    const res = await fetchWithTimeout(
      `${API_BASE}/config/aura_vision`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled: val })
      },
      5000
    )

    if (res.ok) {
      const data = await res.json()
      isAuraVisionEnabled.value = data.enabled
      window.$notify(
        data.enabled ? '已开启主动视觉感应 (AuraVision)' : '已关闭主动视觉感应 (AuraVision)',
        'success'
      )
    } else {
      isAuraVisionEnabled.value = !val // revert // 恢复
      window.$notify('切换失败', 'error')
    }
  } catch {
    isAuraVisionEnabled.value = !val // revert // 恢复
    window.$notify('网络错误', 'error')
  } finally {
    isTogglingAuraVision.value = false
  }
}

// 退出程序
const handleQuitApp = async () => {
  try {
    await openConfirm(
      '退出 萌动链接：PeroperoChat！',
      '确定要关闭 Peropero 并退出所有相关程序吗？',
      {
        type: 'warning'
      }
    )
    await invoke('quit_app')
  } catch (e) {
    if (e.message !== 'User cancelled') {
      console.error('Failed to quit app', e)
    }
  }
}

const fetchMemoryConfig = async () => {
  try {
    const res = await fetchWithTimeout(`${API_BASE}/config/memory`, {}, 3000)
    if (res.ok) {
      const data = await res.json()
      if (data && data.modes) {
        memoryConfig.value = data
      }
    }
  } catch (e) {
    console.error('Failed to fetch memory config:', e)
  }
}

const fetchMcps = async () => {
  if (fetchMcps.isLoading) return
  fetchMcps.isLoading = true
  try {
    const res = await fetchWithTimeout(`${API_BASE}/mcp`, {}, 5000)
    mcps.value = await res.json()
  } catch {
    console.error('Failed to fetch MCPs')
  } finally {
    fetchMcps.isLoading = false
  }
}

const fetchPetState = async () => {
  if (fetchPetState.isPolling) return
  try {
    if (!isBackendOnline.value) return
    fetchPetState.isPolling = true
    let url = `${API_BASE}/pet/state`
    if (activeAgent.value) {
      url += `?agent_id=${activeAgent.value.id}`
    }
    const res = await fetchWithTimeout(url, {}, 2000)
    if (res.ok) {
      petState.value = await res.json()
    }
  } catch {
    // Silent fail for polling, no need to log Failed to fetch
    // 轮询静默失败，无需记录获取失败
  } finally {
    fetchPetState.isPolling = false
  }
}

const fetchMemories = async () => {
  if (fetchMemories.isLoading) return
  fetchMemories.isLoading = true

  const currentRequestId = Symbol('fetchMemories')
  fetchMemories.lastRequestId = currentRequestId

  try {
    let url = `${API_BASE}/memories/list?limit=1000`
    if (memoryFilterDate.value) {
      url += `&date_start=${memoryFilterDate.value}`
    }
    if (memoryFilterType.value) {
      url += `&type=${memoryFilterType.value}`
    }
    if (memoryFilterTags.value.length > 0) {
      url += `&tags=${memoryFilterTags.value.join(',')}`
    }
    // Add active agent filter
    // 添加活动助手过滤器
    if (activeAgent.value) {
      url += `&agent_id=${activeAgent.value.id}`
    }
    const res = await fetchWithTimeout(url, {}, 5000)
    const rawMemories = await res.json()

    // Process in larger batches to reduce Vue churn
    // 分批处理以减少 Vue 抖动
    const processedMemories = []
    const batchSize = 50

    const processBatch = (startIndex) => {
      if (fetchMemories.lastRequestId !== currentRequestId) {
        fetchMemories.isLoading = false
        return
      }

      const endIndex = Math.min(startIndex + batchSize, rawMemories.length)
      for (let i = startIndex; i < endIndex; i++) {
        const m = rawMemories[i]
        processedMemories.push(
          Object.freeze({
            ...m,
            realTime: new Date(m.timestamp).toLocaleDateString()
          })
        )
      }

      memories.value = [...processedMemories]

      if (endIndex < rawMemories.length) {
        setTimeout(() => processBatch(endIndex), 16) // Use 16ms to allow one frame of UI response // 使用 16ms 允许一帧 UI 响应
      } else {
        fetchMemories.isLoading = false
      }
    }

    processBatch(0)
    fetchTagCloud()
  } catch (e) {
    console.error(e)
    fetchMemories.isLoading = false
  }
}

const fetchTasks = async () => {
  if (fetchTasks.isLoading) return
  fetchTasks.isLoading = true

  const currentRequestId = Symbol('fetchTasks')
  fetchTasks.lastRequestId = currentRequestId

  try {
    let url = `${API_BASE}/tasks`
    // Add active agent filter
    // 添加活动助手过滤器
    if (activeAgent.value) {
      url += `?agent_id=${activeAgent.value.id}`
    }
    const res = await fetchWithTimeout(url, {}, 5000)
    const rawTasks = await res.json()

    // Process all at once if count is small (< 100), otherwise batch
    // 如果数量较小 (< 100)，则一次性处理，否则分批处理
    if (rawTasks.length < 100) {
      tasks.value = rawTasks.map((t) => Object.freeze(t))
      fetchTasks.isLoading = false
      return
    }

    const processedTasks = []
    const batchSize = 20

    const processBatch = (startIndex) => {
      if (fetchTasks.lastRequestId !== currentRequestId) {
        fetchTasks.isLoading = false
        return
      }

      const endIndex = Math.min(startIndex + batchSize, rawTasks.length)
      for (let i = startIndex; i < endIndex; i++) {
        processedTasks.push(Object.freeze(rawTasks[i]))
      }

      tasks.value = [...processedTasks]

      if (endIndex < rawTasks.length) {
        setTimeout(() => processBatch(endIndex), 16)
      } else {
        fetchTasks.isLoading = false
      }
    }

    processBatch(0)
  } catch (e) {
    console.error(e)
    fetchTasks.isLoading = false
  }
}

const fetchConfig = async () => {
  try {
    const res = await fetchWithTimeout(`${API_BASE}/configs`, { silent: true }, 5000)
    if (!res.ok) {
      throw new Error(`Status ${res.status}: ${res.statusText}`)
    }
    const data = await res.json()
    globalConfig.value.global_llm_api_key = data.global_llm_api_key || ''
    globalConfig.value.global_llm_api_base = data.global_llm_api_base || 'https://api.openai.com'

    // Infer provider from base URL
    // 从 base URL 推断服务商
    const foundProvider = Object.keys(providerDefaults).find(
      (key) => providerDefaults[key] === globalConfig.value.global_llm_api_base
    )
    if (foundProvider) {
      globalConfig.value.provider = foundProvider
    } else if (globalConfig.value.global_llm_api_base.includes('api.openai.com')) {
      globalConfig.value.provider = 'openai'
    } else {
      globalConfig.value.provider = ''
    }

    currentActiveModelId.value = data.current_model_id ? parseInt(data.current_model_id) : null
    secretaryModelId.value = data.scorer_model_id ? parseInt(data.scorer_model_id) : null
    reflectionModelId.value = data.reflection_model_id ? parseInt(data.reflection_model_id) : null
    auxModelId.value = data.aux_model_id ? parseInt(data.aux_model_id) : null

    // 加载用户设定
    userSettings.value.owner_name = data.owner_name || '主人'
    userSettings.value.user_persona = data.user_persona || '未设定'
    userSettings.value.owner_qq = data.owner_qq || ''

    // [Fix] Sync current session ID if in Work Mode
    // [修复] 如果在工作模式下，同步当前会话 ID
    // Only sync if the backend value is different from what we last synced,
    // 仅当后端值与我们要同步的值不同时才同步，
    // to avoid overwriting user's manual selection in the dropdown.
    // 以避免覆盖用户在下拉列表中手动选择的内容。
    if (data.current_session_id && data.current_session_id !== 'default') {
      if (data.current_session_id !== lastSyncedSessionId.value) {
        selectedSessionId.value = data.current_session_id
        lastSyncedSessionId.value = data.current_session_id
      }
    } else {
      // If backend is default, we can clear our tracking so if it switches to work again, we sync
      // 如果后端是默认值，我们可以清除跟踪，以便再次切换到工作模式时进行同步
      lastSyncedSessionId.value = null
    }
  } catch (e) {
    console.error(e)
    window.$notify('获取配置失败: ' + formatLLMError(e), 'error')
  }
}

const fetchModels = async () => {
  if (fetchModels.isLoading) return
  fetchModels.isLoading = true
  try {
    const res = await fetchWithTimeout(`${API_BASE}/models`, { silent: true }, 5000)
    if (!res.ok) {
      throw new Error(`Status ${res.status}: ${res.statusText}`)
    }
    models.value = await res.json()
  } catch (e) {
    console.error(e)
    window.$notify('获取模型列表失败: ' + formatLLMError(e), 'error')
  } finally {
    fetchModels.isLoading = false
  }
}

// 设置主模型
const setActiveModel = async (id) => {
  const isCurrentlyActive = currentActiveModelId.value === id
  const targetId = isCurrentlyActive ? '' : String(id)

  try {
    const res = await fetchWithTimeout(
      `${API_BASE}/configs`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ current_model_id: targetId }),
        silent: true
      },
      5000
    )
    if (!res.ok) throw new Error(isCurrentlyActive ? '取消主模型失败' : '设置主模型失败')
    currentActiveModelId.value = isCurrentlyActive ? null : id
    window.$notify(isCurrentlyActive ? '主模型配置已取消' : '主模型已更新', 'success')
  } catch (e) {
    window.$notify(formatLLMError(e), 'error')
  }
}

// 设置秘书模型
const setSecretaryModel = async (id) => {
  const isCurrentlyActive = secretaryModelId.value === id
  const targetId = isCurrentlyActive ? '' : String(id)

  try {
    const res = await fetchWithTimeout(
      `${API_BASE}/configs`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ scorer_model_id: targetId }),
        silent: true
      },
      5000
    )
    if (!res.ok) throw new Error(isCurrentlyActive ? '取消秘书模型失败' : '设置秘书模型失败')
    secretaryModelId.value = isCurrentlyActive ? null : id
    window.$notify(isCurrentlyActive ? '秘书模型配置已取消' : '秘书模型已更新', 'success')
  } catch (e) {
    window.$notify(formatLLMError(e), 'error')
  }
}

// 设置反思模型
const setReflectionModel = async (id) => {
  const isCurrentlyActive = reflectionModelId.value === id
  const targetId = isCurrentlyActive ? '' : String(id)

  try {
    const res = await fetchWithTimeout(
      `${API_BASE}/configs`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reflection_model_id: targetId }),
        silent: true
      },
      5000
    )
    if (!res.ok) throw new Error(isCurrentlyActive ? '取消反思模型失败' : '设置反思模型失败')
    reflectionModelId.value = isCurrentlyActive ? null : id
    window.$notify(isCurrentlyActive ? '反思模型配置已取消' : '反思模型已更新', 'success')
  } catch (e) {
    window.$notify(formatLLMError(e), 'error')
  }
}

// 设置辅助模型
const setAuxModel = async (id) => {
  const isCurrentlyActive = auxModelId.value === id
  const targetId = isCurrentlyActive ? '' : String(id)

  try {
    const res = await fetchWithTimeout(
      `${API_BASE}/configs`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ aux_model_id: targetId }),
        silent: true
      },
      5000
    )
    if (!res.ok) throw new Error(isCurrentlyActive ? '取消辅助模型失败' : '设置辅助模型失败')
    auxModelId.value = isCurrentlyActive ? null : id
    window.$notify(isCurrentlyActive ? '辅助模型配置已取消' : '辅助模型已更新', 'success')
  } catch (e) {
    window.$notify(formatLLMError(e), 'error')
  }
}

// Global Settings
const openGlobalSettings = () => {
  showGlobalSettings.value = true
}
const saveGlobalSettings = async () => {
  if (isSaving.value) return
  try {
    isSaving.value = true
    const res = await fetchWithTimeout(
      `${API_BASE}/configs`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(globalConfig.value),
        silent: true
      },
      5000
    )

    if (!res.ok) throw new Error('保存配置失败')

    showGlobalSettings.value = false
    window.$notify('全局配置已保存', 'success')
    await fetchConfig()
  } catch (e) {
    window.$notify(formatLLMError(e), 'error')
  } finally {
    isSaving.value = false
  }
}

// User Settings Logic
const saveUserSettings = async () => {
  if (isSaving.value) return
  try {
    isSaving.value = true
    await fetchWithTimeout(
      `${API_BASE}/configs`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          owner_name: userSettings.value.owner_name,
          user_persona: userSettings.value.user_persona,
          owner_qq: userSettings.value.owner_qq
        })
      },
      5000
    )
    window.$notify('用户设定已保存', 'success')
    await fetchConfig()
  } catch (e) {
    window.$notify('保存失败: ' + e.message, 'error')
  } finally {
    isSaving.value = false
  }
}

// System Reset Logic
// 系统重置逻辑
const handleSystemReset = async () => {
  if (isSaving.value) return
  try {
    const { value, action } = await openConfirm(
      '终极警告',
      '<div class="danger-main-text">主人，真的要让 ' +
        (activeAgent.value?.name || 'Pero') +
        ' 忘掉你吗？o(╥﹏╥)o</div>' +
        '<div class="danger-sub-text">（此操作将执行深度清理，如需继续，请在文本框中输入“我们还会再见的...”）</div>',
      {
        type: 'error',
        isPrompt: true,
        inputValue: '',
        inputPlaceholder: '请输入：我们还会再见的...'
      }
    )

    if (action === 'confirm') {
      if (String(value || '').trim() !== '我们还会再见的...') {
        window.$notify('输入不匹配，已取消', 'error')
        return
      }

      isSaving.value = true
      const res = await fetchWithTimeout(`${API_BASE}/system/reset`, { method: 'POST' }, 10000)

      if (res.ok) {
        window.$notify('系统已恢复出厂设置', 'success')
        // 刷新所有数据以同步 UI
        await fetchAllData(true)
        currentTab.value = 'overview'
      } else {
        const err = await res.json()
        throw new Error(err.detail || '重置失败')
      }
    }
  } catch (e) {
    if (e.message !== 'User cancelled') {
      window.$notify(e.message || '重置过程中发生错误', 'error')
    }
  } finally {
    isSaving.value = false
  }
}

// MCP Logic
// MCP 逻辑
const openMcpEditor = (mcp) => {
  if (mcp) {
    currentEditingMcp.value = JSON.parse(JSON.stringify(mcp))
  } else {
    currentEditingMcp.value = {
      name: '',
      type: 'stdio',
      command: '',
      args: '[]',
      env: '{}',
      url: '',
      enabled: true
    }
  }
  showMcpEditor.value = true
}

const saveMcp = async () => {
  if (isSaving.value) return
  try {
    isSaving.value = true
    const mcp = currentEditingMcp.value
    const url = mcp.id ? `${API_BASE}/mcp/${mcp.id}` : `${API_BASE}/mcp`
    const method = mcp.id ? 'PUT' : 'POST'

    // Validate JSON
    // 验证 JSON
    if (mcp.type === 'stdio') {
      JSON.parse(mcp.args || '[]')
      JSON.parse(mcp.env || '{}')
    }

    const res = await fetchWithTimeout(
      url,
      {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(mcp)
      },
      5000
    )

    if (!res.ok) throw new Error('保存失败')

    showMcpEditor.value = false
    await fetchMcps()
    window.$notify('MCP 配置已保存', 'success')
  } catch (e) {
    window.$notify(e.message, 'error')
  } finally {
    isSaving.value = false
  }
}

const deleteMcp = async (id) => {
  if (!id || deleteMcp.isLoading) {
    if (!id) window.$notify('无效的MCP ID', 'error')
    return
  }

  try {
    await openConfirm('警告', '确定删除此 MCP 配置吗？', {
      type: 'warning'
    })

    deleteMcp.isLoading = true
    const res = await fetchWithTimeout(`${API_BASE}/mcp/${id}`, { method: 'DELETE' }, 5000)

    if (!res.ok) {
      const err = await res.json()
      throw new Error(err.message || '删除失败')
    }
    await fetchMcps()
    window.$notify('已删除', 'success')
  } catch (e) {
    if (e.message !== 'User cancelled') {
      console.error('Unexpected error in deleteMcp:', e)
      window.$notify('系统错误: ' + (e.message || '未知错误'), 'error')
    }
  } finally {
    deleteMcp.isLoading = false
  }
}

const toggleMcpEnabled = async (mcp) => {
  try {
    const res = await fetchWithTimeout(
      `${API_BASE}/mcp/${mcp.id}`,
      {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...mcp, enabled: mcp.enabled }) // Element Plus switch updates v-model directly // Element Plus 开关直接更新 v-model
      },
      5000
    )
    if (!res.ok) throw new Error('更新失败')
    await fetchMcps()
  } catch (e) {
    window.$notify(e.message, 'error')
    mcp.enabled = !mcp.enabled // revert
  }
}

// Model Logic
// 模型逻辑
const openModelEditor = (model) => {
  remoteModels.value = []
  if (model) {
    currentEditingModel.value = {
      enable_vision: false,
      enable_voice: false,
      enable_video: false,
      stream: true,
      temperature: 0.7,
      provider: 'openai',
      ...JSON.parse(JSON.stringify(model))
    }
  } else {
    currentEditingModel.value = {
      name: '',
      model_id: '',
      provider_type: 'custom',
      provider: 'openai',
      api_key: '',
      api_base: '',
      temperature: 0.7,
      stream: true,
      enable_vision: false,
      enable_voice: false,
      enable_video: false
    }
  }
  showModelEditor.value = true
}

const handleProviderChange = (val) => {
  // Auto-fill API Base for known providers if empty or using default
  // 强制使用官方 API Base 如果是已知服务商
  if (providerDefaults[val]) {
    currentEditingModel.value.api_base = providerDefaults[val]
  } else if (val === 'openai' && !currentEditingModel.value.api_base) {
    currentEditingModel.value.api_base = 'https://api.openai.com'
  }
}

const handleGlobalProviderChange = (val) => {
  // DeepSeek 强制使用官方 API Base
  if (val === 'deepseek') {
    globalConfig.value.global_llm_api_base = providerDefaults[val]
  } else if (
    providerDefaults[val] &&
    (!globalConfig.value.global_llm_api_base ||
      globalConfig.value.global_llm_api_base.includes('api.openai.com'))
  ) {
    globalConfig.value.global_llm_api_base = providerDefaults[val]
  } else if (val === 'openai' && !globalConfig.value.global_llm_api_base) {
    globalConfig.value.global_llm_api_base = 'https://api.openai.com'
  }
}

const fetchRemoteModels = async () => {
  if (isFetchingRemote.value) return
  try {
    isFetchingRemote.value = true
    let apiKey = '',
      apiBase = ''
    if (currentEditingModel.value.provider_type === 'global') {
      apiKey = globalConfig.value.global_llm_api_key
      apiBase = globalConfig.value.global_llm_api_base
    } else {
      apiKey = currentEditingModel.value.api_key
      apiBase = currentEditingModel.value.api_base
    }

    if (
      !apiBase &&
      ![
        'openai',
        'gemini',
        'anthropic',
        'siliconflow',
        'deepseek',
        'moonshot',
        'dashscope',
        'volcengine',
        'groq',
        'zhipu',
        'minimax',
        'mistral',
        'yi',
        'xai',
        'stepfun',
        'hunyuan',
        'ollama'
      ].includes(currentEditingModel.value.provider)
    ) {
      window.$notify('请先配置 API Base URL', 'warning')
      return
    }

    const res = await fetchWithTimeout(
      `${API_BASE}/models/remote`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          api_key: apiKey,
          api_base: apiBase,
          provider: currentEditingModel.value.provider || 'openai'
        }),
        silent: true
      },
      10000
    )

    if (!res.ok) {
      let errorDetail = ''
      try {
        const errData = await res.json()
        errorDetail = errData.detail || errData.message || JSON.stringify(errData)
      } catch {
        // ignore
      }
      throw new Error(errorDetail || `Status ${res.status}`)
    }

    const data = await res.json()
    if (data.models?.length) {
      remoteModels.value = data.models
      window.$notify(`获取到 ${data.models.length} 个模型`, 'success')
    } else {
      window.$notify('未找到模型或 API 不支持', 'warning')
    }
  } catch (e) {
    window.$notify(formatLLMError(e), 'error')
  } finally {
    isFetchingRemote.value = false
  }
}

const saveModel = async () => {
  if (isSaving.value) return
  try {
    isSaving.value = true
    const model = currentEditingModel.value
    const url = model.id ? `${API_BASE}/models/${model.id}` : `${API_BASE}/models`
    const method = model.id ? 'PUT' : 'POST'

    const res = await fetchWithTimeout(
      url,
      {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(model),
        silent: true
      },
      5000
    )

    if (!res.ok) throw new Error('保存失败')

    showModelEditor.value = false
    await fetchModels()
    window.$notify('模型已保存', 'success')
  } catch (e) {
    window.$notify(formatLLMError(e), 'error')
  } finally {
    isSaving.value = false
  }
}

const deleteModel = async (id) => {
  if (!id || deleteModel.isLoading) {
    if (!id) window.$notify('无效的模型ID', 'error')
    return
  }

  try {
    await openConfirm('警告', '确定删除此模型配置吗？', {
      type: 'warning'
    })

    deleteModel.isLoading = true
    const res = await fetchWithTimeout(`${API_BASE}/models/${id}`, { method: 'DELETE' }, 5000)

    if (!res.ok) {
      const err = await res.json()
      throw new Error(err.message || '删除失败')
    }
    await fetchModels()
    window.$notify('已删除', 'success')
  } catch (e) {
    if (e.message !== 'User cancelled') {
      console.error('Unexpected error in deleteModel:', e)
      window.$notify('系统错误: ' + (e.message || '未知错误'), 'error')
    }
  } finally {
    deleteModel.isLoading = false
  }
}

// 日志逻辑
// 日志逻辑

// 云同步状态
const initSessionAndFetchLogs = async () => {
  // 不在这里设置 isLogsFetching，而是交给 fetchLogs 统一管理
  // 仅负责初始化 session ID
  const storedSessionId = localStorage.getItem('ppc.sessionId')
  if (storedSessionId && !selectedSessionId.value) {
    selectedSessionId.value = storedSessionId
  } else if (!selectedSessionId.value) {
    selectedSessionId.value = 'default'
  }
  await fetchLogs()
}

const fetchLogs = async () => {
  if (!selectedSessionId.value || isLogsFetching.value) return
  isLogsFetching.value = true

  // 为此获取请求创建一个唯一的符号
  // 为此获取请求创建一个唯一的符号
  const currentRequestId = Symbol('fetchLogs')
  fetchLogs.lastRequestId = currentRequestId

  try {
    let url = `${API_BASE}/history/${selectedSource.value}/${selectedSessionId.value}?limit=200&sort=${selectedSort.value}`
    if (selectedDate.value) {
      url += `&date=${selectedDate.value}`
    }
    // 添加活动助手过滤器
    // 添加活动助手过滤器
    if (activeAgent.value) {
      url += `&agent_id=${activeAgent.value.id}`
    }

    const res = await fetchWithTimeout(url, {}, 5000)
    const rawLogs = await res.json()

    // 仅当请求过时时跳过更新
    // 仅当请求过时时跳过更新
    if (fetchLogs.lastRequestId !== currentRequestId) {
      return
    }

    // 首先过滤掉无效日志
    // 首先过滤掉无效日志
    const processedLogs = (Array.isArray(rawLogs) ? rawLogs : [])
      .filter((log) => log && typeof log === 'object')
      .map((log) => {
        const metadata = getLogMetadata(log)
        let images = []
        if (metadata && metadata.images && Array.isArray(metadata.images)) {
          images = metadata.images.map(
            (path) => `${API_BASE}/ide/image?path=${encodeURIComponent(path)}`
          )
        }

        return Object.freeze({
          ...log,
          // 内容原始传递给 AsyncMarkdown
          displayTime: new Date(log.timestamp).toLocaleString(),
          metadata: metadata || {},
          sentiment: log.sentiment || (metadata?.sentiment ?? null),
          importance: log.importance || (metadata?.importance ?? null),
          images: images
        })
      })

    logs.value = processedLogs

    // 自动滚动
    setTimeout(() => {
      if (currentTab.value !== 'logs') return
      const container = document.querySelector('.chat-scroll-area')
      if (container) {
        if (selectedSort.value === 'desc') {
          container.scrollTop = 0
        } else {
          container.scrollTop = container.scrollHeight
        }
      }
    }, 50)
  } catch (e) {
    console.error(e)
    window.$notify('获取日志失败', 'error')
  } finally {
    isLogsFetching.value = false
  }
}

const startLogEdit = (log) => {
  editingLogId.value = log.id
  editingContent.value = log.content
}

const cancelLogEdit = () => {
  editingLogId.value = null
  editingContent.value = ''
}

const saveLogEdit = async (logId) => {
  if (!editingContent.value.trim()) return
  try {
    const res = await fetchWithTimeout(
      `${API_BASE}/history/${logId}`,
      {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content: editingContent.value })
      },
      5000
    )
    if (res.ok) {
      editingLogId.value = null
      await fetchLogs()
      window.$notify('已修改', 'success')
    } else window.$notify('修改失败', 'error')
  } catch (e) {
    window.$notify('网络错误', 'error')
    console.error(e)
  }
}

const deleteLog = async (logId) => {
  if (!logId) {
    window.$notify('无效的记录ID', 'error')
    return
  }

  try {
    await openConfirm('提示', '确定删除这条记录？', {
      type: 'warning'
    })

    const res = await fetchWithTimeout(
      `${API_BASE}/history/${logId}`,
      {
        method: 'DELETE'
      },
      5000
    )

    if (res.ok) {
      window.$notify('已删除', 'success')
      await fetchLogs()
    } else {
      const err = await res.json()
      window.$notify(err.message || '删除失败', 'error')
    }
  } catch (e) {
    if (e.message !== 'User cancelled') {
      console.error('Error in deleteLog:', e)
      window.$notify('系统错误: ' + (e.message || '未知错误'), 'error')
    }
  }
}

const updateLogStatus = (logId, status) => {
  const index = logs.value.findIndex((l) => l.id === logId)
  if (index !== -1) {
    const newLog = { ...logs.value[index], analysis_status: status }
    // Update array immutably to support shallowRef and Object.freeze
    // 不可变地更新数组以支持 shallowRef 和 Object.freeze
    const newLogs = [...logs.value]
    newLogs[index] = Object.freeze(newLog)
    logs.value = newLogs
  }
}

const retryLogAnalysis = async (log) => {
  if (!log || !log.id) {
    window.$notify('无效的日志 ID', 'error')
    return
  }

  try {
    if (log.analysis_status === 'processing') return

    // 乐观更新 UI
    updateLogStatus(log.id, 'processing')

    const url = `${API_BASE}/history/${log.id}/retry_analysis`
    console.log('[Dashboard] Retrying analysis for log:', log.id, 'URL:', url)

    const res = await fetchWithTimeout(
      url,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        silent: true
      },
      10000
    ) // Increase timeout to 10s

    if (res.ok) {
      window.$notify('已提交重试请求', 'success')
      // 后台异步处理，稍后刷新或通过 WebSocket 更新
      // 这里简单起见，延迟刷新一下
      setTimeout(() => fetchLogs(), 2000)
    } else {
      const err = await res.json()
      throw new Error(err.detail || '重试请求失败')
    }
  } catch (e) {
    console.error('Retry failed:', e)
    // 详细输出错误信息以便排查
    window.$notify(formatLLMError(e), 'error')
    updateLogStatus(log.id, 'failed')
  }
}

const deleteMemory = async (memoryId) => {
  if (!memoryId || deleteMemory.isLoading) {
    if (!memoryId) window.$notify('无效的记忆ID', 'error')
    return
  }

  try {
    await openConfirm('提示', '确定要遗忘这段记忆吗？', {
      type: 'warning'
    })

    deleteMemory.isLoading = true
    const res = await fetchWithTimeout(
      `${API_BASE}/memories/${memoryId}`,
      { method: 'DELETE' },
      5000
    )

    if (res.ok) {
      await fetchMemories()
      window.$notify('已遗忘', 'success')
    } else {
      const err = await res.json()
      window.$notify(err.message || '操作失败', 'error')
    }
  } catch (e) {
    if (e.message !== 'User cancelled') {
      console.error('Error in deleteMemory:', e)
      window.$notify('系统错误: ' + (e.message || '未知错误'), 'error')
    }
  } finally {
    deleteMemory.isLoading = false
  }
}

const deleteTask = async (taskId) => {
  if (!taskId || deleteTask.isLoading) {
    if (!taskId) window.$notify('无效的任务ID', 'error')
    return
  }

  try {
    await openConfirm('提示', '确定删除此任务？', {
      type: 'warning'
    })

    deleteTask.isLoading = true
    const res = await fetchWithTimeout(`${API_BASE}/tasks/${taskId}`, { method: 'DELETE' }, 5000)

    if (res.ok) {
      await fetchTasks()
      window.$notify('已删除', 'success')
    } else {
      const err = await res.json()
      window.$notify(err.message || '操作失败', 'error')
    }
  } catch (e) {
    if (e.message !== 'User cancelled') {
      console.error('Error in deleteTask:', e)
      window.$notify('系统错误: ' + (e.message || '未知错误'), 'error')
    }
  } finally {
    deleteTask.isLoading = false
  }
}

// Handler for state updates via Gateway
const handleStateUpdate = () => {
  if (currentTab.value === 'overview') {
    fetchPetState()
  }
}

// Handler for schedule updates via Gateway
const handleScheduleUpdate = () => {
  if (currentTab.value === 'tasks') {
    fetchTasks()
  }
}

// Handler for agent changes via Gateway
const handleAgentChanged = () => {
  fetchAgents()
}

// Handler for log updates via Gateway
const handleLogUpdate = (data) => {
  const payload = data.params || data
  if (currentTab.value === 'logs') {
    // If it's a delete, we can remove locally to be snappier
    if (payload.operation === 'delete') {
      logs.value = logs.value.filter((l) => l.id != payload.id)
    } else {
      // For updates or new analysis results, we fetch to get fresh data
      fetchLogs()
    }
  }
}

onMounted(async () => {
  waitForBackend()

  // Listen for auto-update messages
  await listenSafe('update-message', handleUpdateMessage)

  // Fetch app version
  try {
    const v = await invoke('get_app_version')
    if (v) appVersion.value = v
  } catch {
    console.warn('Failed to get app version')
  }

  // Listen for real-time updates
  gatewayClient.on('action:state_update', handleStateUpdate)
  gatewayClient.on('action:schedule_update', handleScheduleUpdate)
  gatewayClient.on('action:agent_changed', handleAgentChanged)
  gatewayClient.on('action:log_updated', handleLogUpdate)

  // Listen for monitor updates
  if (window.electron && window.electron.on) {
    // Add debounced history update listener
    let logFetchTimeout = null
    window.electron.on('history-update', () => {
      if (logFetchTimeout) clearTimeout(logFetchTimeout)
      logFetchTimeout = setTimeout(() => {
        fetchLogs()
        logFetchTimeout = null
      }, 500)
    })
  } else {
    console.warn('Electron listeners not available')
  }
})

onUnmounted(() => {
  gatewayClient.off('action:new_message')
  gatewayClient.off('action:state_update', handleStateUpdate)
  gatewayClient.off('action:schedule_update', handleScheduleUpdate)
  gatewayClient.off('action:agent_changed', handleAgentChanged)
  gatewayClient.off('action:log_updated', handleLogUpdate)

  if (pollingInterval.value) {
    clearTimeout(pollingInterval.value)
  }
  if (resizeHandler) {
    window.removeEventListener('resize', resizeHandler)
  }
  if (chartInstance) {
    chartInstance.dispose()
  }
})
</script>

<style scoped>
/* 平面化动作按钮 */
.flat-action-btn {
  box-shadow: none !important;
  border: 1.5px solid rgba(255, 255, 255, 0.3) !important;
  background-image: none !important;
  transition: all 0.2s ease !important;
}

.flat-action-btn:hover {
  transform: translateY(-1px) !important;
  filter: brightness(1.05);
}

.flat-action-btn:active {
  transform: translateY(0) !important;
}

/* 动画效果 */
.fade-slide-enter-active,
.fade-slide-leave-active {
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.fade-slide-enter-from {
  opacity: 0;
  transform: translateX(20px);
}

.fade-slide-leave-to {
  opacity: 0;
  transform: translateX(-20px);
}

/* 自定义滚动条 */
.custom-scrollbar::-webkit-scrollbar {
  width: 6px;
}

.custom-scrollbar::-webkit-scrollbar-track {
  background: transparent;
}

.custom-scrollbar::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.1);
  border-radius: 10px;
}

.custom-scrollbar::-webkit-scrollbar-thumb:hover {
  background: rgba(255, 255, 255, 0.2);
}

.scrollbar-hide::-webkit-scrollbar {
  display: none;
}

.state-box .label {
  font-size: 13px;
  color: var(--healing-text-light);
  display: block;
  margin-bottom: 6px;
}
.state-box .value {
  font-size: 20px;
  font-weight: 800;
  color: var(--healing-text);
  margin-bottom: 12px;
  display: block;
}

/* Logs View */
.logs-layout {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.filter-card {
  margin-bottom: 16px;
}

.chat-scroll-area {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
  border-radius: var(--radius-md);
  background: rgba(255, 255, 255, 0.2); /* Lighter glass */
  border: 1px solid rgba(255, 255, 255, 0.2);
  margin-right: -10px;
  padding-right: 20px;
}

.chat-bubble-wrapper {
  display: flex;
  gap: 16px;
  margin-bottom: 24px;
}

.chat-bubble-wrapper.assistant {
  flex-direction: row;
}
.chat-bubble-wrapper.user {
  flex-direction: row-reverse;
}

.avatar {
  width: 44px;
  height: 44px;
  background: white;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 22px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  flex-shrink: 0;
  border: 2px solid white;
}

.bubble-content-box {
  max-width: 70%;
  padding: 16px 20px;
  border-radius: 20px; /* More rounded */
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
  position: relative;
  transition: all 0.3s;
}

.chat-bubble-wrapper.user .bubble-content-box {
  background: var(--healing-primary); /* Sky Blue */
  color: white;
  border-bottom-right-radius: 4px; /* Squircle effect */
  box-shadow: 0 4px 12px rgba(108, 180, 238, 0.3);
}

/* 消息气泡样式 */
.chat-bubble-wrapper {
  display: flex;
  margin-bottom: 20px;
  max-width: 85%;
  position: relative;
}

.chat-bubble-wrapper.user {
  margin-left: auto;
  flex-direction: row-reverse;
}

.bubble-content-box {
  padding: 12px 18px;
  border-radius: 20px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
  position: relative;
  transition: all 0.3s;
}

.chat-bubble-wrapper.user .bubble-content-box {
  background: var(--healing-primary);
  color: white;
  border-bottom-right-radius: 4px;
  box-shadow: 0 4px 12px rgba(108, 180, 238, 0.3);
}

.chat-bubble-wrapper.assistant .bubble-content-box {
  background: white;
  color: var(--healing-text);
  border-bottom-left-radius: 4px;
}

.bubble-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 11px;
  color: var(--healing-text-light);
  margin-bottom: 8px;
}

.log-meta-tag {
  background: rgba(0, 0, 0, 0.05);
  padding: 2px 8px; /* Larger capsule */
  border-radius: 12px;
  cursor: help;
  font-weight: 600;
}

.log-meta-tag.importance {
  color: #f59e0b; /* amber-500 */
  background: #fffbeb; /* amber-50 */
}

.log-meta-tag.memory {
  background: #f0f9ff; /* sky-50 */
  color: #0ea5e9; /* sky-500 */
}

.message-markdown {
  font-size: 15px;
  line-height: 1.6;
}

/* User text color fix for Markdown */
.chat-bubble-wrapper.user .message-content-wrapper :deep(.markdown-body),
.chat-bubble-wrapper.user .message-content-wrapper :deep(.markdown-body p),
.chat-bubble-wrapper.user .message-content-wrapper :deep(.markdown-body span),
.chat-bubble-wrapper.user .message-content-wrapper :deep(.markdown-body li),
.chat-bubble-wrapper.user .message-content-wrapper :deep(.markdown-body strong) {
  color: white !important;
}

/* User Bubble Meta Color Fix */
.chat-bubble-wrapper.user .bubble-meta {
  color: rgba(255, 255, 255, 0.9) !important;
}
.chat-bubble-wrapper.user .bubble-meta .role-name,
.chat-bubble-wrapper.user .bubble-meta .time {
  color: inherit !important;
}

/* Exclude code blocks from being white if they have their own styling */
.chat-bubble-wrapper.user .message-content-wrapper :deep(.markdown-body code) {
  color: #c7254e; /* Default code color or whatever fits */
  background-color: #f9f2f4;
  border-radius: 4px;
  padding: 2px 4px;
}

.chat-bubble-wrapper.user .message-content-wrapper :deep(.markdown-body pre) {
  background-color: #f8fafc; /* slate-50 */
  color: #1e293b; /* slate-800 */
}

.chat-bubble-wrapper.user .message-content-wrapper :deep(.markdown-body pre code) {
  color: inherit;
  background-color: transparent;
}

/* Trigger Blocks inside Markdown */
:deep(.trigger-block) {
  margin: 12px 0;
  border-radius: 16px; /* Rounded block */
  overflow: hidden;
  font-size: 13px;
  border: 1px solid rgba(0, 0, 0, 0.05);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.03);
  background: white;
}

:deep(.trigger-header) {
  padding: 8px 12px;
  background: rgba(0, 0, 0, 0.03);
  font-weight: bold;
  font-size: 12px;
  display: flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
  user-select: none;
  list-style: none;
  outline: none;
}

:deep(.trigger-header::-webkit-details-marker) {
  display: none;
}

:deep(.expand-arrow) {
  margin-left: auto;
  font-size: 10px;
  color: #94a3b8; /* slate-400 */
  transition: transform 0.2s;
}

:deep(details[open] .expand-arrow) {
  transform: rotate(90deg);
}

:deep(.trigger-title) {
  flex: 1;
}

:deep(.trigger-body) {
  padding: 12px;
  border-top: 1px solid rgba(0, 0, 0, 0.05);
}

/* Specific Block Themes */
:deep(.trigger-block.perocue) {
  border-color: #fca5a5; /* red-300 */
}
:deep(.trigger-block.perocue .trigger-header) {
  background: linear-gradient(90deg, #fff1f2, #ffe4e6); /* red-50/100 */
  color: #f43f5e; /* rose-500 */
}

:deep(.trigger-block.memory) {
  border-color: #bae6fd; /* sky-200 */
}
:deep(.trigger-block.memory .trigger-header) {
  background: linear-gradient(90deg, #f0f9ff, #e0f2fe); /* sky-50/100 */
  color: #0ea5e9; /* sky-500 */
}

:deep(.trigger-block.click_messages) {
  border-color: #fde047; /* yellow-300 */
}
:deep(.trigger-block.click_messages .trigger-header) {
  background: linear-gradient(90deg, #fefce8, #fef9c3); /* yellow-50/100 */
  color: #a16207; /* yellow-700 */
}

:deep(.trigger-block.idle_messages),
:deep(.trigger-block.back_messages) {
  border-color: #7dd3fc; /* sky-300 */
}
:deep(.trigger-block.idle_messages .trigger-header),
:deep(.trigger-block.back_messages .trigger-header) {
  background: linear-gradient(90deg, #f0f9ff, #e0f2fe); /* sky-50/100 */
  color: #0ea5e9; /* sky-500 */
}

:deep(.trigger-block.unknown-xml) {
  border-color: #cbd5e1; /* slate-300 */
}
:deep(.trigger-block.unknown-xml .trigger-header) {
  background: linear-gradient(90deg, #f8fafc, #f1f5f9); /* slate-50/100 */
  color: #64748b; /* slate-500 */
}

/* Sub-elements styling */
:deep(.pero-meta-row) {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 8px;
  align-items: center;
}

:deep(.pero-label) {
  font-size: 11px;
  color: #64748b; /* slate-500 */
  background: #f1f5f9; /* slate-100 */
  padding: 2px 6px;
  border-radius: 4px;
}

:deep(.pero-val) {
  font-weight: 600;
  color: #1e293b; /* slate-800 */
}

:deep(.pero-mind-box) {
  background: #fff5f7; /* rose-50 */
  border-left: 3px solid #fda4af; /* rose-300 */
  padding: 8px 10px;
  border-radius: 4px;
  font-style: italic;
  color: #475569; /* slate-600 */
  line-height: 1.5;
}

:deep(.pero-memory-content) {
  line-height: 1.6;
  margin-bottom: 10px;
  color: #334155; /* slate-700 */
}

:deep(.pero-tag-cloud) {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

:deep(.pero-tag) {
  background: #f3e5f5;
  color: #7b1fa2;
  padding: 2px 8px;
  border-radius: 12px;
  font-size: 11px;
  font-weight: 500;
}

:deep(.pero-click-grid) {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  gap: 10px;
}

:deep(.pero-part-card) {
  background: #fdfdfb; /* stone-50 */
  border: 1px solid #fde68a; /* amber-200 */
  border-radius: 8px;
  padding: 8px;
}

:deep(.part-name) {
  font-size: 11px;
  font-weight: bold;
  color: #92400e; /* amber-800 */
  margin-bottom: 4px;
  border-bottom: 1px dashed #fef3c7; /* amber-100 */
  padding-bottom: 2px;
}

:deep(.part-list),
:deep(.pero-topic-box),
:deep(.pero-task-box) {
  margin: 0;
  padding-left: 18px;
  font-size: 12px;
  color: #475569; /* slate-600 */
}

:deep(.part-list li) {
  margin-bottom: 2px;
}

:deep(.pero-task-box),
:deep(.pero-topic-box) {
  padding: 8px;
  background: #f0f9ff; /* sky-50 */
  border-radius: 6px;
  color: #0284c7; /* sky-600 */
  list-style: none;
}

:deep(.trigger-block.error) {
  border-color: #fca5a5; /* red-300 */
  color: #ef4444; /* red-500 */
  padding: 8px;
  background: #fef2f2; /* red-50 */
}

.bubble-actions {
  display: flex;
  justify-content: flex-end;
  margin-top: 4px;
  opacity: 0;
  transition: opacity 0.2s;
}

.chat-bubble-wrapper:hover .bubble-actions {
  opacity: 1;
}

.chat-bubble-wrapper.editing .bubble-content-box {
  max-width: 100%;
  width: 100%;
}

/* Memories View */
.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.section-title {
  font-size: 20px;
  font-weight: 700;
  color: var(--healing-text);
  margin: 0;
  letter-spacing: 0.5px;
}

.memory-header-enhanced {
  display: flex;
  align-items: center;
  gap: 12px;
}

.header-icon-wrapper {
  width: 42px;
  height: 42px;
  border-radius: 12px;
  background: linear-gradient(135deg, #7dd3fc 0%, #0ea5e9 100%); /* sky-300 to sky-500 */
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 4px 10px rgba(14, 165, 233, 0.3);
  color: white;
  font-size: 20px;
}

.header-text-content {
  display: flex;
  flex-direction: column;
  justify-content: center;
}

.section-title-enhanced {
  font-size: 20px;
  font-weight: 800;
  margin: 0;
  background: linear-gradient(90deg, #0369a1 0%, #0ea5e9 100%); /* sky-700 to sky-500 */
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  color: #0369a1;
  line-height: 1.2;
}

.section-subtitle {
  font-size: 10px;
  color: #64748b; /* slate-500 */
  font-weight: 600;
  letter-spacing: 0.5px;
  text-transform: uppercase;
  margin-top: 2px;
}

.memory-waterfall {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 20px;
  align-items: start;
}

.memory-item {
  margin-bottom: 0;
}

.memory-card {
  border-radius: 16px !important;
  transition: all 0.4s cubic-bezier(0.25, 0.8, 0.25, 1);
  cursor: default;
  border: 1px solid rgba(255, 255, 255, 0.6) !important;
  background: rgba(255, 255, 255, 0.75) !important;
  backdrop-filter: blur(16px);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.03) !important;
  position: relative;
  overflow: hidden;
  padding-top: 5px; /* Make space for the top bar */
}

.memory-card:hover {
  transform: translateY(-5px) scale(1.01);
  background: rgba(255, 255, 255, 0.95) !important;
  box-shadow:
    0 15px 30px rgba(0, 0, 0, 0.08),
    0 5px 15px rgba(0, 0, 0, 0.04) !important;
  z-index: 10;
  border-color: rgba(255, 255, 255, 0.9) !important;
}

/* Color Coding with Gradients */
.memory-card::after {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 4px;
  background: #cbd5e1; /* slate-300 */
  z-index: 1;
}

.memory-card.preference::after {
  background: linear-gradient(90deg, #fb7185 0%, #fda4af 100%); /* rose-400 to rose-300 */
}
.memory-card.event::after {
  background: linear-gradient(90deg, #7dd3fc 0%, #bae6fd 100%); /* sky-300 to sky-200 */
}
.memory-card.fact::after {
  background: linear-gradient(90deg, #38bdf8 0%, #7dd3fc 100%); /* sky-400 to sky-300 */
}
.memory-card.summary::after {
  background: linear-gradient(90deg, #fbbf24 0%, #fcd34d 100%); /* amber-400 to amber-300 */
}
.memory-card.promise::after {
  background: linear-gradient(90deg, #38bdf8 0%, #7dd3fc 100%); /* sky-400 to sky-300 */
}
.memory-card.work_log::after {
  background: linear-gradient(90deg, #94a3b8 0%, #cbd5e1 100%); /* slate-400 to slate-300 */
}

/* Remove old specific borders */
.memory-card.preference,
.memory-card.event,
.memory-card.fact,
.memory-card.summary {
  border-top: none !important;
}

.memory-text {
  font-size: 14.5px;
  line-height: 1.65;
  color: #334155; /* slate-700 */
  margin: 12px 0 16px 0;
  padding: 0 4px;
  font-weight: 500;
  letter-spacing: 0.01em;
}

.memory-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
  padding-top: 8px; /* Extra padding since we have the top bar */
}

.memory-bottom {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px dashed rgba(0, 0, 0, 0.06);
}

.mini-tag {
  border: none !important;
  font-weight: 600;
  letter-spacing: 0.3px;
  box-shadow: 0 2px 5px rgba(0, 0, 0, 0.05);
}

/* Enhanced Memory Toolbar */
.memory-toolbar {
  flex-direction: column !important;
  align-items: stretch !important;
  gap: 15px;
  height: auto !important;
}

.filters-glass-panel {
  background: rgba(255, 255, 255, 0.6);
  backdrop-filter: blur(12px);
  border: 1px solid rgba(255, 255, 255, 0.4);
  border-radius: 16px;
  padding: 12px 16px;
  margin-bottom: 10px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.02);
}

.filter-row-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.filter-group-left {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.filter-group-right {
  display: flex;
  align-items: center;
}

.agent-selector-wrapper {
  display: flex;
  align-items: center;
  gap: 8px;
  background: rgba(255, 255, 255, 0.5);
  padding: 4px 10px;
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.3);
}

.agent-selector-wrapper .label {
  font-size: 12px;
  color: #64748b; /* slate-500 */
  font-weight: 500;
}

.agent-name {
  font-weight: 600;
  color: var(--healing-primary);
  font-size: 13px;
  display: flex;
  align-items: center;
  gap: 4px;
  cursor: pointer;
}

.divider-vertical {
  width: 1px;
  height: 20px;
  background: rgba(0, 0, 0, 0.06);
  margin: 0 4px;
}

.filter-row-bottom {
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-top: 1px dashed rgba(0, 0, 0, 0.05);
  padding-top: 10px;
}

.tag-cloud-inline {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
  overflow: hidden;
  margin-right: 15px;
}

.tag-label {
  font-size: 11px;
  color: #94a3b8; /* slate-400 */
  white-space: nowrap;
}

.tag-scroll-area {
  display: flex;
  align-items: center;
  gap: 6px;
  overflow-x: auto;
  padding-bottom: 2px;
  -ms-overflow-style: none;
  scrollbar-width: none;
}

.tag-scroll-area::-webkit-scrollbar {
  display: none;
}

.glass-check-tag {
  background: rgba(255, 255, 255, 0.4) !important;
  border: 1px solid rgba(0, 0, 0, 0.05) !important;
  font-size: 11px !important;
  padding: 2px 8px !important;
  border-radius: 6px !important;
  color: #475569; /* slate-600 */
  transition: all 0.2s !important;
  cursor: pointer;
}

.glass-check-tag:hover {
  background: #fff !important;
  color: var(--healing-primary) !important;
}

.glass-check-tag.is-checked {
  background: var(--healing-primary) !important;
  color: white !important;
  border-color: var(--healing-primary) !important;
}

.action-buttons {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}

.glass-button {
  border: 1px solid rgba(0, 0, 0, 0.05) !important;
  background: rgba(255, 255, 255, 0.6) !important;
  transition: all 0.2s !important;
}

.glass-button:hover {
  transform: translateY(-2px);
  background: #fff !important;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
}

/* Tasks Waterfall */
.task-waterfall {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 20px;
  align-items: start;
}

.task-item {
  margin-bottom: 0;
}

.task-card-modern {
  border-radius: var(--radius-md) !important;
  transition: all 0.3s;
  border: none !important;
  background: rgba(255, 255, 255, 0.7) !important;
  backdrop-filter: blur(10px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05) !important;
}

.task-card-modern:hover {
  transform: translateY(-3px);
  box-shadow: 0 12px 24px rgba(0, 0, 0, 0.08) !important;
}

.task-card-modern.reminder {
  border-left: 4px solid #f43f5e !important; /* rose-500 */
}
.task-card-modern.topic {
  border-left: 4px solid #0ea5e9 !important; /* sky-500 */
}
.task-card-modern.todo {
  border-left: 4px solid #0ea5e9 !important; /* sky-500 */
}

.task-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.task-content {
  font-size: 14px;
  color: var(--healing-text);
  line-height: 1.6;
  margin-bottom: 14px;
  font-weight: 500;
}

.task-bottom {
  border-top: 1px solid rgba(0, 0, 0, 0.05);
  padding-top: 10px;
}

.task-time {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  color: var(--healing-text-light);
}

/* Fix Dialog Transparency Issue */
.custom-modal-content {
  background: rgba(15, 23, 42, 0.95) !important; /* slate-900 */
  backdrop-filter: blur(20px);
  border-radius: 24px;
  box-shadow: 0 16px 48px rgba(0, 0, 0, 0.3);
  border: 1px solid rgba(255, 255, 255, 0.1);
}

/* Ensure input text is visible in custom components */
.p-input-inner {
  color: #f1f5f9 !important; /* slate-100 */
}

.memory-top {
  display: flex;
  justify-content: space-between;
  margin-bottom: 8px;
}
.memory-text {
  font-size: 14px;
  color: #475569; /* slate-600 */
  line-height: 1.5;
  margin-bottom: 12px;
}
.memory-bottom {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.time-hint {
  font-size: 11px;
  color: #94a3b8; /* slate-400 */
}

/* 模型网格 */
.models-grid-layout {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 20px;
}

.model-config-card {
  border-radius: 12px;
  position: relative;
  overflow: hidden;
}

.status-badge {
  display: flex;
  align-items: center;
  background: rgba(255, 255, 255, 0.5);
  padding: 4px 8px;
  border-radius: 12px;
  border: 1px solid rgba(0, 0, 0, 0.05);
  transition: all 0.3s;
  cursor: help;
}

.status-badge:hover {
  background: rgba(255, 255, 255, 0.8);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background-color: #94a3b8; /* Offline - slate-400 */
  box-shadow: 0 0 0 2px rgba(255, 255, 255, 0.8);
  transition: all 0.3s;
}

.status-dot.online {
  background-color: #0ea5e9; /* Online - sky-500 */
  box-shadow: 0 0 4px #0ea5e9;
}

.status-dot.warning {
  background-color: #f59e0b; /* amber-500 */
}

.status-dot.offline {
  background-color: #f43f5e; /* rose-500 */
}

.model-config-card.active-main {
  border: 2px solid var(--healing-primary);
}
.model-config-card.active-secretary {
  border: 2px solid #f59e0b; /* amber-500 */
}
.model-config-card.active-reflection {
  border: 2px solid #0284c7; /* sky-600 */
}

/* Scrollbar Beauty */
::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}

::-webkit-scrollbar-track {
  background: transparent;
}

::-webkit-scrollbar-thumb {
  background: rgba(0, 0, 0, 0.1);
  border-radius: 10px;
}

::-webkit-scrollbar-thumb:hover {
  background: rgba(0, 0, 0, 0.2);
}

.model-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 12px;
}

.model-header h3 {
  margin: 0;
  font-size: 16px;
}

.model-body p {
  margin: 4px 0;
  font-size: 13px;
  color: #64748b; /* slate-500 */
}

.model-actions {
  margin-top: 16px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.utils-group {
  display: flex;
  gap: 4px;
}

/* MCP Card Modern */
.mcp-card-modern {
  border-radius: 12px;
  height: 100%;
  display: flex;
  flex-direction: column;
}
.mcp-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}
.mcp-title {
  font-weight: bold;
  font-size: 15px;
}
.mcp-info {
  flex: 1;
  margin-bottom: 12px;
}
.mcp-detail {
  font-size: 12px;
  color: #64748b; /* slate-500 */
  margin-top: 4px;
  word-break: break-all;
  font-family: monospace;
  background: #f1f5f9; /* slate-100 */
  padding: 4px;
  border-radius: 4px;
}
.mcp-footer {
  display: flex;
  justify-content: flex-end;
}

/* Transition */
.fade-slide-enter-active,
.fade-slide-leave-active {
  transition: all 0.3s ease;
}

.fade-slide-enter-from {
  opacity: 0;
  transform: translateY(10px);
}

.fade-slide-leave-to {
  opacity: 0;
  transform: translateY(-10px);
}

/* List Transition */
.list-enter-active,
.list-leave-active {
  transition: all 0.4s ease;
}
.list-enter-from,
.list-leave-to {
  opacity: 0;
  transform: translateY(20px);
}

/* Responsive */
@media (max-width: 768px) {
  .memory-waterfall,
  .task-waterfall {
    column-count: 1;
  }
  .glass-sidebar {
    display: none;
  } /* Mobile todo */
}

/* Dashboard Global Edit Input Style */
.dashboard-edit-textarea {
  font-size: 15px;
  line-height: 1.6;
  padding: 12px 16px;
  border-radius: 12px;
  background-color: #ffffff;
  border: 2px solid #e2e8f0; /* slate-200 */
  color: #1e293b; /* slate-800 */
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
  transition: all 0.3s ease;
  font-family: 'Segoe UI', system-ui, sans-serif;
  width: 100%;
  outline: none;
}

.dashboard-edit-textarea:focus {
  border-color: #0ea5e9; /* sky-500 */
  box-shadow: 0 4px 16px rgba(14, 165, 233, 0.15);
}

.edit-mode {
  width: 100%;
  margin: 10px 0;
}

.edit-tools {
  margin-top: 12px;
  display: flex;
  gap: 10px;
  justify-content: flex-end;
}
/* New Memory UI Styles */
.memory-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.badges-left {
  display: flex;
  gap: 6px;
  align-items: center;
}

.actions-right {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 12px;
}

.importance-indicator {
  color: #f59e0b; /* amber-500 */
  font-weight: bold;
  cursor: help;
}

.access-indicator {
  color: #f43f5e; /* rose-500 */
  font-weight: bold;
  cursor: help;
}

/* --- NIT Status Styles --- */
.nit-status-box {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.nit-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.nit-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
  font-size: 16px;
  color: #1e293b; /* slate-800 */
}
.nit-metrics {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 13px;
  color: #64748b; /* slate-500 */
}
.nit-plugins-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
}
.mini-plugin-tag {
  font-family: monospace;
}
.more-tag {
  font-size: 12px;
  color: #94a3b8; /* slate-400 */
}

/* --- Memory Dashboard Styles --- */
.memory-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}
.filters {
  display: flex;
  gap: 10px;
  align-items: center;
}
.tag-cloud-area {
  margin-bottom: 20px;
  background: rgba(255, 255, 255, 0.6);
  padding: 12px 16px;
  border-radius: 12px;
  display: flex;
  align-items: flex-start;
  gap: 12px;
}
.tag-cloud-label {
  font-size: 13px;
  font-weight: bold;
  color: #475569; /* slate-600 */
  white-space: nowrap;
  margin-top: 4px;
}
.tag-cloud-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.cloud-tag {
  font-size: 12px !important;
}

/* Graph Mode */
.memory-graph-container {
  background: #ffffff;
  border-radius: 12px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
  padding: 20px;
  min-height: 500px;
}
.simple-graph-view {
  position: relative;
  width: 100%;
  height: 500px;
  border: 1px solid #f1f5f9; /* slate-100 */
  border-radius: 8px;
  overflow: hidden;
  background: #fafafa;
}
.graph-svg {
  width: 100%;
  height: 100%;
}
.graph-hint {
  position: absolute;
  bottom: 10px;
  left: 10px;
  font-size: 12px;
  color: #94a3b8; /* slate-400 */
  background: rgba(255, 255, 255, 0.8);
  padding: 8px;
  border-radius: 4px;
  pointer-events: none;
}

/* --- Transition Animations --- */
.fade-slide-enter-active,
.fade-slide-leave-active {
  transition:
    opacity 0.3s ease,
    transform 0.3s ease;
}

.fade-slide-enter-from {
  opacity: 0;
  transform: translateY(10px);
}

.fade-slide-leave-to {
  opacity: 0;
  transform: translateY(-10px);
}
</style>
