<template>
  <div class="voice-panel">
    <!-- 顶部头部区域 -->
    <div class="panel-header">
      <div class="header-content">
        <h2 class="title">语音功能配置</h2>
        <p class="subtitle">管理您的语音识别 (STT) 与语音合成 (TTS) 引擎</p>
      </div>
      <el-button type="primary" class="add-btn" size="large" :icon="Plus" @click="openEditor(null)">
        添加新配置
      </el-button>
    </div>

    <!-- 主要内容区域 -->
    <div class="panel-body">
      <el-tabs v-model="activeTab" class="custom-tabs">
        <!-- STT 面板 -->
        <el-tab-pane name="stt">
          <template #label>
            <div class="tab-label">
              <el-icon><Microphone /></el-icon>
              <span>语音识别 (STT)</span>
            </div>
          </template>

          <div class="config-container">
            <div v-if="sttConfigs.length === 0" class="empty-state">
              <el-empty description="暂无语音识别配置">
                <el-button type="primary" @click="openEditor(null)">立即添加</el-button>
              </el-empty>
            </div>
            <el-row v-else :gutter="20">
              <el-col
                v-for="config in sttConfigs"
                :key="config.id"
                :xs="24"
                :sm="12"
                :md="8"
                :lg="6"
              >
                <el-card
                  class="config-card glass-card"
                  :class="{ active: config.is_active }"
                  shadow="hover"
                >
                  <div class="card-header-wrapper">
                    <div class="card-icon stt-icon">
                      <el-icon><Microphone /></el-icon>
                    </div>
                    <div v-if="config.is_active" class="active-badge">
                      <el-icon><Check /></el-icon> 使用中
                    </div>
                  </div>

                  <div class="card-content">
                    <h3 class="config-name" :title="config.name">{{ config.name }}</h3>
                    <div class="config-meta">
                      <el-tag size="small" effect="dark" type="info" class="meta-tag">
                        {{ config.provider }}
                      </el-tag>
                      <el-tag
                        v-if="config.model"
                        size="small"
                        effect="plain"
                        type="success"
                        class="meta-tag"
                      >
                        {{ config.model }}
                      </el-tag>
                    </div>
                  </div>

                  <div class="card-footer">
                    <el-button
                      v-if="!config.is_active"
                      class="action-btn activate-btn"
                      type="primary"
                      plain
                      size="small"
                      @click="activateConfig(config)"
                    >
                      启用
                    </el-button>
                    <div class="footer-tools">
                      <el-tooltip content="编辑配置" placement="top">
                        <el-button
                          class="tool-btn"
                          size="small"
                          :icon="Edit"
                          circle
                          @click="openEditor(config)"
                        />
                      </el-tooltip>
                      <el-tooltip content="删除配置" placement="top">
                        <el-button
                          class="tool-btn delete-btn"
                          type="danger"
                          plain
                          size="small"
                          :icon="Delete"
                          circle
                          :disabled="config.is_active"
                          @click="deleteConfig(config)"
                        />
                      </el-tooltip>
                    </div>
                  </div>
                </el-card>
              </el-col>
            </el-row>
          </div>
        </el-tab-pane>

        <!-- TTS 面板 -->
        <el-tab-pane name="tts">
          <template #label>
            <div class="tab-label">
              <el-icon><Headset /></el-icon>
              <span>语音合成 (TTS)</span>
            </div>
          </template>

          <div class="config-container">
            <!-- TTS 全局开关 Banner -->
            <div class="tts-banner glass-banner" :class="{ disabled: !ttsEnabled }">
              <div class="banner-left">
                <div class="banner-icon-wrapper">
                  <el-icon class="banner-icon">
                    <component :is="ttsEnabled ? 'Headset' : 'Mute'" />
                  </el-icon>
                </div>
                <div class="banner-info">
                  <div class="banner-title">全局语音合成开关</div>
                  <div class="banner-desc">
                    {{
                      ttsEnabled ? '当前已开启，助手将通过语音回复您' : '当前已关闭，助手将保持静默'
                    }}
                  </div>
                </div>
              </div>
              <div class="banner-right">
                <el-switch
                  v-model="ttsEnabled"
                  size="large"
                  inline-prompt
                  active-text="ON"
                  inactive-text="OFF"
                  style="--el-switch-on-color: #13ce66; --el-switch-off-color: #ff4949"
                  @change="toggleTTSMode"
                />
              </div>
            </div>

            <div v-if="ttsConfigs.length === 0" class="empty-state">
              <el-empty description="暂无语音合成配置">
                <el-button type="primary" @click="openEditor(null)">立即添加</el-button>
              </el-empty>
            </div>
            <el-row v-else :gutter="20">
              <el-col
                v-for="config in ttsConfigs"
                :key="config.id"
                :xs="24"
                :sm="12"
                :md="8"
                :lg="6"
              >
                <el-card
                  class="config-card glass-card"
                  :class="{ active: config.is_active }"
                  shadow="hover"
                >
                  <div class="card-header-wrapper">
                    <div class="card-icon tts-icon">
                      <el-icon><Headset /></el-icon>
                    </div>
                    <div v-if="config.is_active" class="active-badge">
                      <el-icon><Check /></el-icon> 使用中
                    </div>
                  </div>

                  <div class="card-content">
                    <h3 class="config-name" :title="config.name">{{ config.name }}</h3>
                    <div class="config-meta">
                      <el-tag size="small" effect="dark" type="info" class="meta-tag">
                        {{ config.provider }}
                      </el-tag>
                      <el-tag
                        v-if="config.model"
                        size="small"
                        effect="plain"
                        type="warning"
                        class="meta-tag"
                      >
                        {{ config.model }}
                      </el-tag>
                    </div>
                  </div>

                  <div class="card-footer">
                    <el-button
                      v-if="!config.is_active"
                      class="action-btn activate-btn"
                      type="primary"
                      plain
                      size="small"
                      @click="activateConfig(config)"
                    >
                      启用
                    </el-button>
                    <div class="footer-tools">
                      <el-tooltip content="编辑配置" placement="top">
                        <el-button
                          class="tool-btn"
                          size="small"
                          :icon="Edit"
                          circle
                          @click="openEditor(config)"
                        />
                      </el-tooltip>
                      <el-tooltip content="删除配置" placement="top">
                        <el-button
                          class="tool-btn delete-btn"
                          type="danger"
                          plain
                          size="small"
                          :icon="Delete"
                          circle
                          :disabled="config.is_active"
                          @click="deleteConfig(config)"
                        />
                      </el-tooltip>
                    </div>
                  </div>
                </el-card>
              </el-col>
            </el-row>
          </div>
        </el-tab-pane>
      </el-tabs>
    </div>

    <!-- 编辑器对话框 -->
    <el-dialog
      v-model="showEditor"
      :title="editingConfig.id ? '编辑配置' : '添加新配置'"
      width="640px"
      class="custom-dialog glass-dialog"
      align-center
      destroy-on-close
    >
      <el-form label-position="top" class="custom-form">
        <div class="form-row">
          <el-form-item label="配置类型" class="flex-1">
            <el-radio-group
              v-model="editingConfig.type"
              :disabled="!!editingConfig.id"
              class="custom-radio-group"
            >
              <el-radio-button value="stt">
                <el-icon><Microphone /></el-icon> 语音识别 (STT)
              </el-radio-button>
              <el-radio-button value="tts">
                <el-icon><Headset /></el-icon> 语音合成 (TTS)
              </el-radio-button>
            </el-radio-group>
          </el-form-item>
        </div>

        <el-form-item label="配置名称">
          <el-input
            v-model="editingConfig.name"
            placeholder="给这个配置起个名字，例如：我的本地模型"
            size="large"
          >
            <template #prefix>
              <el-icon><EditPen /></el-icon>
            </template>
          </el-input>
        </el-form-item>

        <el-form-item label="服务提供商">
          <el-select v-model="editingConfig.provider" size="large" class="w-full">
            <template v-if="editingConfig.type === 'stt'">
              <el-option label="Local Whisper (本地)" value="local_whisper" />
              <el-option label="OpenAI Compatible (云端)" value="openai_compatible" />
            </template>
            <template v-else>
              <el-option label="Edge TTS (免费云端)" value="edge_tts" />
              <el-option label="OpenAI Compatible (云端)" value="openai_compatible" />
            </template>
          </el-select>
        </el-form-item>

        <transition name="fade-slide">
          <div v-if="editingConfig.provider === 'openai_compatible'" class="form-section">
            <h4 class="section-label">API 设置</h4>
            <el-form-item label="Base URL">
              <el-input v-model="editingConfig.api_base" placeholder="https://api.openai.com/v1">
                <template #prefix
                  ><el-icon><Link /></el-icon
                ></template>
              </el-input>
            </el-form-item>
            <el-form-item label="API Key">
              <el-input
                v-model="editingConfig.api_key"
                type="password"
                show-password
                placeholder="sk-..."
              >
                <template #prefix
                  ><el-icon><Key /></el-icon
                ></template>
              </el-input>
            </el-form-item>
            <el-form-item label="Model ID">
              <div class="flex gap-2 w-full" style="display: flex; gap: 8px">
                <el-input
                  v-model="editingConfig.model"
                  placeholder="例如: whisper-1"
                  class="flex-1"
                />
                <el-button :loading="isFetchingRemote" :icon="Refresh" @click="fetchRemoteModels">
                  获取列表
                </el-button>
              </div>
              <el-select
                v-if="remoteModels.length > 0"
                v-model="editingConfig.model"
                placeholder="选择检测到的模型"
                class="w-full mt-2"
                style="width: 100%; margin-top: 8px"
              >
                <el-option v-for="m in remoteModels" :key="m" :label="m" :value="m" />
              </el-select>
            </el-form-item>
          </div>
        </transition>

        <div class="form-section">
          <h4 class="section-label">高级参数 (JSON)</h4>
          <el-input
            v-model="editingConfig.config_json"
            type="textarea"
            :rows="4"
            class="code-font"
            placeholder="{}"
          />
          <div class="form-tip">
            <el-icon><InfoFilled /></el-icon>
            <span v-if="editingConfig.type === 'stt'"
              >STT 示例: {"device": "cpu", "compute_type": "int8"}</span
            >
            <span v-else>TTS 示例: {"voice": "zh-CN-XiaoyiNeural", "rate": "+15%"}</span>
          </div>
        </div>
      </el-form>
      <template #footer>
        <div class="dialog-footer">
          <el-button size="large" @click="showEditor = false">取消</el-button>
          <el-button type="primary" :loading="isSaving" size="large" @click="saveConfig"
            >保存配置</el-button
          >
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import {
  Plus,
  Edit,
  Delete,
  Check,
  Microphone,
  Headset,
  Mute,
  EditPen,
  Link,
  Key,
  Refresh,
  InfoFilled
} from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'

const API_BASE = 'http://localhost:9120/api'
const activeTab = ref('stt')
const configs = ref([])
const showEditor = ref(false)
const isSaving = ref(false)
const editingConfig = ref({})
const remoteModels = ref([])
const isFetchingRemote = ref(false)
const ttsEnabled = ref(true)

const sttConfigs = computed(() => configs.value.filter((c) => c.type === 'stt'))
const ttsConfigs = computed(() => configs.value.filter((c) => c.type === 'tts'))

const fetchTTSMode = async () => {
  try {
    const res = await fetch(`${API_BASE}/config/tts`)
    if (res.ok) {
      const data = await res.json()
      ttsEnabled.value = data.enabled
    }
  } catch (e) {
    console.error('获取 TTS 模式错误:', e)
  }
}

const toggleTTSMode = async (val) => {
  try {
    await fetch(`${API_BASE}/config/tts`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ enabled: val })
    })
    ElMessage.success(val ? '语音合成已开启' : '语音合成已关闭')
  } catch {
    ElMessage.error('设置失败')
    ttsEnabled.value = !val // 恢复原状
  }
}

const fetchConfigs = async () => {
  try {
    const res = await fetch(`${API_BASE}/voice-configs`)
    if (res.ok) {
      configs.value = await res.json()
    }
  } catch (e) {
    console.error('获取配置错误:', e)
  }
}

const fetchRemoteModels = async () => {
  try {
    if (!editingConfig.value.api_base) {
      ElMessage.warning('请先填写 Base URL')
      return
    }
    isFetchingRemote.value = true
    const res = await fetch(`${API_BASE}/models/remote`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        api_key: editingConfig.value.api_key || '',
        api_base: editingConfig.value.api_base
      })
    })
    const data = await res.json()
    if (data.models && data.models.length > 0) {
      remoteModels.value = data.models
      ElMessage.success(`成功获取 ${data.models.length} 个模型`)
    } else {
      ElMessage.warning('未能获取到模型列表，请检查配置')
    }
  } catch (e) {
    ElMessage.error('获取模型失败: ' + e.message)
  } finally {
    isFetchingRemote.value = false
  }
}

const openEditor = (config) => {
  remoteModels.value = []
  if (config) {
    editingConfig.value = JSON.parse(JSON.stringify(config))
  } else {
    editingConfig.value = {
      type: activeTab.value,
      name: '',
      provider: activeTab.value === 'stt' ? 'local_whisper' : 'edge_tts',
      config_json: '{}',
      is_active: false
    }
  }
  showEditor.value = true
}

const saveConfig = async () => {
  try {
    isSaving.value = true
    // 验证 JSON
    try {
      JSON.parse(editingConfig.value.config_json || '{}')
    } catch {
      ElMessage.error('Config JSON 格式错误')
      return
    }

    const method = editingConfig.value.id ? 'PUT' : 'POST'
    const url = editingConfig.value.id
      ? `${API_BASE}/voice-configs/${editingConfig.value.id}`
      : `${API_BASE}/voice-configs`

    const res = await fetch(url, {
      method,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(editingConfig.value)
    })

    if (!res.ok) {
      const err = await res.json()
      throw new Error(err.detail || '保存失败')
    }

    await fetchConfigs()
    showEditor.value = false
    ElMessage.success('配置已保存')
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    isSaving.value = false
  }
}

const activateConfig = async (config) => {
  try {
    config.is_active = true
    const res = await fetch(`${API_BASE}/voice-configs/${config.id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(config)
    })
    if (!res.ok) throw new Error('切换失败')
    await fetchConfigs()
    ElMessage.success('已切换当前配置')
  } catch (e) {
    ElMessage.error(e.message)
  }
}

const deleteConfig = async (config) => {
  try {
    await ElMessageBox.confirm('确定要删除此语音配置吗? 此操作无法撤销。', '删除确认', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning',
      icon: InfoFilled
    })
    const res = await fetch(`${API_BASE}/voice-configs/${config.id}`, { method: 'DELETE' })
    if (!res.ok) throw new Error('删除失败')
    await fetchConfigs()
    ElMessage.success('配置已删除')
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e.message)
  }
}

onMounted(() => {
  fetchConfigs()
  fetchTTSMode()
})
</script>

<style scoped>
.voice-panel {
  height: 100%;
  display: flex;
  flex-direction: column;
  padding: 0 20px 20px;
  max-width: 1400px;
  margin: 0 auto;
}

/* 头部样式 */
.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  padding-bottom: 15px;
  border-bottom: 1px solid var(--el-border-color-light);
}

.title {
  font-size: 24px;
  font-weight: 700;
  color: var(--el-text-color-primary);
  margin: 0 0 6px 0;
}

.subtitle {
  font-size: 13px;
  color: var(--el-text-color-secondary);
  margin: 0;
}

.add-btn {
  box-shadow: 0 4px 12px rgba(64, 158, 255, 0.3);
  transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1);
}
.add-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 16px rgba(64, 158, 255, 0.4);
}
.add-btn:active {
  transform: translateY(0);
}

/* Tabs 样式 */
.custom-tabs :deep(.el-tabs__nav-wrap::after) {
  height: 1px;
  background-color: var(--el-border-color-lighter);
}
.custom-tabs :deep(.el-tabs__item) {
  font-size: 15px;
  height: 48px;
  color: var(--el-text-color-regular);
  transition: all 0.3s;
}
.custom-tabs :deep(.el-tabs__item.is-active) {
  color: var(--el-color-primary);
  font-weight: 600;
}
.custom-tabs :deep(.el-tabs__active-bar) {
  background-color: var(--el-color-primary);
  height: 3px;
  border-radius: 3px;
}
.tab-label {
  display: flex;
  align-items: center;
  gap: 8px;
}

/* 内容区域 */
.panel-body {
  flex: 1;
  overflow-y: auto;
  padding-right: 8px;
}

/* 滚动条美化 */
.panel-body::-webkit-scrollbar {
  width: 6px;
}
.panel-body::-webkit-scrollbar-thumb {
  background: var(--el-border-color-darker);
  border-radius: 3px;
}
.panel-body::-webkit-scrollbar-track {
  background: transparent;
}

/* 配置容器 */
.config-container {
  padding-top: 10px;
}

/* Glass Card 效果 - 适配亮色背景 */
.glass-card {
  background: rgba(255, 255, 255, 0.8);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 16px;
  color: var(--el-text-color-primary);
  transition: all 0.4s cubic-bezier(0.25, 0.8, 0.25, 1);
  position: relative;
  overflow: hidden;
  margin-bottom: 20px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
}

.glass-card:hover {
  transform: translateY(-5px);
  background: #fff;
  border-color: var(--el-color-primary-light-7);
  box-shadow: 0 12px 24px rgba(0, 0, 0, 0.08);
}

.glass-card.active {
  border: 1px solid var(--el-color-success-light-5);
  background: linear-gradient(135deg, var(--el-color-success-light-9), #fff);
  box-shadow: 0 4px 12px rgba(103, 194, 58, 0.15);
}

.glass-card :deep(.el-card__body) {
  padding: 20px;
  height: 100%;
  display: flex;
  flex-direction: column;
}

/* Card Header */
.card-header-wrapper {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 16px;
}

.card-icon {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
  color: white;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.stt-icon {
  background: linear-gradient(135deg, #a0cfff, #409eff);
}
.tts-icon {
  background: linear-gradient(135deg, #b3e19d, #67c23a);
}

.active-badge {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: var(--el-color-success);
  background: var(--el-color-success-light-9);
  padding: 4px 8px;
  border-radius: 12px;
  border: 1px solid var(--el-color-success-light-5);
}

/* Card Content */
.card-content {
  flex: 1;
  margin-bottom: 20px;
}

.config-name {
  font-size: 18px;
  font-weight: 600;
  margin: 0 0 10px 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  color: var(--el-text-color-primary);
}

.config-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.meta-tag {
  /* 使用 Element Plus 默认样式，不再强制覆盖 */
}

/* Card Footer */
.card-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: auto;
  padding-top: 15px;
  border-top: 1px solid var(--el-border-color-lighter);
}

.activate-btn {
  /* 使用默认 Primary Plain 样式 */
}

.footer-tools {
  display: flex;
  gap: 8px;
  margin-left: auto;
}

.tool-btn {
  background: transparent;
  border: 1px solid var(--el-border-color-lighter);
  color: var(--el-text-color-regular);
  transition: all 0.2s;
}
.tool-btn:hover {
  background: var(--el-fill-color-light);
  color: var(--el-color-primary);
  border-color: var(--el-color-primary-light-7);
  transform: scale(1.05);
}
.delete-btn:hover {
  background: var(--el-color-danger-light-9);
  color: var(--el-color-danger);
  border-color: var(--el-color-danger-light-7);
}

/* TTS Banner */
.glass-banner {
  background: linear-gradient(135deg, #ecf5ff, #fff);
  backdrop-filter: blur(12px);
  border: 1px solid #d9ecff;
  border-radius: 16px;
  padding: 24px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
  box-shadow: 0 4px 16px rgba(64, 158, 255, 0.1);
  transition: all 0.3s;
}

.glass-banner.disabled {
  background: #f4f4f5;
  border-color: #e9e9eb;
  opacity: 0.8;
  box-shadow: none;
}

.banner-left {
  display: flex;
  align-items: center;
  gap: 20px;
}

.banner-icon-wrapper {
  width: 56px;
  height: 56px;
  border-radius: 50%;
  background: linear-gradient(135deg, #409eff, #36d1dc);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 4px 12px rgba(64, 158, 255, 0.3);
}

.glass-banner.disabled .banner-icon-wrapper {
  background: #909399;
  box-shadow: none;
}

.banner-icon {
  font-size: 28px;
  color: white;
}

.banner-info {
  display: flex;
  flex-direction: column;
}

.banner-title {
  font-size: 18px;
  font-weight: 600;
  color: var(--el-text-color-primary);
  margin-bottom: 4px;
}

.banner-desc {
  font-size: 13px;
  color: var(--el-text-color-secondary);
}

/* Dialog Styles */
.custom-form {
  margin-top: 10px;
}
.form-section {
  background: var(--el-fill-color-lighter);
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 16px;
  border: 1px solid var(--el-border-color-lighter);
}
.section-label {
  margin: 0 0 12px 0;
  font-size: 14px;
  font-weight: 600;
  color: var(--el-text-color-primary);
  display: flex;
  align-items: center;
}
.form-tip {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 8px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.code-font :deep(.el-textarea__inner) {
  font-family: 'JetBrains Mono', Consolas, monospace;
  font-size: 12px;
  background-color: var(--el-fill-color-light);
}

/* Animations */
.fade-slide-enter-active,
.fade-slide-leave-active {
  transition: all 0.3s ease;
}
.fade-slide-enter-from,
.fade-slide-leave-to {
  opacity: 0;
  transform: translateY(-10px);
}
</style>
