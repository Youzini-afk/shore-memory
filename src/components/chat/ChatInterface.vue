<template>
  <div
    class="flex flex-col h-full transition-colors duration-300 relative"
    :class="workMode ? 'bg-[#1e293b] text-slate-200' : 'bg-transparent text-slate-700'"
  >
    <!-- 指令执行遮罩 -->
    <Transition name="fade">
      <div
        v-if="activeCommand"
        class="absolute inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-6"
      >
        <div
          class="bg-white dark:bg-slate-800 rounded-2xl shadow-2xl w-full max-w-md overflow-hidden border border-slate-200 dark:border-slate-700 transform transition-all animate-scale-in"
        >
          <!-- 标题栏 -->
          <div
            class="px-6 py-4 bg-sky-50 dark:bg-sky-900/20 border-b border-sky-100 dark:border-sky-800/30 flex items-center gap-3"
          >
            <div
              class="p-2 bg-sky-100 dark:bg-sky-800/40 rounded-full text-sky-600 dark:text-sky-400 animate-spin-slow"
            >
              <Terminal class="w-5 h-5" />
            </div>
            <div>
              <h3 class="font-bold text-slate-800 dark:text-slate-100">正在执行指令...</h3>
              <p class="text-xs text-slate-500 dark:text-slate-400">请稍候，任务正在后台运行</p>
            </div>
          </div>

          <!-- 内容区域 -->
          <div class="p-6">
            <div
              class="bg-slate-900 rounded-lg p-4 font-mono text-sm text-green-400 overflow-x-auto custom-scrollbar border border-slate-700 shadow-inner relative"
            >
              <span class="select-text">{{ activeCommand.command }}</span>
              <div class="absolute bottom-2 right-2 flex gap-1">
                <div class="w-1.5 h-1.5 bg-green-500 rounded-full animate-pulse"></div>
                <div class="w-1.5 h-1.5 bg-green-500 rounded-full animate-pulse delay-75"></div>
                <div class="w-1.5 h-1.5 bg-green-500 rounded-full animate-pulse delay-150"></div>
              </div>
            </div>
            <div class="mt-4 flex items-center justify-between">
              <p class="text-xs text-slate-500 dark:text-slate-400">PID: {{ activeCommand.pid }}</p>
              <button
                class="text-xs text-amber-500 hover:text-amber-600 font-medium underline underline-offset-2 transition-colors"
                @click="skipCommandWait"
              >
                跳过等待 (后台继续)
              </button>
            </div>
          </div>
        </div>
      </div>
    </Transition>

    <!-- 指令确认遮罩 -->
    <Transition name="fade">
      <div
        v-if="pendingConfirmation"
        class="absolute inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-6"
      >
        <div
          class="bg-white dark:bg-slate-800 rounded-2xl shadow-2xl w-full max-w-md overflow-hidden border border-slate-200 dark:border-slate-700 transform transition-all animate-scale-in"
        >
          <!-- 标题栏 -->
          <div
            class="px-6 py-4 flex items-center gap-3 border-b transition-colors"
            :class="getRiskLevelColor(pendingConfirmation.riskInfo?.level, 'header')"
          >
            <div
              class="p-2 rounded-full transition-colors"
              :class="getRiskLevelColor(pendingConfirmation.riskInfo?.level, 'icon')"
            >
              <Terminal class="w-5 h-5" />
            </div>
            <div>
              <h3 class="font-bold text-slate-800 dark:text-slate-100 flex items-center gap-2">
                请求执行终端指令
                <span
                  v-if="pendingConfirmation.riskInfo?.level > 0"
                  class="px-2 py-0.5 text-white text-[10px] rounded-full uppercase tracking-wide font-bold"
                  :class="getRiskLevelColor(pendingConfirmation.riskInfo?.level, 'badge')"
                >
                  {{ getRiskLabel(pendingConfirmation.riskInfo?.level) }}
                </span>
              </h3>
              <p class="text-xs text-slate-500 dark:text-slate-400">
                {{ agentName }} 申请在您的系统中执行以下命令
              </p>
            </div>
          </div>

          <!-- 内容区域 -->
          <div class="p-6">
            <div
              class="bg-slate-900 rounded-lg p-4 font-mono text-sm overflow-x-auto custom-scrollbar border shadow-inner transition-colors"
              :class="getRiskLevelColor(pendingConfirmation.riskInfo?.level, 'content')"
            >
              <span
                v-if="pendingConfirmation.riskInfo?.highlight"
                v-html="
                  highlightCommand(
                    pendingConfirmation.command,
                    pendingConfirmation.riskInfo.highlight
                  )
                "
              ></span>
              <span v-else class="select-text">{{ pendingConfirmation.command }}</span>
            </div>

            <div
              v-if="pendingConfirmation.riskInfo?.level >= 2"
              class="mt-4 p-3 rounded-lg flex gap-3 items-start"
              :class="getRiskLevelColor(pendingConfirmation.riskInfo?.level, 'warning_box')"
            >
              <div
                class="p-1 rounded shrink-0"
                :class="getRiskLevelColor(pendingConfirmation.riskInfo?.level, 'warning_icon')"
              >
                <AlertTriangle class="w-4 h-4" />
              </div>
              <div
                class="text-xs"
                :class="getRiskLevelColor(pendingConfirmation.riskInfo?.level, 'warning_text')"
              >
                <p class="font-bold mb-1">
                  系统警告：{{ pendingConfirmation.riskInfo?.reason || '敏感操作' }}
                </p>
                <p class="opacity-90">
                  此指令包含可能修改系统关键配置或删除文件的操作。请务必确认指令来源和意图。
                </p>
              </div>
            </div>
            <p v-else class="mt-4 text-xs text-slate-500 dark:text-slate-400 text-center">
              说明:
              {{
                pendingConfirmation.riskInfo?.reason ||
                '请仔细检查指令内容。此操作将在您的系统终端中真实执行。'
              }}
            </p>
          </div>

          <!-- 操作按钮 -->
          <div
            class="px-6 py-4 bg-slate-50 dark:bg-slate-800/50 flex justify-end gap-3 border-t border-slate-100 dark:border-slate-700"
          >
            <button
              class="px-4 py-2 rounded-lg text-sm font-medium text-slate-600 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700 transition-colors"
              @click="respondConfirmation(false)"
            >
              拒绝执行
            </button>
            <button
              class="px-4 py-2 rounded-lg text-sm font-medium text-white shadow-lg transition-all active:scale-95 flex items-center gap-2"
              :class="getRiskLevelColor(pendingConfirmation.riskInfo?.level, 'button')"
              @click="respondConfirmation(true)"
            >
              <Check class="w-4 h-4" />
              <span>{{
                pendingConfirmation.riskInfo?.level >= 3 ? '确认授权并执行' : '批准并执行'
              }}</span>
            </button>
          </div>
        </div>
      </div>
    </Transition>

    <!-- 消息区域 -->
    <div
      ref="msgContainer"
      class="flex-1 overflow-y-auto p-6 space-y-6 custom-scrollbar flex flex-col"
    >
      <!-- 加载更多按钮 -->
      <div v-if="hasMore" class="flex justify-center py-4">
        <button
          class="text-xs text-slate-400 hover:text-sky-500 transition-colors flex items-center gap-1"
          @click="loadMore"
        >
          <Clock class="w-3 h-3" />
          <span>查看更多历史记录</span>
        </button>
      </div>

      <div v-for="msg in messages" :key="msg.id || msg.timestamp" class="flex flex-col">
        <!-- 用户消息 -->
        <div v-if="msg.role === 'user'" class="flex justify-end mb-4 animate-fade-in-up group">
          <div class="max-w-[85%] animate-float flex flex-col items-end">
            <!-- 图片显示 -->
            <div
              v-if="msg.images && msg.images.length > 0"
              class="flex gap-2 mb-2 flex-wrap justify-end"
            >
              <div v-for="(img, iIdx) in msg.images" :key="iIdx" class="relative">
                <img
                  :src="img"
                  class="max-h-32 rounded-lg shadow-md border border-white/10 object-cover hover:scale-105 transition-transform cursor-pointer"
                  @click="window.open(img, '_blank')"
                />
              </div>
            </div>

            <div
              class="px-5 py-3 rounded-2xl rounded-tr-sm shadow-md text-sm leading-relaxed whitespace-pre-wrap font-sans transition-all backdrop-blur-xl border border-white/10 hover:scale-[1.02] hover:-translate-y-[2px] hover:shadow-lg hover:shadow-sky-500/30 relative hover:z-10 duration-300 ease-out"
              :class="
                workMode
                  ? 'bg-amber-600/90 text-white'
                  : 'bg-gradient-to-br from-sky-500/60 to-blue-600/60 text-white shadow-sky-500/20'
              "
            >
              <template v-if="editingMsgId === msg.id">
                <textarea
                  v-model="editingContent"
                  class="w-full bg-transparent border-none outline-none resize-none text-white custom-scrollbar"
                  rows="3"
                  style="min-width: 200px"
                ></textarea>
                <div class="flex gap-2 justify-end mt-2 pt-2 border-t border-white/20">
                  <button
                    class="p-1 hover:bg-white/20 rounded text-white"
                    title="保存"
                    @click="saveEdit(msg)"
                  >
                    <Check class="w-4 h-4" />
                  </button>
                  <button
                    class="p-1 hover:bg-white/20 rounded text-white"
                    title="取消"
                    @click="cancelEdit"
                  >
                    <X class="w-4 h-4" />
                  </button>
                </div>
              </template>
              <template v-else>
                {{ msg.content }}
              </template>
            </div>
            <div class="flex items-center gap-2 mt-1 mr-1">
              <div
                v-if="!editingMsgId"
                class="opacity-0 group-hover:opacity-100 transition-opacity flex gap-2"
              >
                <button
                  class="text-slate-400 hover:text-sky-500 transition-colors"
                  @click="startEdit(msg)"
                >
                  <Edit2 class="w-3 h-3" />
                </button>
                <button
                  class="text-slate-400 hover:text-red-500 transition-colors"
                  @click="deleteMessage(msg.id)"
                >
                  <Trash2 class="w-3 h-3" />
                </button>
              </div>
              <div
                class="text-[10px] text-right"
                :class="workMode ? 'text-slate-500' : 'text-slate-400'"
              >
                {{ formatTime(msg.timestamp) }}
              </div>
            </div>
          </div>
        </div>

        <!-- 助手消息 -->
        <div
          v-else-if="msg.role === 'assistant'"
          class="flex justify-start mb-4 gap-3 group animate-fade-in-up"
        >
          <!-- 头像 -->
          <div
            class="w-10 h-10 rounded-full flex-shrink-0 flex items-center justify-center text-white shadow-md transition-all overflow-hidden relative animate-float"
            :class="
              workMode
                ? 'bg-gradient-to-br from-indigo-400 to-purple-500'
                : 'bg-gradient-to-br from-sky-400 to-blue-500 shadow-sky-500/20'
            "
          >
            <span class="text-sm font-bold">{{
              msg.senderId && msg.senderId !== 'pero' && msg.senderId !== 'user'
                ? msg.senderId[0].toUpperCase()
                : AGENT_AVATAR_TEXT
            }}</span>
            <!-- 在线状态点 -->
            <div
              class="absolute bottom-0 right-0 w-2.5 h-2.5 bg-emerald-500 border-2 border-white rounded-full"
            ></div>
          </div>

          <div class="max-w-[85%] min-w-[200px] animate-float" style="animation-delay: 1s">
            <!-- 名称与时间 -->
            <div
              class="flex items-center gap-2 mb-1.5 ml-1 opacity-0 group-hover:opacity-100 transition-opacity duration-300"
            >
              <span
                class="text-xs font-bold"
                :class="workMode ? 'text-indigo-300' : 'text-slate-500'"
                >{{
                  msg.senderId && msg.senderId !== 'pero' && msg.senderId !== 'user'
                    ? msg.senderId
                    : AGENT_NAME
                }}</span
              >
              <span class="text-[10px] text-slate-400">{{ formatTime(msg.timestamp) }}</span>

              <!-- 操作按钮 -->
              <div v-if="!editingMsgId" class="flex gap-2 ml-2">
                <button
                  class="transition-colors"
                  :class="[
                    playingMsgId === msg.id
                      ? 'text-sky-500 animate-pulse'
                      : 'text-slate-400 hover:text-sky-500',
                    isLoadingAudio && playingMsgId === msg.id ? 'cursor-wait' : ''
                  ]"
                  :title="playingMsgId === msg.id ? '停止播放' : '播放语音'"
                  @click="playMessage(msg)"
                >
                  <component :is="playingMsgId === msg.id ? Square : Volume2" class="w-3 h-3" />
                </button>
                <button
                  class="text-slate-400 hover:text-sky-500 transition-colors"
                  @click="startEdit(msg)"
                >
                  <Edit2 class="w-3 h-3" />
                </button>
                <button
                  class="text-slate-400 hover:text-red-500 transition-colors"
                  @click="deleteMessage(msg.id)"
                >
                  <Trash2 class="w-3 h-3" />
                </button>
              </div>
            </div>

            <div
              class="p-4 rounded-2xl rounded-tl-sm shadow-sm text-sm leading-relaxed font-sans border transition-all flex flex-col gap-3 backdrop-blur-xl hover:scale-[1.02] hover:-translate-y-[2px] hover:shadow-xl relative hover:z-10 duration-300 ease-out"
              :class="
                workMode
                  ? 'bg-[#1e293b]/90 text-slate-200 border-slate-700/50'
                  : 'bg-white/30 text-slate-700 border-white/20 shadow-lg shadow-sky-100/30'
              "
            >
              <template v-if="editingMsgId === msg.id">
                <textarea
                  v-model="editingContent"
                  class="w-full bg-transparent border-none outline-none resize-none custom-scrollbar"
                  :class="workMode ? 'text-slate-200' : 'text-slate-700'"
                  rows="10"
                ></textarea>
                <div
                  class="flex gap-2 justify-end mt-2 pt-2 border-t"
                  :class="workMode ? 'border-slate-700' : 'border-slate-200'"
                >
                  <button
                    class="p-1 hover:bg-black/10 rounded"
                    :class="workMode ? 'text-slate-300' : 'text-slate-600'"
                    title="Save"
                    @click="saveEdit(msg)"
                  >
                    <Check class="w-4 h-4" />
                  </button>
                  <button
                    class="p-1 hover:bg-black/10 rounded"
                    :class="workMode ? 'text-slate-300' : 'text-slate-600'"
                    title="Cancel"
                    @click="cancelEdit"
                  >
                    <X class="w-4 h-4" />
                  </button>
                </div>
              </template>
              <template v-else>
                <template
                  v-if="
                    !msg.content &&
                    msg.role === 'assistant' &&
                    idx === messages.length - 1 &&
                    isSending
                  "
                >
                  <div class="flex items-center gap-2 h-6 px-1">
                    <span class="w-1.5 h-1.5 bg-slate-400 rounded-full animate-bounce"></span>
                    <span
                      class="w-1.5 h-1.5 bg-slate-400 rounded-full animate-bounce delay-100"
                    ></span>
                    <span
                      class="w-1.5 h-1.5 bg-slate-400 rounded-full animate-bounce delay-200"
                    ></span>
                    <span class="text-xs text-slate-400 ml-2 font-medium"
                      >{{ agentName }} 正在思考...</span
                    >
                  </div>
                </template>
                <template v-for="(segment, sIdx) in parseMessage(msg.content)" v-else :key="sIdx">
                  <!-- 思考过程块 -->
                  <div
                    v-if="segment.type === 'thinking'"
                    class="rounded-lg overflow-hidden border my-1 transition-all duration-300"
                    :class="
                      workMode
                        ? 'bg-slate-800/50 border-slate-700'
                        : 'bg-slate-50/50 border-slate-200/60'
                    "
                  >
                    <div
                      class="px-3 py-1.5 flex items-center justify-between cursor-pointer select-none border-b transition-colors"
                      :class="
                        workMode
                          ? 'text-sky-400 border-slate-700 hover:bg-slate-700/50'
                          : 'text-slate-500 bg-slate-100/30 border-slate-200/60 hover:bg-slate-100/50'
                      "
                      @click="toggleCollapse(idx, sIdx)"
                    >
                      <div class="flex items-center gap-2 text-xs font-bold">
                        <Brain class="w-3.5 h-3.5" />
                        <span>思考过程 (Thinking Process)</span>
                      </div>
                      <span
                        class="text-[10px] transition-transform duration-200"
                        :class="{ 'rotate-180': isCollapsed(idx, sIdx) }"
                        >▼</span
                      >
                    </div>
                    <div
                      v-show="!isCollapsed(idx, sIdx)"
                      class="p-3 text-xs italic opacity-80 whitespace-pre-wrap font-mono leading-relaxed text-slate-500"
                    >
                      {{ segment.content }}
                    </div>
                  </div>

                  <!-- 独白块 -->
                  <div
                    v-else-if="segment.type === 'monologue'"
                    class="rounded-lg overflow-hidden border relative my-1 transition-all duration-300"
                    :class="
                      workMode
                        ? 'bg-pink-900/10 border-pink-500/20'
                        : 'bg-pink-50/30 border-pink-100/60'
                    "
                  >
                    <div
                      class="px-3 py-1.5 flex items-center justify-between cursor-pointer select-none border-b transition-colors"
                      :class="[
                        workMode
                          ? 'text-pink-400 border-pink-500/10 hover:bg-pink-900/20'
                          : 'text-pink-400 bg-pink-50/30 border-pink-100/60 hover:bg-pink-50/60'
                      ]"
                      @click="toggleCollapse(idx, sIdx)"
                    >
                      <div class="flex items-center gap-2 text-xs font-bold">
                        <MessageSquareQuote class="w-3.5 h-3.5" />
                        <span>内心独白</span>
                      </div>
                      <span
                        class="text-[10px] transition-transform duration-200"
                        :class="{ 'rotate-180': isCollapsed(idx, sIdx) }"
                        >▼</span
                      >
                    </div>
                    <div
                      v-show="!isCollapsed(idx, sIdx)"
                      class="px-3 py-3 text-xs opacity-90 whitespace-pre-wrap leading-relaxed text-slate-600"
                    >
                      {{ segment.content }}
                    </div>
                  </div>

                  <!-- 工具调用块 (NIT) -->
                  <div
                    v-else-if="segment.type === 'tool'"
                    class="rounded-xl overflow-hidden border shadow-sm my-2"
                    :class="workMode ? 'border-blue-500/30' : 'border-blue-100/60'"
                  >
                    <div
                      class="px-3 py-2 text-xs font-bold text-white flex items-center justify-between cursor-pointer"
                      :class="
                        workMode
                          ? 'bg-blue-600/80'
                          : 'bg-gradient-to-r from-blue-500/80 to-sky-500/80 backdrop-blur-sm'
                      "
                      @click="toggleCollapse(idx, sIdx)"
                    >
                      <div class="flex items-center gap-2">
                        <Terminal class="w-3.5 h-3.5" />
                        <span>NIT: {{ segment.name }}</span>
                      </div>
                      <div class="flex items-center gap-2">
                        <span class="font-mono opacity-70 text-[10px]">{{ segment.id }}</span>
                        <span
                          class="text-[10px] transition-transform duration-200"
                          :class="{ 'rotate-180': isCollapsed(idx, sIdx) }"
                          >▼</span
                        >
                      </div>
                    </div>
                    <div
                      v-show="!isCollapsed(idx, sIdx)"
                      class="p-3 text-xs font-mono overflow-x-auto custom-scrollbar whitespace-pre"
                      :class="
                        workMode ? 'bg-[#0f172a]/80 text-blue-100' : 'bg-slate-50/50 text-slate-600'
                      "
                    >
                      {{ segment.content }}
                    </div>
                  </div>

                  <!-- 普通文本 -->
                  <div
                    v-else
                    class="min-h-[1.5em]"
                    :class="workMode ? 'text-slate-100' : 'text-slate-700'"
                  >
                    <AsyncMarkdown v-if="segment.content" :content="segment.content" />
                  </div>
                </template>
              </template>
            </div>
          </div>
        </div>

        <!-- 思维链卡片 -->
        <div v-else-if="msg.role === 'thought_chain'" class="flex justify-start mb-4 gap-3 w-full">
          <div class="w-10 h-10 flex-shrink-0"></div>
          <!-- Spacer -->
          <!-- 占位符 -->
          <div class="w-full max-w-2xl">
            <div
              class="rounded-2xl overflow-hidden shadow-lg transition-all duration-300 border hover:shadow-xl hover:scale-[1.01] hover:-translate-y-[2px]"
              :class="
                workMode
                  ? 'bg-[#0f172a] border-slate-700/50'
                  : 'bg-white/40 backdrop-blur-md border-white/30 shadow-sky-200/30'
              "
            >
              <!-- Header -->
              <!-- 头部 -->
              <div
                class="px-4 py-3 flex items-center justify-between cursor-pointer transition-colors"
                :class="workMode ? 'hover:bg-slate-800/50' : 'hover:bg-white/40'"
                @click="msg.isCollapsed = !msg.isCollapsed"
              >
                <div class="flex items-center gap-2">
                  <div class="relative">
                    <div
                      class="w-2 h-2 rounded-full"
                      :class="[
                        workMode ? 'bg-sky-400' : 'bg-sky-500',
                        { 'animate-pulse': msg.isThinking }
                      ]"
                    ></div>
                    <div
                      v-if="msg.isThinking"
                      class="absolute inset-0 w-2 h-2 rounded-full animate-ping opacity-75"
                      :class="workMode ? 'bg-sky-400' : 'bg-sky-500'"
                    ></div>
                  </div>
                  <span
                    class="text-xs font-bold tracking-wide"
                    :class="workMode ? 'text-sky-400' : 'text-sky-600'"
                  >
                    {{ msg.isThinking ? 'PERO 正在思考...' : '思考过程' }}
                  </span>
                </div>
                <div class="flex items-center gap-2">
                  <span
                    v-if="msg.steps.length > 0"
                    class="text-[10px] font-mono"
                    :class="workMode ? 'text-slate-500' : 'text-slate-500'"
                    >{{ msg.steps.length }} 步</span
                  >
                  <span
                    class="transition-transform duration-200"
                    :class="[
                      workMode ? 'text-slate-500' : 'text-slate-400',
                      { 'rotate-180': !msg.isCollapsed }
                    ]"
                    >▼</span
                  >
                </div>
              </div>

              <!-- 内容 -->
              <div
                v-if="!msg.isCollapsed"
                class="max-h-[400px] overflow-y-auto custom-scrollbar"
                :class="
                  workMode
                    ? 'bg-[#020617]/50 border-t border-slate-800/50'
                    : 'bg-white/30 border-t border-white/20'
                "
              >
                <div class="p-4 space-y-3">
                  <div
                    v-for="(step, sIdx) in msg.steps"
                    :key="sIdx"
                    class="relative pl-4 border-l-2"
                    :class="{
                      'border-sky-500/50': step.type === 'thinking',
                      'border-emerald-500/50': step.type === 'action',
                      'border-red-500/50': step.type === 'error',
                      'border-amber-500/50': step.type === 'reflection'
                    }"
                  >
                    <div
                      class="absolute -left-[5px] top-0 w-2 h-2 rounded-full"
                      :class="{
                        'bg-sky-500': step.type === 'thinking',
                        'bg-emerald-500': step.type === 'action',
                        'bg-red-500': step.type === 'error',
                        'bg-amber-500': step.type === 'reflection'
                      }"
                    ></div>
                    <div
                      class="text-[10px] font-bold uppercase tracking-wider mb-1 opacity-70"
                      :class="[
                        workMode ? '' : 'font-semibold',
                        {
                          'text-sky-400': step.type === 'thinking' && workMode,
                          'text-sky-700': step.type === 'thinking' && !workMode,
                          'text-emerald-400': step.type === 'action' && workMode,
                          'text-emerald-700': step.type === 'action' && !workMode,
                          'text-red-400': step.type === 'error' && workMode,
                          'text-red-700': step.type === 'error' && !workMode,
                          'text-amber-400': step.type === 'reflection' && workMode,
                          'text-amber-700': step.type === 'reflection' && !workMode
                        }
                      ]"
                    >
                      {{ step.type }}
                    </div>
                    <div
                      class="text-xs font-mono whitespace-pre-wrap leading-relaxed opacity-90"
                      :class="workMode ? 'text-slate-300' : 'text-slate-700'"
                    >
                      {{ step.content }}
                    </div>
                  </div>
                </div>

                <!-- 操作 -->
                <div
                  v-if="msg.isThinking"
                  class="px-4 py-2 flex gap-2 border-t"
                  :class="
                    workMode ? 'bg-slate-900/50 border-slate-800/50' : 'bg-white/40 border-white/20'
                  "
                >
                  <button
                    class="px-3 py-1 text-xs rounded-md border transition-all font-medium flex items-center gap-1"
                    :class="
                      workMode
                        ? 'bg-red-500/10 text-red-400 hover:bg-red-500/20 border-red-500/20'
                        : 'bg-red-100 text-red-600 hover:bg-red-200 border-red-200'
                    "
                    @click="injectInstruction('stop')"
                  >
                    <span
                      class="w-1.5 h-1.5 rounded-sm"
                      :class="workMode ? 'bg-red-500' : 'bg-red-600'"
                    ></span>
                    停止
                  </button>
                  <button
                    class="px-3 py-1 text-xs rounded-md border transition-all font-medium flex items-center gap-1"
                    :class="
                      workMode
                        ? 'bg-amber-500/10 text-amber-400 hover:bg-amber-500/20 border-amber-500/20'
                        : 'bg-amber-100 text-amber-600 hover:bg-amber-200 border-amber-200'
                    "
                    @click="togglePause"
                  >
                    <span
                      class="w-1.5 h-1.5 rounded-full"
                      :class="workMode ? 'bg-amber-500' : 'bg-amber-600'"
                    ></span>
                    {{ msg.isPaused ? '继续' : '暂停' }}
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 输入区域 -->
    <div class="p-6 pt-0 bg-transparent flex-shrink-0 relative z-20">
      <div
        class="rounded-2xl shadow-xl border transition-all flex flex-col overflow-hidden"
        :class="
          workMode
            ? 'bg-[#0f172a] border-slate-700/50 focus-within:border-amber-500/50 focus-within:shadow-amber-500/10'
            : 'bg-white/60 border-sky-200/50 focus-within:border-sky-400/50 focus-within:shadow-sky-400/20 backdrop-blur-md'
        "
      >
        <!-- 待发送图片预览 (移入输入框内部容器) -->
        <div
          v-if="pendingImages.length > 0"
          class="px-4 pt-4 pb-2 flex gap-2 overflow-x-auto custom-scrollbar border-b border-white/10"
        >
          <div v-for="(img, idx) in pendingImages" :key="idx" class="relative group flex-shrink-0">
            <img
              :src="img.url"
              class="h-16 w-16 object-cover rounded-lg shadow-sm border border-white/10"
            />
            <button
              class="absolute -top-1.5 -right-1.5 bg-white rounded-full shadow-md hover:scale-110 transition-transform text-slate-500 hover:text-red-500"
              @click="removePendingImage(idx)"
            >
              <XCircle class="w-4 h-4 fill-current" />
            </button>
          </div>
        </div>

        <!-- 文本输入区 -->
        <textarea
          v-model="input"
          class="w-full bg-transparent text-sm p-4 focus:outline-none resize-none min-h-[56px] max-h-48 custom-scrollbar font-sans border-none"
          :class="[
            workMode
              ? 'text-slate-200 placeholder-slate-500'
              : 'text-slate-800 placeholder-slate-400',
            disabled ? 'opacity-50 cursor-not-allowed' : ''
          ]"
          :placeholder="disabled ? '工作区初始化中...' : `问 ${agentName} 任何问题...`"
          :disabled="isInputLocked || disabled"
          style="field-sizing: content"
          @keydown.enter.prevent="handleEnter"
        ></textarea>

        <!-- 底部工具栏 (图标外置到输入框内部底部) -->
        <div
          class="px-3 py-2 flex items-center justify-between border-t transition-colors"
          :class="workMode ? 'border-slate-700/50 bg-slate-900/30' : 'border-white/20 bg-white/30'"
        >
          <div class="flex items-center gap-2">
            <!-- 图片上传按钮 -->
            <input
              ref="fileInput"
              type="file"
              accept="image/*"
              multiple
              class="hidden"
              @change="handleFileSelect"
            />
            <button
              :disabled="isInputLocked || disabled || !isVisionEnabled"
              class="h-9 w-9 rounded-xl transition-all flex items-center justify-center group relative border"
              :class="
                workMode
                  ? !isVisionEnabled
                    ? 'opacity-30 cursor-not-allowed text-slate-500 border-transparent'
                    : 'text-amber-500 border-amber-500/20 hover:bg-amber-500/10 hover:border-amber-500/40'
                  : !isVisionEnabled
                    ? 'opacity-30 cursor-not-allowed text-slate-400 border-transparent'
                    : 'text-sky-600 border-sky-200 bg-sky-50/50 hover:bg-sky-100 hover:border-sky-300'
              "
              :title="!isVisionEnabled ? '当前模型不支持视觉功能 (请在设置中开启)' : '上传图片'"
              @click="triggerUpload"
            >
              <ImageIcon class="w-4.5 h-4.5" />
            </button>
          </div>

          <!-- 发送按钮 -->
          <button
            :disabled="isInputLocked || (!input.trim() && pendingImages.length === 0) || disabled"
            class="h-9 px-4 rounded-xl transition-all shadow-sm flex items-center justify-center gap-2 text-xs font-bold border"
            :class="
              workMode
                ? 'bg-amber-500 border-amber-600 hover:bg-amber-600 text-white shadow-amber-500/20 disabled:bg-slate-700 disabled:border-transparent disabled:text-slate-500 disabled:shadow-none'
                : 'bg-sky-500 border-sky-600 hover:bg-sky-600 text-white shadow-sky-500/20 disabled:bg-slate-200 disabled:border-transparent disabled:text-slate-400 disabled:shadow-none'
            "
            @click="sendMessage"
          >
            <span v-if="!isSending">发送</span>
            <div
              v-else
              class="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin"
            ></div>
            <svg
              v-if="!isSending"
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 24 24"
              fill="currentColor"
              class="w-3.5 h-3.5 group-hover:translate-x-0.5 transition-transform"
            >
              <path
                d="M3.478 2.404a.75.75 0 0 0-.926.941l2.432 7.905H13.5a.75.75 0 0 1 0 1.5H4.984l-2.432 7.905a.75.75 0 0 0 .926.94 60.519 60.519 0 0 0 18.445-8.986.75.75 0 0 0 0-1.218A60.517 60.517 0 0 0 3.478 2.404Z"
              />
            </svg>
          </button>
        </div>
      </div>
      <div
        class="text-center mt-3 text-[9px] font-bold tracking-widest opacity-30 uppercase"
        :class="workMode ? 'text-slate-500' : 'text-slate-400'"
      >
        {{ AGENT_NAME }} AI AGENT · POWERED BY RE-ACT ENGINE
      </div>
    </div>

    <CustomDialog
      v-model:visible="deleteDialogVisible"
      type="confirm"
      title="删除消息"
      :message="deleteDialogMessage"
      @confirm="handleConfirmDelete"
    />
  </div>
</template>

<script setup>
import { ref, watch, nextTick, onMounted, onUnmounted, computed } from 'vue'
import { listen, emit } from '@/utils/ipcAdapter'
import {
  Brain,
  MessageSquareQuote,
  Terminal,
  Square,
  Clock,
  Edit2,
  Trash2,
  Check,
  X,
  Volume2,
  AlertTriangle,
  Image as ImageIcon,
  XCircle
} from 'lucide-vue-next'
import AsyncMarkdown from '../markdown/AsyncMarkdown.vue'
import CustomDialog from '../ui/CustomDialog.vue'
import { AGENT_NAME, AGENT_AVATAR_TEXT } from '../../config'
import { gatewayClient } from '../../api/gateway'

const API_BASE = 'http://127.0.0.1:9120'

const props = defineProps({
  workMode: Boolean,
  disabled: Boolean,
  mode: { type: String, default: 'direct' }, // 'direct' | 'group'
  targetId: { type: String, default: 'pero' },
  agentName: { type: String, default: AGENT_NAME }
})

const getRiskLabel = (level) => {
  if (level === undefined) return '未知'
  switch (level) {
    case 0:
      return '安全'
    case 1:
      return '注意'
    case 2:
      return '低风险'
    case 3:
      return '中风险'
    case 4:
      return '高风险'
    default:
      return level >= 2 ? '高风险' : '常规'
  }
}

const getRiskLevelColor = (level, type) => {
  const safeLevel = level === undefined ? 1 : level

  // 颜色映射表
  const colors = {
    // Level 0: 安全 (绿色)
    0: {
      header: 'bg-emerald-50 dark:bg-emerald-900/20 border-emerald-100 dark:border-emerald-800/30',
      icon: 'bg-emerald-100 dark:bg-emerald-800/40 text-emerald-600 dark:text-emerald-400',
      badge: 'bg-emerald-500',
      content:
        'text-emerald-600 dark:text-emerald-400 border-emerald-200 dark:border-emerald-800 bg-emerald-50 dark:bg-emerald-900/10',
      warning_box:
        'bg-emerald-50 dark:bg-emerald-900/10 border-emerald-100 dark:border-emerald-900/30',
      warning_icon: 'bg-emerald-100 dark:bg-emerald-800/50 text-emerald-600 dark:text-emerald-400',
      warning_text: 'text-emerald-600 dark:text-emerald-400',
      button: 'bg-emerald-500 hover:bg-emerald-600 shadow-emerald-500/30'
    },
    // Level 1: 注意 (蓝色/青色)
    1: {
      header: 'bg-sky-50 dark:bg-sky-900/20 border-sky-100 dark:border-sky-800/30',
      icon: 'bg-sky-100 dark:bg-sky-800/40 text-sky-600 dark:text-sky-400',
      badge: 'bg-sky-500',
      content:
        'text-sky-600 dark:text-sky-400 border-sky-200 dark:border-sky-800 bg-sky-50 dark:bg-sky-900/10',
      warning_box: 'bg-sky-50 dark:bg-sky-900/10 border-sky-100 dark:border-sky-900/30',
      warning_icon: 'bg-sky-100 dark:bg-sky-800/50 text-sky-600 dark:text-sky-400',
      warning_text: 'text-sky-600 dark:text-sky-400',
      button: 'bg-sky-500 hover:bg-sky-600 shadow-sky-500/30'
    },
    // Level 2: 低风险 (琥珀色/黄色)
    2: {
      header: 'bg-amber-50 dark:bg-amber-900/20 border-amber-100 dark:border-amber-800/30',
      icon: 'bg-amber-100 dark:bg-amber-800/40 text-amber-600 dark:text-amber-400',
      badge: 'bg-amber-500',
      content:
        'text-amber-600 dark:text-amber-400 border-amber-200 dark:border-amber-800 bg-amber-50 dark:bg-amber-900/10',
      warning_box: 'bg-amber-50 dark:bg-amber-900/10 border-amber-100 dark:border-amber-900/30',
      warning_icon: 'bg-amber-100 dark:bg-amber-800/50 text-amber-600 dark:text-amber-400',
      warning_text: 'text-amber-600 dark:text-amber-400',
      button: 'bg-amber-500 hover:bg-amber-600 shadow-amber-500/30'
    },
    // Level 3: 中风险 (橙色)
    3: {
      header: 'bg-orange-50 dark:bg-orange-900/20 border-orange-100 dark:border-orange-800/30',
      icon: 'bg-orange-100 dark:bg-orange-800/40 text-orange-600 dark:text-orange-400',
      badge: 'bg-orange-500',
      content:
        'text-orange-600 dark:text-orange-400 border-orange-200 dark:border-orange-800 bg-orange-50 dark:bg-orange-900/10',
      warning_box: 'bg-orange-50 dark:bg-orange-900/10 border-orange-100 dark:border-orange-900/30',
      warning_icon: 'bg-orange-100 dark:bg-orange-800/50 text-orange-600 dark:text-orange-400',
      warning_text: 'text-orange-600 dark:text-orange-400',
      button: 'bg-orange-500 hover:bg-orange-600 shadow-orange-500/30'
    },
    // Level 4: 高风险 (红色)
    4: {
      header: 'bg-red-50 dark:bg-red-900/20 border-red-100 dark:border-red-800/30',
      icon: 'bg-red-100 dark:bg-red-800/40 text-red-600 dark:text-red-400 animate-pulse',
      badge: 'bg-red-500',
      content: 'text-red-300 border-red-900/50 bg-red-950/20',
      warning_box: 'bg-red-50 dark:bg-red-900/10 border-red-100 dark:border-red-900/30',
      warning_icon: 'bg-red-100 dark:bg-red-800/50 text-red-600 dark:text-red-400',
      warning_text: 'text-red-600 dark:text-red-400',
      button: 'bg-red-500 hover:bg-red-600 shadow-red-500/30'
    }
  }

  // 回退
  if (!colors[safeLevel]) {
    return safeLevel >= 2 ? colors[4][type] : colors[2][type]
  }

  return colors[safeLevel][type]
}

// 确认状态
const pendingConfirmation = ref(null)

// 设置确认监听器
onMounted(async () => {
  checkVisionCapability()
  fetchHistory(true)

  // 1. 监听从父级或全局总线转发的 WebSocket 消息（通过 Gateway）
  gatewayClient.on('action:new_message', (data) => {
    const payload = data.params || data
    // 如果新消息属于当前会话或相关，则追加
    // 暂时假设默认会话或检查 payload.session_id
    console.log('[ChatInterface] Received new message via Gateway:', payload)

    // 检查重复
    // 1. 检查精确 ID 匹配
    const exists = messages.value.some((m) => m.id == payload.id)

    // 2. 检查是否有匹配此内容的待定消息（无 ID）
    // 这处理从“流式/待定” -> “已持久化”的过渡
    let pendingMatchIndex = -1

    if (!exists) {
      // [修复] 检查待定用户消息（乐观更新）
      if (payload.role === 'user') {
        // 向后查找待定用户消息
        for (let i = messages.value.length - 1; i >= 0; i--) {
          const m = messages.value[i]
          if (m.role === 'user' && !m.id && m.content === payload.content) {
            pendingMatchIndex = i
            break
          }
        }
      }
      // [修复] 检查待定助手消息
      else if (payload.role === 'assistant') {
        const lastMsgIndex = messages.value.length - 1
        const lastMsg = messages.value[lastMsgIndex]

        // 如果最后一条消息是助手，没有 ID，且内容相似或者是最后一条
        if (lastMsg && lastMsg.role === 'assistant' && !lastMsg.id) {
          // 我们假设这是流的持久化版本
          pendingMatchIndex = lastMsgIndex
        }
      }
    }

    if (!exists) {
      if (pendingMatchIndex !== -1) {
        // 更新待定消息的真实 ID 和最终内容
        const msg = messages.value[pendingMatchIndex]
        msg.id = payload.id
        msg.content = payload.raw_content || payload.content // 使用 raw_content 保留 NIT 日志
        msg.timestamp = payload.timestamp
        msg.senderId = payload.agent_id || 'pero'
        msg.pair_id = payload.pair_id
        msg.metadata = JSON.parse(payload.metadata || '{}')
        // 图片通常单独处理，但如果 payload 包含它们，则更新
      } else {
        // 添加为新消息
        messages.value.push({
          id: payload.id,
          role: payload.role,
          content: payload.raw_content || payload.content, // 使用 raw_content 保留 NIT 日志
          timestamp: payload.timestamp,
          senderId: payload.agent_id || 'pero',
          pair_id: payload.pair_id,
          images: [], // 图片单独处理或通过 metadata
          metadata: JSON.parse(payload.metadata || '{}')
        })
        scrollToBottom()
      }
    }
  })

  gatewayClient.on('action:confirmation_request', (payload) => {
    pendingConfirmation.value = {
      id: payload.id,
      command: payload.command,
      riskInfo: payload.risk_info,
      isHighRisk: payload.is_high_risk || false
    }
  })
})

let unlistenConfirmation = null

const highlightCommand = (command, highlight) => {
  if (!highlight) return command
  // 使用正则替换以支持多次出现，忽略大小写
  try {
    const regex = new RegExp(`(${highlight})`, 'gi')
    return command.replace(
      regex,
      '<span class="bg-red-500/30 text-red-200 font-bold px-1 rounded">$1</span>'
    )
  } catch {
    return command
  }
}

const respondConfirmation = async (approved) => {
  if (!pendingConfirmation.value) return

  // 通过 Gateway 发送回执
  try {
    await gatewayClient.sendRequest('backend', 'confirm', {
      id: pendingConfirmation.value.id,
      approved: approved ? 'true' : 'false'
    })
  } catch (e) {
    console.error('发送确认响应失败:', e)
  }

  pendingConfirmation.value = null
}

// 当前活动指令状态
const activeCommand = ref(null)

const skipCommandWait = async () => {
  if (!activeCommand.value) return

  try {
    await fetch(`${API_BASE}/api/ide/tools/terminal/skip`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ pid: activeCommand.value.pid })
    })
    // 乐观地清除覆盖层
    activeCommand.value = null
  } catch (e) {
    console.error('跳过指令失败', e)
  }
}

onUnmounted(() => {
  if (unlistenConfirmation) unlistenConfirmation()
})

// TTS 语音状态
const playingMsgId = ref(null)
const isLoadingAudio = ref(false)
const currentAudio = ref(null)

const playMessage = async (msg) => {
  // 如果当前正在播放这条消息，则停止
  if (playingMsgId.value === msg.id) {
    if (currentAudio.value) {
      currentAudio.value.pause()
      currentAudio.value = null
    }
    playingMsgId.value = null
    isLoadingAudio.value = false
    return
  }

  // 停止之前的播放
  if (currentAudio.value) {
    currentAudio.value.pause()
    currentAudio.value = null
  }

  playingMsgId.value = msg.id
  isLoadingAudio.value = true

  try {
    const response = await fetch(`${API_BASE}/api/tts/preview`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ text: msg.content })
    })

    if (!response.ok) {
      throw new Error('TTS request failed')
    }

    const blob = await response.blob()
    const url = URL.createObjectURL(blob)
    const audio = new Audio(url)

    currentAudio.value = audio

    audio.onended = () => {
      playingMsgId.value = null
      currentAudio.value = null
      isLoadingAudio.value = false
      URL.revokeObjectURL(url)
    }

    audio.onerror = (e) => {
      console.error('Audio playback error:', e)
      playingMsgId.value = null
      currentAudio.value = null
      isLoadingAudio.value = false
      URL.revokeObjectURL(url)
    }

    await audio.play()
    isLoadingAudio.value = false // 开始播放，停止加载动画
  } catch (error) {
    console.error('TTS Error:', error)
    playingMsgId.value = null
    isLoadingAudio.value = false
    currentAudio.value = null
  }
}

const emitEvent = defineEmits(['mode-change'])

const messages = ref([])
const offset = ref(0)
const hasMore = ref(true)
const input = ref('')
const fileInput = ref(null)
const pendingImages = ref([])
const isVisionEnabled = ref(false)

const checkVisionCapability = async () => {
  try {
    const configRes = await fetch(`${API_BASE}/api/configs`)
    if (!configRes.ok) return
    const configs = await configRes.json()
    const modelId = configs.current_model_id

    if (modelId) {
      const modelsRes = await fetch(`${API_BASE}/api/models`)
      if (!modelsRes.ok) return
      const models = await modelsRes.json()
      const currentModel = models.find((m) => m.id == modelId)
      if (currentModel && currentModel.enable_vision) {
        isVisionEnabled.value = true
      } else {
        isVisionEnabled.value = false
      }
    }
  } catch (e) {
    console.error('Failed to check vision capability', e)
  }
}

const triggerUpload = () => {
  fileInput.value.click()
}

const handleFileSelect = (event) => {
  const files = event.target.files
  if (!files || files.length === 0) return

  for (let i = 0; i < files.length; i++) {
    const file = files[i]
    if (!file.type.startsWith('image/')) continue

    const reader = new FileReader()
    reader.onload = (e) => {
      pendingImages.value.push({
        file: file,
        url: e.target.result // Data URL 用于预览和发送
      })
    }
    reader.readAsDataURL(file)
  }
  // 重置输入
  event.target.value = ''
}

const removePendingImage = (index) => {
  pendingImages.value.splice(index, 1)
}

const msgContainer = ref(null)
const isSending = ref(false)
const isInputLocked = computed(() => {
  return isSending.value || (activeThoughtChain.value && activeThoughtChain.value.isThinking)
})

// 配置
const HISTORY_LIMIT = 30

const parseMessage = (content) => {
  if (!content) return [{ type: 'text', content: '' }]

  const segments = []

  // 健壮的正则模式
  // 1. 思考/独白: 【Thinking: ...】 或 【Monologue: ...】 (Monologue 为旧版兼容)
  // 2. NIT 工具: <nit>...</nit> 或 <nit-ID>...</nit-ID> 或 [[[NIT_CALL]]]...[[[NIT_END]]]
  // 3. DeepSeek 思考: <think>...</think>

  const regex =
    /【(Thinking|Monologue)\s*:\s*([\s\S]*?)】|<(nit(?:-[a-zA-Z0-9-]+)?)>([\s\S]*?)<\/\3>|\[\[\[NIT_CALL\]\]\]([\s\S]*?)\[\[\[NIT_END\]\]\]|<think>([\s\S]*?)<\/think>/g

  let lastIndex = 0
  let match

  while ((match = regex.exec(content)) !== null) {
    // 添加匹配前的文本
    if (match.index > lastIndex) {
      const text = content.slice(lastIndex, match.index)
      if (text.trim()) {
        segments.push({ type: 'text', content: text })
      }
    }

    if (match[1]) {
      // Thinking or Monologue (Standard)
      // 思考或独白（标准）
      // [兼容性保留] Monologue 类型在 2024-02 之后已废弃，合并入 Thinking，此处保留解析以支持历史记录显示
      segments.push({
        type: match[1].toLowerCase(),
        content: match[2].trim()
      })
    } else if (match[6]) {
      // DeepSeek <think>
      // DeepSeek <think>
      segments.push({
        type: 'thinking',
        content: match[6].trim()
      })
    } else if (match[3] || match[5]) {
      // NIT 工具（XML 或括号）
      const nitTag = match[3]
      const code = match[4] || match[5] // Group 4 用于 XML，Group 5 用于括号

      // 如果存在，从标签中提取 ID（例如 nit-123 -> 123）
      let toolId = 'unknown'
      if (nitTag && nitTag.startsWith('nit-')) {
        toolId = nitTag.substring(4)
      }

      const trimmedCode = code.trim()

      let toolName = '脚本执行' // Script Execution -> 脚本执行
      const funcMatch = /([a-zA-Z_][a-zA-Z0-9_]*)\./.exec(trimmedCode)
      if (funcMatch) {
        toolName = funcMatch[1]
      }

      segments.push({
        type: 'tool',
        name: toolName,
        id: toolId,
        content: trimmedCode
      })
    }

    lastIndex = regex.lastIndex
  }

  // 添加剩余文本
  if (lastIndex < content.length) {
    let text = content.slice(lastIndex)

    // 移除 NIT 数据行
    text = text.replace(/(\n|^)\s*data:\s*\{"triggers":[\s\S]*?(\n|$)/g, '$1')

    if (text.trim()) {
      segments.push({ type: 'text', content: text })
    }
  }

  return segments.length > 0
    ? segments
    : [
        {
          type: 'text',
          content: content.replace(/(\n|^)\s*data:\s*\{"triggers":[\s\S]*?(\n|$)/g, '$1')
        }
      ]
}

// --- 折叠逻辑 ---
const collapsedStates = ref(new Set())

const toggleCollapse = (msgIdx, segIdx) => {
  const key = `${msgIdx}-${segIdx}`
  if (collapsedStates.value.has(key)) {
    collapsedStates.value.delete(key)
  } else {
    collapsedStates.value.add(key)
  }
}

const isCollapsed = (msgIdx, segIdx) => {
  return collapsedStates.value.has(`${msgIdx}-${segIdx}`)
}

// --- 编辑逻辑 ---
const editingMsgId = ref(null)
const editingContent = ref('')

const startEdit = (msg) => {
  editingMsgId.value = msg.id
  editingContent.value = msg.content
}

const cancelEdit = () => {
  editingMsgId.value = null
  editingContent.value = ''
}

const saveEdit = async (msg) => {
  if (!editingContent.value.trim() || !msg.id) return

  try {
    const res = await fetch(`${API_BASE}/api/history/${msg.id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content: editingContent.value })
    })

    if (res.ok) {
      msg.content = editingContent.value
      editingMsgId.value = null
    }
  } catch (e) {
    console.error('Failed to edit message', e)
  }
}

// --- 对话框逻辑 ---
const deleteDialogVisible = ref(false)
const deleteDialogMessage = ref('')
const pendingDeleteId = ref(null)

const deleteMessage = (msgId) => {
  pendingDeleteId.value = msgId
  deleteDialogMessage.value = '确定删除这条消息吗？此操作无法撤销。'
  deleteDialogVisible.value = true
}

const handleConfirmDelete = async () => {
  if (!pendingDeleteId.value) return

  try {
    const res = await fetch(`${API_BASE}/api/history/${pendingDeleteId.value}`, {
      method: 'DELETE'
    })

    if (res.ok) {
      const deletedMsg = messages.value.find((m) => m.id === pendingDeleteId.value)
      if (deletedMsg && deletedMsg.pair_id) {
        // 如果有 pair_id，删除本地所有匹配的消息（原子化同步）
        messages.value = messages.value.filter((m) => m.pair_id !== deletedMsg.pair_id)
      } else {
        // 否则仅删除单条
        messages.value = messages.value.filter((m) => m.id !== pendingDeleteId.value)
      }
    }
  } catch (e) {
    console.error('Failed to delete message', e)
  } finally {
    deleteDialogVisible.value = false
    pendingDeleteId.value = null
  }
}

// --- Gateway 事件逻辑 ---
const handleVoiceUpdate = (data) => {
  const params = data.params || data
  if (params.target === 'pet_view_only') return

  // [修复] 处理来自 RealtimeSessionManager 的 text_response 和 transcription（语音/桌面模式）
  if (params.type === 'transcription') {
    // 来自语音/桌面的用户输入
    if (!isSending.value) {
      const content = params.content || params.text
      messages.value.push({ role: 'user', content: content, timestamp: new Date().toISOString() })
      scrollToBottom()
    }
  } else if (params.type === 'text_response') {
    // 来自语音/桌面的助手回复（增量或最终）
    // [修复] 即使 isSending 为 true，我们可能会通过 Gateway 接收异步更新（例如来自工具输出）
    // 但通常 fetch 处理响应。
    // 然而，如果响应为空（例如仅工具调用），fetch 可能会返回空。
    // 如果内容不为空，让我们依赖 Gateway 进行文本更新。

    if (params.content) {
      const content = params.content
      const lastMsg = messages.value[messages.value.length - 1]

      if (lastMsg && lastMsg.role === 'assistant') {
        // 如果看起来是延续或替换，则更新现有消息
        // 由于 RealtimeSessionManager 发送完整的累积文本到 'content'，我们可以直接替换它。
        lastMsg.content = content
        scrollToBottom()
      } else {
        // 新消息
        messages.value.push({
          role: 'assistant',
          content: content,
          timestamp: new Date().toISOString()
        })
        scrollToBottom()
      }
    }
  }

  if (params.status === 'thinking') {
    ensureActiveThoughtChain()
    if (params.detail) {
      const stepContent = params.detail
      const lastStep = activeThoughtChain.value.steps[activeThoughtChain.value.steps.length - 1]
      if (!lastStep || lastStep.content !== stepContent) {
        activeThoughtChain.value.steps.push({
          type: 'thinking',
          content: stepContent
        })
        scrollToBottom()
      }
    }
  } else if (params.status === 'idle') {
    if (activeThoughtChain.value) {
      activeThoughtChain.value.isThinking = false
      activeThoughtChain.value = null
    }
  }
}

const handleTextStream = (data) => {
  const params = data.params || data
  if (params.target === 'pet_view_only') return

  // 如果我们正在主动发送，则忽略流更新（由 fetch 处理）
  if (isSending.value) return

  // 智能追加被动更新
  const lastMsg = messages.value[messages.value.length - 1]
  if (lastMsg && lastMsg.role === 'assistant') {
    // 如果内容只是被扩展，更新它
    // 简单启发式：如果新内容以旧内容开头
    if (params.content.startsWith(lastMsg.content)) {
      lastMsg.content = params.content
      scrollToBottom()
      return
    }
    // 如果新内容是增量（如何知道？），追加？
    // 目前，如果不匹配，假设完全内容替换。
  }

  messages.value.push({
    role: 'assistant',
    content: params.content,
    timestamp: new Date().toISOString()
  })
  scrollToBottom()
}

// [修复] 添加 text_response 处理程序（最终/完整响应广播）
const handleTextResponse = (data) => {
  // 目前逻辑与 text_stream 相同，因为两者都携带 'content'
  handleTextStream(data)
}

const handleTranscription = (data) => {
  const params = data.params || data
  if (!isSending.value) {
    messages.value.push({ role: 'user', content: params.text, timestamp: new Date().toISOString() })
    scrollToBottom()
  }
}

const handleCommandRunning = (data) => {
  const params = data.params || data
  activeCommand.value = {
    command: params.command,
    pid: params.pid
  }
}

const handleCommandFinished = () => {
  activeCommand.value = null
}

const handleModeUpdate = (data) => {
  const params = data.params || data
  if (params.mode === 'work') {
    emitEvent('mode-change', params.is_active === 'true' || params.is_active === true)
  }
}

const activeThoughtChain = ref(null)

const ensureActiveThoughtChain = () => {
  const lastMsg = messages.value[messages.value.length - 1]
  if (lastMsg && lastMsg.role === 'thought_chain' && lastMsg.isThinking) {
    activeThoughtChain.value = lastMsg
    return
  }

  const newChain = {
    role: 'thought_chain',
    isThinking: true,
    isCollapsed: false,
    isPaused: false,
    steps: [],
    timestamp: new Date().toISOString()
  }
  messages.value.push(newChain)
  activeThoughtChain.value = newChain
  scrollToBottom()
}

const togglePause = async () => {
  if (!activeThoughtChain.value) return
  const isPaused = activeThoughtChain.value.isPaused
  const action = isPaused ? 'resume' : 'pause'

  await injectInstruction(action)
  activeThoughtChain.value.isPaused = !isPaused
}

const injectInstruction = async (action) => {
  const sessionId = props.workMode ? 'current_work_session' : props.targetId || 'default'
  try {
    if (action === 'pause') {
      await fetch(`${API_BASE}/api/task/${sessionId}/pause`, { method: 'POST' })
    } else if (action === 'resume') {
      await fetch(`${API_BASE}/api/task/${sessionId}/resume`, { method: 'POST' })
    } else if (action === 'stop') {
      await fetch(`${API_BASE}/api/task/${sessionId}/inject`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ instruction: '停止任务' })
      })
    }
  } catch (e) {
    console.error('Task control failed', e)
  }
}

const formatTime = (ts) => {
  if (!ts) return ''
  const date = new Date(ts)
  const now = new Date()

  const isToday =
    date.getDate() === now.getDate() &&
    date.getMonth() === now.getMonth() &&
    date.getFullYear() === now.getFullYear()

  if (isToday) {
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  } else {
    return (
      date.toLocaleDateString([], { month: '2-digit', day: '2-digit' }) +
      ' ' +
      date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    )
  }
}

const fetchHistory = async (append = false) => {
  // 如果在工作模式下，使用 'ide' 源。
  // 如果在聊天模式下（workMode false），使用 'desktop' 源与 PetView 同步。
  const source = props.workMode ? 'ide' : 'desktop'
  // [修复] 在桌面/直接模式下，DB 中的 session_id 通常为 'default'。
  // 我们使用 agent_id 参数按角色过滤，而不是 session_id。
  const sessionId = props.workMode ? 'current_work_session' : 'default'

  try {
    let res
    if (props.mode === 'group') {
      if (append) {
        hasMore.value = false
        return
      } // Group chat pagination not supported yet
      res = await fetch(
        `${API_BASE}/api/groupchat/rooms/${props.targetId}/history?limit=${HISTORY_LIMIT}`
      )
    } else {
      let url = `${API_BASE}/api/history/${source}/${sessionId}?limit=${HISTORY_LIMIT}&offset=${offset.value}&sort=desc`
      // Pass agent_id for direct mode (targetId acts as agentId)
      if (props.targetId) {
        url += `&agent_id=${props.targetId}`
      }
      res = await fetch(url)
    }

    if (res.ok) {
      const logs = await res.json()
      if (logs.length < HISTORY_LIMIT) {
        hasMore.value = false
      }

      const newMsgs = (Array.isArray(logs) ? logs : [])
        .filter((log) => log && typeof log === 'object')
        .map((log) => {
          let images = []
          try {
            if (log.metadata_json) {
              const meta = JSON.parse(log.metadata_json)
              if (meta.images && Array.isArray(meta.images)) {
                images = meta.images.map(
                  (path) => `${API_BASE}/api/ide/image?path=${encodeURIComponent(path)}`
                )
              }
            }
          } catch (e) {
            console.warn('Meta parse error', e)
          }

          // Group Chat Compatibility
          let role = log.role
          if (props.mode === 'group') {
            role = log.sender_id === 'user' ? 'user' : 'assistant'
          }

          return {
            id: log.id,
            role: role,
            content: log.raw_content || log.content, // Prioritize raw_content for NIT tool display
            timestamp: log.timestamp,
            images: images,
            senderId: log.sender_id,
            pair_id: log.pair_id
          }
        })

      // 反转以获得 [最旧, ..., 最新] 的显示顺序
      // 直接历史记录返回 DESC（最新优先），因此需要反转。
      // 群组历史记录返回 ASC（最旧优先），因此不需要反转。
      if (props.mode !== 'group') {
        newMsgs.reverse()
      }

      if (append) {
        // 将较旧的消息（历史记录）预置到顶部
        // 保存滚动位置
        if (msgContainer.value) {
          const oldHeight = msgContainer.value.scrollHeight
          const oldTop = msgContainer.value.scrollTop

          messages.value.unshift(...newMsgs)

          await nextTick()
          // 恢复相对于新内容的滚动位置
          const newHeight = msgContainer.value.scrollHeight
          msgContainer.value.scrollTop = newHeight - oldHeight + oldTop
        } else {
          messages.value.unshift(...newMsgs)
        }
      } else {
        // 初始加载
        messages.value = newMsgs
        await nextTick()
        scrollToBottom()
      }
    } else {
      console.error('Fetch history failed with status:', res.status)
    }
  } catch (e) {
    console.error('Failed to fetch history', e)
  }
}

const loadMore = async () => {
  // 修复：如果消息为空（初始加载失败），不要增加偏移量
  if (messages.value.length === 0) {
    offset.value = 0
  } else {
    offset.value += HISTORY_LIMIT
  }
  await fetchHistory(true)
}

let groupPollingInterval = null

const startGroupPolling = () => {
  if (props.mode !== 'group' || !props.targetId) return
  stopGroupPolling()

  groupPollingInterval = setInterval(async () => {
    if (document.hidden) return // Optimization
    try {
      // 使用 fetchHistory with append=true 获取新消息？
      // Actually fetchHistory implementation for group chat might need adjustment or we use a separate endpoint.
      // 目前，让我们重用 fetchHistory，但我们需要小心处理重复。
      // 或者更好的是，只获取最新消息。
      // Let's stick to simple polling for now.
      await fetchHistory(true)
    } catch (e) {
      console.error('Group polling failed', e)
    }
  }, 3000)
}

const stopGroupPolling = () => {
  if (groupPollingInterval) {
    clearInterval(groupPollingInterval)
    groupPollingInterval = null
  }
}

let unlistenSync = null
let unlistenDelete = null
let visionCheckInterval = null

onMounted(async () => {
  gatewayClient.on('action:voice_update', handleVoiceUpdate)
  gatewayClient.on('action:text_stream', handleTextStream)
  // [修复] 监听 text_response
  gatewayClient.on('action:text_response', handleTextResponse)
  gatewayClient.on('action:transcription', handleTranscription)
  gatewayClient.on('action:command_running', handleCommandRunning)
  gatewayClient.on('action:command_finished', handleCommandFinished)
  gatewayClient.on('action:mode_update', handleModeUpdate)

  fetchHistory()
  startGroupPolling()
  checkVisionCapability()
  // 轮询视觉能力更改（例如模型切换）
  visionCheckInterval = setInterval(checkVisionCapability, 5000)

  // 设置用于聊天同步的 Tauri 事件监听器
  try {
    // 监听日志删除
    unlistenDelete = await listen('log-deleted', (event) => {
      const deletedLogId = event.payload
      if (deletedLogId) {
        messages.value = messages.value.filter((msg) => msg.id !== deletedLogId)
      }
    })

    // 监听来自后端/PetView的同步消息
    unlistenSync = await listen('sync-chat-to-ide', (event) => {
      const { role, content, timestamp } = event.payload

      // 用于比较的规范化内容助手（去除 NIT 数据和空格）
      const normalize = (str) => {
        return (str || '').replace(/(\n|^)\s*data:\s*\{"triggers":[\s\S]*?(\n|$)/g, '').trim()
      }

      const incomingNorm = normalize(content)

      // 避免重复添加 (Enhanced Dedup Logic)
      // 1. 检查末尾的精确匹配（规范化）
      const lastMsg = messages.value[messages.value.length - 1]
      if (lastMsg && lastMsg.role === role) {
        const lastNorm = normalize(lastMsg.content)
        // 如果内容相同或传入内容是子集（例如流式传输伪影），则跳过
        if (
          lastNorm === incomingNorm ||
          (incomingNorm.length > 0 && lastNorm.includes(incomingNorm))
        ) {
          return
        }
      }

      // 2. 检查乐观发送的用户消息（无 ID，相同内容，最近）
      if (role === 'user') {
        // 向后查找待定用户消息
        for (let i = messages.value.length - 1; i >= 0; i--) {
          const m = messages.value[i]
          const mNorm = normalize(m.content)

          // 如果我们找到没有 ID（乐观）且内容相同的用户消息
          if (m.role === 'user' && !m.id && mNorm === incomingNorm) {
            return
          }
          // 如果我们找到带有 ID 的用户消息，我们可能已经通过了乐观区域
          if (m.role === 'user' && m.id) break
        }
      }

      messages.value.push({ role, content, timestamp: timestamp || new Date().toISOString() })
      scrollToBottom()
    })
  } catch (e) {
    console.warn('Failed to setup Tauri listener:', e)
  }
})

watch(
  () => props.workMode,
  () => {
    offset.value = 0
    hasMore.value = true
    fetchHistory()
  }
)

watch(
  () => props.mode,
  () => {
    stopGroupPolling()
    startGroupPolling()
  }
)

onUnmounted(() => {
  gatewayClient.off('action:voice_update', handleVoiceUpdate)
  gatewayClient.off('action:text_stream', handleTextStream)
  gatewayClient.off('action:text_response', handleTextResponse)
  gatewayClient.off('action:transcription', handleTranscription)
  gatewayClient.off('action:command_running', handleCommandRunning)
  gatewayClient.off('action:command_finished', handleCommandFinished)
  gatewayClient.off('action:mode_update', handleModeUpdate)

  if (visionCheckInterval) clearInterval(visionCheckInterval)
  stopGroupPolling()
  if (unlistenSync) unlistenSync()
  if (unlistenDelete) unlistenDelete()
})

// --- 聊天逻辑 ---
const handleEnter = (e) => {
  if (e.shiftKey) return
  sendMessage()
}

const sendMessage = async () => {
  if ((!input.value.trim() && pendingImages.value.length === 0) || isSending.value) return

  const content = input.value

  // 捕获图像以进行本地显示
  const currentImages = pendingImages.value.map((p) => p.url)

  const userMsg = {
    role: 'user',
    content,
    timestamp: new Date().toISOString(),
    images: currentImages
  }
  messages.value.push(userMsg)

  // 如果不在工作模式，则为 PetView 发送同步事件
  if (!props.workMode) {
    emit('sync-chat-to-pet', { role: 'user', content, timestamp: new Date().toISOString() })
  }

  // Construct Payload Content (Structured if images exist)
  let payloadContent
  if (currentImages.length > 0) {
    payloadContent = []
    if (content) payloadContent.push({ type: 'text', text: content })
    currentImages.forEach((url) => {
      payloadContent.push({ type: 'image_url', image_url: { url } })
    })
  } else {
    payloadContent = content
  }

  input.value = ''
  pendingImages.value = []
  isSending.value = true

  await nextTick()
  scrollToBottom()

  // 预添加助手消息以获得即时反馈
  const assistantMsg = { role: 'assistant', content: '', timestamp: new Date().toISOString() }
  messages.value.push(assistantMsg)
  await nextTick()
  scrollToBottom()

  try {
    if (props.mode === 'group') {
      const res = await fetch(`${API_BASE}/api/groupchat/rooms/${props.targetId}/messages`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          sender_id: 'user',
          content: content,
          role: 'user'
        })
      })
      if (res.ok) {
        assistantMsg.content = '' // 清除占位符
        messages.value.pop() // 移除占位符助手消息
      } else {
        assistantMsg.content = 'Failed to send message.'
      }
      return
    }

    // 构造 API 消息列表
    const historyMsgs = messages.value
      .slice(0, -1)
      .filter((m) => m.role === 'user' || m.role === 'assistant')
      .slice(-10)
    const apiMessages = historyMsgs.map((m) => {
      if (m === userMsg) {
        return { role: 'user', content: payloadContent }
      }
      return { role: m.role, content: m.content } // 历史记录总是文本
    })

    const res = await fetch(`${API_BASE}/api/ide/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        messages: apiMessages,
        source: props.workMode ? 'ide' : 'desktop',
        session_id: props.workMode ? 'current_work_session' : props.targetId || 'default'
      })
    })

    if (!res.body) throw new Error('No response body')

    const reader = res.body.getReader()
    const decoder = new TextDecoder()

    // eslint-disable-next-line no-constant-condition
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      const chunk = decoder.decode(value)
      assistantMsg.content += chunk
      scrollToBottom()
    }
  } catch (e) {
    assistantMsg.content = `Error: ${e.message}`
    // 出错时强制重置思维链
    if (activeThoughtChain.value) {
      activeThoughtChain.value.isThinking = false
      activeThoughtChain.value = null
    }
  } finally {
    isSending.value = false
    scrollToBottom()
  }
}

const scrollToBottom = () => {
  if (msgContainer.value) {
    msgContainer.value.scrollTop = msgContainer.value.scrollHeight
  }
}
</script>

<style scoped>
@keyframes float {
  0%,
  100% {
    transform: translateY(0px) scale(1);
  }
  50% {
    transform: translateY(-6px) scale(1.01);
  }
}

.animate-float {
  animation: float 6s ease-in-out infinite;
}

/* 添加随机延迟以获得自然感 */
.animate-float:nth-child(odd) {
  animation-delay: 0s;
}
.animate-float:nth-child(even) {
  animation-delay: 2s;
}
.animate-float:nth-child(3n) {
  animation-delay: 4s;
}

/* 自定义滚动条 */
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

.animate-fade-in-up {
  animation: fadeInUp 0.4s ease-out forwards;
}

@keyframes fadeInUp {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
</style>
