<script setup lang="ts">
import { ref, computed } from 'vue'
import { invoke } from '@tauri-apps/api/core'
import { open, save } from '@tauri-apps/plugin-dialog'

interface EncryptResult {
  success: boolean
  message: string
  output_size: number | null
  fileCount: number | null
}

const inputFolder = ref<string>('')
const outputPath = ref<string>('')
const isProcessing = ref(false)
const resultMessage = ref('')
const isSuccess = ref<boolean | null>(null)
const isDragging = ref(false)

const canProcess = computed(() => {
  return inputFolder.value && !isProcessing.value
})

async function selectInputFolder() {
  const selected = await open({
    directory: true,
    multiple: false,
    title: '选择模型文件夹'
  })
  if (selected && typeof selected === 'string') {
    inputFolder.value = selected
    if (!outputPath.value) {
      const pathParts = selected.split(/[/\\]/)
      const folderName = pathParts.pop()
      const parentPath = pathParts.join('/')
      if (folderName) {
        outputPath.value = `${parentPath}/${folderName}.pero`
      }
    }
  }
}

async function selectOutputFile() {
  const folderName = inputFolder.value.split(/[/\\]/).pop() || 'model'
  const selected = await save({
    defaultPath: outputPath.value || `${folderName}.pero`,
    filters: [{ name: 'Pero 加密容器', extensions: ['pero'] }],
    title: '选择输出位置'
  })
  if (selected && typeof selected === 'string') {
    outputPath.value = selected
  }
}

async function handleDrop(event: DragEvent) {
  isDragging.value = false
  event.preventDefault()

  const items = event.dataTransfer?.items
  if (items && items.length > 0) {
    const item = items[0] as any
    if (item && item.kind === 'file') {
      const entry = item.webkitGetAsEntry?.() as any
      if (entry && entry.isDirectory) {
        const folderPath = (item as any).getAsFileSystemHandle?.()?.path
        if (folderPath) {
          inputFolder.value = folderPath
          const pathParts = folderPath.split(/[/\\]/)
          const folderName = pathParts.pop()
          const parentPath = pathParts.join('/')
          if (folderName) {
            outputPath.value = `${parentPath}/${folderName}.pero`
          }
        }
      }
    }
  }

  const files = event.dataTransfer?.files
  if (files && files.length > 0) {
    const file = files[0] as any
    if (file && file.path) {
      const filePath = file.path as string
      inputFolder.value = filePath
      const pathParts = filePath.split(/[/\\]/)
      const folderName = pathParts.pop()
      const parentPath = pathParts.join('/')
      if (folderName) {
        outputPath.value = `${parentPath}/${folderName}.pero`
      }
    }
  }
}

function handleDragOver(event: DragEvent) {
  event.preventDefault()
  isDragging.value = true
}

function handleDragLeave() {
  isDragging.value = false
}

async function processFolder() {
  if (!canProcess.value) return

  isProcessing.value = true
  resultMessage.value = ''
  isSuccess.value = null

  try {
    const result = await invoke<EncryptResult>('encrypt_folder', {
      inputFolder: inputFolder.value,
      outputPath: outputPath.value
    })
    resultMessage.value = result.message
    isSuccess.value = result.success
  } catch (error) {
    resultMessage.value = `错误: ${error}`
    isSuccess.value = false
  } finally {
    isProcessing.value = false
  }
}

function resetForm() {
  inputFolder.value = ''
  outputPath.value = ''
  resultMessage.value = ''
  isSuccess.value = null
}
</script>

<template>
  <div class="container">
    <header class="header">
      <h1>🔐 Pero 模型打包加密</h1>
      <p class="subtitle">将整个模型文件夹打包加密为单一 .pero 文件</p>
    </header>

    <main class="main-content">
      <div
        class="drop-zone"
        :class="{ 'drag-over': isDragging }"
        @drop="handleDrop"
        @dragover="handleDragOver"
        @dragleave="handleDragLeave"
        @click="selectInputFolder"
      >
        <div class="drop-icon">
          <span v-if="!isDragging">📁</span>
          <span v-else class="bounce">🐾</span>
        </div>
        <p class="drop-text">
          {{ inputFolder ? inputFolder.split(/[/\\]/).pop() : '拖拽模型文件夹到这里，或点击选择' }}
        </p>
        <p v-if="!inputFolder" class="drop-hint">将包含模型、材质、动画等文件的整个文件夹打包</p>
        <p v-else class="path-display" title="点击更换文件夹">{{ inputFolder }}</p>
      </div>

      <div class="controls-area">
        <div class="path-row">
          <div class="input-group">
            <div class="label-row">
              <label>输出文件</label>
              <button v-if="inputFolder" class="btn-clear" @click.stop="resetForm">重置</button>
            </div>
            <div class="input-wrapper">
              <input
                v-model="outputPath"
                type="text"
                placeholder="点击选择输出位置..."
                readonly
                @click="selectOutputFile"
              />
              <button class="btn-browse" @click="selectOutputFile">浏览</button>
            </div>
          </div>
        </div>

        <button class="btn-process" :disabled="!canProcess" @click="processFolder">
          <span v-if="!isProcessing">🚀 开始打包加密</span>
          <span v-else class="processing">⏳ 处理中...</span>
        </button>

        <div
          v-if="resultMessage"
          class="result-area"
          :class="{ success: isSuccess, error: !isSuccess }"
        >
          <p>{{ resultMessage }}</p>
        </div>
      </div>
    </main>

    <footer class="footer">
      <p>🐾 Pero 模型加密工具 · 安全打包您的创作</p>
    </footer>
  </div>
</template>

<style scoped>
* {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

.container {
  min-height: 100vh;
  background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
  color: #e8e8e8;
  font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  position: relative;
}

.container::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background:
    radial-gradient(circle at 20% 80%, rgba(120, 200, 255, 0.08) 0%, transparent 50%),
    radial-gradient(circle at 80% 20%, rgba(255, 150, 200, 0.08) 0%, transparent 50%),
    radial-gradient(circle at 50% 50%, rgba(100, 255, 200, 0.05) 0%, transparent 60%);
  pointer-events: none;
}

.header {
  text-align: center;
  padding: 28px 20px 20px;
  position: relative;
  z-index: 1;
}

.header h1 {
  font-size: 1.6rem;
  font-weight: 700;
  background: linear-gradient(135deg, #fff 0%, #a8d8ff 50%, #ffb6c1 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  margin-bottom: 8px;
  letter-spacing: 1px;
}

.subtitle {
  color: rgba(255, 255, 255, 0.6);
  font-size: 0.85rem;
}

.main-content {
  flex: 1;
  padding: 0 24px 24px;
  display: flex;
  flex-direction: column;
  gap: 20px;
  position: relative;
  z-index: 1;
}

.drop-zone {
  background: rgba(255, 255, 255, 0.03);
  border: 2px dashed rgba(255, 255, 255, 0.15);
  border-radius: 16px;
  padding: 36px 24px;
  text-align: center;
  cursor: pointer;
  transition: all 0.3s ease;
  backdrop-filter: blur(10px);
  position: relative;
  overflow: hidden;
}

.drop-zone::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: linear-gradient(135deg, rgba(255, 255, 255, 0.02) 0%, transparent 100%);
  pointer-events: none;
}

.drop-zone:hover {
  border-color: rgba(168, 216, 255, 0.4);
  background: rgba(255, 255, 255, 0.06);
  transform: translateY(-2px);
  box-shadow: 0 8px 32px rgba(168, 216, 255, 0.1);
}

.drop-zone.drag-over {
  border-color: rgba(255, 182, 193, 0.6);
  background: rgba(255, 182, 193, 0.1);
  transform: scale(1.02);
}

.drop-icon {
  font-size: 2.8rem;
  margin-bottom: 12px;
  filter: drop-shadow(0 2px 8px rgba(255, 255, 255, 0.2));
}

.bounce {
  display: inline-block;
  animation: bounce 0.6s ease infinite;
}

@keyframes bounce {
  0%,
  100% {
    transform: translateY(0);
  }
  50% {
    transform: translateY(-8px);
  }
}

.drop-text {
  font-size: 1rem;
  color: rgba(255, 255, 255, 0.9);
  margin-bottom: 6px;
}

.drop-hint {
  font-size: 0.8rem;
  color: rgba(255, 255, 255, 0.4);
}

.path-display {
  font-size: 0.75rem;
  color: rgba(168, 216, 255, 0.6);
  word-break: break-all;
  margin-top: 8px;
  padding: 6px 10px;
  background: rgba(0, 0, 0, 0.2);
  border-radius: 6px;
}

.controls-area {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.path-row {
  background: rgba(255, 255, 255, 0.03);
  border-radius: 12px;
  padding: 16px;
  backdrop-filter: blur(10px);
}

.label-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.label-row label {
  font-size: 0.85rem;
  color: rgba(255, 255, 255, 0.7);
  font-weight: 500;
}

.btn-clear {
  background: rgba(255, 100, 100, 0.2);
  border: none;
  color: rgba(255, 150, 150, 0.9);
  padding: 4px 10px;
  border-radius: 6px;
  font-size: 0.75rem;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-clear:hover {
  background: rgba(255, 100, 100, 0.3);
  color: #fff;
}

.input-wrapper {
  display: flex;
  gap: 10px;
}

.input-wrapper input {
  flex: 1;
  background: rgba(0, 0, 0, 0.3);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 8px;
  padding: 10px 14px;
  color: #e8e8e8;
  font-size: 0.85rem;
  cursor: pointer;
  transition: all 0.2s;
}

.input-wrapper input:hover {
  border-color: rgba(168, 216, 255, 0.3);
}

.input-wrapper input:focus {
  outline: none;
  border-color: rgba(168, 216, 255, 0.5);
}

.btn-browse {
  background: rgba(168, 216, 255, 0.15);
  border: 1px solid rgba(168, 216, 255, 0.3);
  color: rgba(168, 216, 255, 0.9);
  padding: 10px 16px;
  border-radius: 8px;
  font-size: 0.85rem;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-browse:hover {
  background: rgba(168, 216, 255, 0.25);
  border-color: rgba(168, 216, 255, 0.5);
}

.btn-process {
  background: linear-gradient(135deg, rgba(168, 216, 255, 0.3) 0%, rgba(255, 182, 193, 0.3) 100%);
  border: 1px solid rgba(168, 216, 255, 0.4);
  color: #fff;
  padding: 14px 28px;
  border-radius: 12px;
  font-size: 1rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s ease;
  position: relative;
  overflow: hidden;
}

.btn-process::before {
  content: '';
  position: absolute;
  top: 0;
  left: -100%;
  width: 100%;
  height: 100%;
  background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.2), transparent);
  transition: left 0.5s;
}

.btn-process:hover:not(:disabled)::before {
  left: 100%;
}

.btn-process:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 6px 24px rgba(168, 216, 255, 0.3);
  border-color: rgba(168, 216, 255, 0.6);
}

.btn-process:disabled {
  opacity: 0.4;
  cursor: not-allowed;
  transform: none;
}

.processing {
  display: inline-block;
  animation: pulse 1.5s ease infinite;
}

@keyframes pulse {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0.5;
  }
}

.result-area {
  padding: 14px 18px;
  border-radius: 10px;
  text-align: center;
  animation: slideIn 0.3s ease;
}

@keyframes slideIn {
  from {
    opacity: 0;
    transform: translateY(-10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.result-area.success {
  background: rgba(100, 255, 150, 0.1);
  border: 1px solid rgba(100, 255, 150, 0.3);
  color: rgba(150, 255, 180, 0.95);
}

.result-area.error {
  background: rgba(255, 100, 100, 0.1);
  border: 1px solid rgba(255, 100, 100, 0.3);
  color: rgba(255, 150, 150, 0.95);
}

.footer {
  text-align: center;
  padding: 16px;
  color: rgba(255, 255, 255, 0.3);
  font-size: 0.75rem;
  position: relative;
  z-index: 1;
}
</style>
