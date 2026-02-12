<script setup lang="ts">
import { ref } from 'vue'
import {
  Menu as IconMenu,
  ChatLineRound,
  Cpu,
  Bell,
  User,
  SetUp,
  Microphone,
  Connection,
  ChatDotSquare,
  Monitor,
  Warning,
  SwitchButton
} from '@element-plus/icons-vue'

// Mock Data

const currentTab = ref('overview')

const handleTabSelect = (index: string) => {
  currentTab.value = index
}

const handleQuitApp = () => {
  // 不执行任何反应
}
</script>

<template>
  <div class="dashboard-wrapper-demo">
    <div class="custom-title-bar-mock">
      <span>Pero Dashboard (Demo)</span>
    </div>

    <!-- 动态背景 -->
    <div class="background-blobs">
      <div class="blob blob-1"></div>
      <div class="blob blob-2"></div>
      <div class="blob blob-3"></div>
    </div>

    <el-container class="main-layout">
      <!-- 侧边导航栏 -->
      <el-aside width="260px" class="glass-sidebar">
        <el-menu :default-active="currentTab" class="sidebar-menu" @select="handleTabSelect">
          <el-menu-item index="overview">
            <el-icon><IconMenu /></el-icon>
            <span>总览</span>
          </el-menu-item>
          <el-menu-item index="logs">
            <el-icon><ChatLineRound /></el-icon>
            <span>对话日志</span>
          </el-menu-item>
          <el-menu-item index="memories">
            <el-icon><Cpu /></el-icon>
            <span>核心记忆</span>
          </el-menu-item>
          <el-menu-item index="tasks">
            <el-icon><Bell /></el-icon>
            <span>待办任务</span>
          </el-menu-item>
          <el-menu-item index="user_settings">
            <el-icon><User /></el-icon>
            <span>用户设定</span>
          </el-menu-item>
          <el-menu-item index="model_config">
            <el-icon><SetUp /></el-icon>
            <span>模型配置</span>
          </el-menu-item>
          <el-menu-item index="voice_config">
            <el-icon><Microphone /></el-icon>
            <span>语音功能</span>
          </el-menu-item>
          <el-menu-item index="mcp_config">
            <el-icon><Connection /></el-icon>
            <span>MCP 配置</span>
          </el-menu-item>
          <el-menu-item index="napcat">
            <el-icon><ChatDotSquare /></el-icon>
            <span>NapCat 终端</span>
          </el-menu-item>
          <el-menu-item index="terminal">
            <el-icon><Monitor /></el-icon>
            <span>系统终端</span>
          </el-menu-item>
          <el-menu-item index="system_reset" style="color: #f56c6c">
            <el-icon><Warning /></el-icon>
            <span>危险区域</span>
          </el-menu-item>
        </el-menu>

        <div class="sidebar-footer">
          <el-button class="quit-button" type="danger" plain @click="handleQuitApp">
            <el-icon><SwitchButton /></el-icon>
            <span>退出系统</span>
          </el-button>
        </div>
      </el-aside>

      <el-container>
        <!-- 主内容区 -->
        <el-main class="content-area">
          <div class="view-container-wrapper">
            <!-- 1. 仪表盘概览 -->
            <div v-if="currentTab === 'overview'" class="view-container">
              <div style="margin-top: 40px; text-align: center; color: #666">
                <h2>欢迎使用 PeroCore 控制面板</h2>
                <p>点击左侧菜单查看不同功能模块 (演示版)</p>
              </div>
            </div>
            <div v-else class="view-container placeholder-view">
              <el-empty :description="currentTab + ' 页面 (演示模式)'" />
            </div>
          </div>
        </el-main>
      </el-container>
    </el-container>
  </div>
</template>

<style scoped>
.dashboard-wrapper-demo {
  position: relative;
  width: 100%;
  aspect-ratio: 16 / 9;
  background-color: #fce7f3; /* pink-50 */
  overflow: hidden;
  border-radius: 12px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
  color: #374151;
}

.custom-title-bar-mock {
  height: 32px;
  background: rgba(255, 255, 255, 0.6);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  color: #666;
  border-bottom: 1px solid rgba(0, 0, 0, 0.05);
  position: relative;
  z-index: 10;
}

/* 动态背景 */
.background-blobs {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  overflow: hidden;
  z-index: 0;
  pointer-events: none;
}

.blob {
  position: absolute;
  border-radius: 50%;
  filter: blur(60px);
  opacity: 0.6;
  animation: float 20s infinite ease-in-out;
}

.blob-1 {
  width: 400px;
  height: 400px;
  background: #fbcfe8; /* pink-200 */
  top: -100px;
  left: -100px;
  animation-delay: 0s;
}

.blob-2 {
  width: 300px;
  height: 300px;
  background: #ddd6fe; /* violet-200 */
  bottom: -50px;
  right: -50px;
  animation-delay: -5s;
}

.blob-3 {
  width: 250px;
  height: 250px;
  background: #bae6fd; /* sky-200 */
  top: 40%;
  left: 40%;
  animation-delay: -10s;
}

@keyframes float {
  0%,
  100% {
    transform: translate(0, 0) scale(1);
  }
  33% {
    transform: translate(30px, -50px) scale(1.1);
  }
  66% {
    transform: translate(-20px, 20px) scale(0.9);
  }
}

.main-layout {
  height: calc(100% - 32px); /* Minus title bar */
  backdrop-filter: blur(10px);
  position: relative;
  z-index: 1;
}

.glass-sidebar {
  background: rgba(255, 255, 255, 0.4);
  border-right: 1px solid rgba(255, 255, 255, 0.5);
  display: flex;
  flex-direction: column;
  transition: all 0.3s ease;
}

.brand-area {
  padding: 24px 0 20px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}

.logo-box {
  width: 64px;
  height: 64px;
  background: linear-gradient(135deg, #ec4899 0%, #8b5cf6 100%);
  border-radius: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 12px;
  box-shadow: 0 8px 16px rgba(236, 72, 153, 0.2);
}

.logo-placeholder {
  color: white;
  font-size: 32px;
  font-weight: bold;
}

.brand-text {
  text-align: center;
}

.brand-text h1 {
  margin: 0;
  font-size: 20px;
  font-weight: 700;
  background: linear-gradient(to right, #db2777, #7c3aed);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  line-height: 1.2;
}

.version-tag {
  font-size: 10px;
  background: rgba(255, 255, 255, 0.5);
  padding: 2px 6px;
  border-radius: 10px;
  color: #666;
}

.sidebar-menu {
  background: transparent !important;
  border-right: none !important;
  flex: 1;
  overflow-y: auto;
  padding: 0 12px;
}

:deep(.el-menu-item) {
  height: 44px;
  line-height: 44px;
  border-radius: 8px;
  margin-bottom: 4px;
  color: #4b5563;
  font-weight: 500;
}

:deep(.el-menu-item:hover) {
  background-color: rgba(255, 255, 255, 0.5);
}

:deep(.el-menu-item.is-active) {
  background: linear-gradient(to right, rgba(236, 72, 153, 0.1), rgba(139, 92, 246, 0.1));
  color: #db2777;
  font-weight: 600;
}

.sidebar-footer {
  padding: 20px;
  border-top: 1px solid rgba(255, 255, 255, 0.3);
}

.quit-button {
  width: 100%;
  border-radius: 8px;
  justify-content: center;
  font-weight: 600;
}

.content-area {
  padding: 20px;
  overflow-y: auto;
  background: rgba(255, 255, 255, 0.2);
}

.view-container {
  height: 100%;
}

.placeholder-view {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  background: rgba(255, 255, 255, 0.3);
  border-radius: 12px;
}

.stat-card {
  border: none;
  border-radius: 16px;
  color: white;
  transition: transform 0.3s;
}

.stat-card:hover {
  transform: translateY(-5px);
}

.pink-gradient {
  background: linear-gradient(135deg, #f472b6 0%, #db2777 100%);
  box-shadow: 0 8px 16px rgba(219, 39, 119, 0.3);
}

.blue-gradient {
  background: linear-gradient(135deg, #60a5fa 0%, #2563eb 100%);
  box-shadow: 0 8px 16px rgba(37, 99, 235, 0.3);
}

.purple-gradient {
  background: linear-gradient(135deg, #a78bfa 0%, #7c3aed 100%);
  box-shadow: 0 8px 16px rgba(124, 58, 237, 0.3);
}

.stat-content {
  display: flex;
  align-items: center;
}

.stat-icon {
  font-size: 32px;
  margin-right: 16px;
  background: rgba(255, 255, 255, 0.2);
  width: 56px;
  height: 56px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.stat-info h3 {
  margin: 0;
  font-size: 14px;
  opacity: 0.9;
  font-weight: 500;
}

.stat-info .number {
  font-size: 24px;
  font-weight: 700;
  margin-top: 4px;
}
</style>
