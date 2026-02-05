import { app, BrowserWindow, shell, ipcMain, screen, Notification } from 'electron'
import { release } from 'os'
import { join } from 'path'
import { startBackend, stopBackend, getBackendLogs } from './services/python.js'
import { startGateway, stopGateway } from './services/gateway.js'
import { getDiagnostics } from './services/diagnostics.js'
import { getSystemStats, getConfig, saveConfig, getGatewayToken } from './services/system.js'
import { scanLocalAgents, getPlugins, saveAgentLaunchConfig, saveGlobalLaunchConfig } from './services/agents.js'
import { startNapCat, stopNapCat, getNapCatLogs, sendNapCatCommand, installNapCat } from './services/napcat.js'
import { checkEsInstalled, installEs } from './services/everything.js'
import { setupUpdater } from './services/updater.js'
import { windowManager } from './windows/manager.js'
import { createTray, destroyTray } from './services/tray.js'
import { registerShortcuts } from './services/shortcuts.js'
import { fileURLToPath } from 'url'
import { dirname } from 'path'
import axios from 'axios'
import { parseArgs } from './utils/args'
import { startCli } from '../cli/index'

// Check for CLI mode immediately
const args = parseArgs(process.argv)

if (args.cliMode) {
    // CLI Mode: Start ServiceManager and avoid GUI
    console.log('Detected CLI mode flag. Starting in Headless Mode...')
    startCli()
    // In CLI mode, we rely on Node's event loop (via readline) to keep running.
    // We do NOT hook into Electron's app lifecycle for window creation.
} else {
    // GUI Mode (Original Logic)

    // Disable GPU Acceleration for Windows 7
    // 禁用 Windows 7 的 GPU 加速
    if (release().startsWith('6.1')) app.disableHardwareAcceleration()

    // Standard flags for transparency support
    // 透明支持的标准标志
    app.commandLine.appendSwitch('disable-renderer-backgrounding')
    // [Fix] Resolve black background issue on some systems (e.g. multi-GPU or special hardware)
    // [修复] 解决某些系统（如多显卡或特殊硬件）上的黑背景问题
    app.commandLine.appendSwitch('disable-software-rasterizer')
    app.commandLine.appendSwitch('disable-gpu-compositing') 
    // Disable Autofill to prevent DevTools errors
    // 禁用自动填充以防止 DevTools 错误
    app.commandLine.appendSwitch('disable-features', 'Autofill')

    // Set application name for Windows 10+ notifications
    // 设置 Windows 10+ 通知的应用程序名称
    if (process.platform === 'win32') app.setAppUserModelId(app.getName())

    if (!app.requestSingleInstanceLock()) {
      app.quit()
      process.exit(0)
    }

    process.env['ELECTRON_DISABLE_SECURITY_WARNINGS'] = 'true'

    async function createWindow() {
      const win = windowManager.createLauncherWindow()

      // Setup auto updater
      setupUpdater()

      // Create system tray
      // 创建系统托盘
      createTray()

      // Register global shortcuts
      // 注册全局快捷键
      registerShortcuts()

      // Test active push message to Renderer-process
      // 测试向渲染进程主动推送消息
      win.webContents.on('did-finish-load', () => {
        try { if (!win.isDestroyed()) win.webContents.send('main-process-message', new Date().toLocaleString()) } catch(e){}
      })
    }

    app.whenReady().then(createWindow)

    app.on('window-all-closed', () => {
      // Do nothing, keep app running in tray
      // 什么都不做，保持应用在托盘中运行
      if (process.platform === 'darwin') return
    })

    app.on('before-quit', () => {
      stopBackend() // Ensure backend is killed // 确保后端被杀死
      stopGateway() // Ensure gateway is killed // 确保网关被杀死
    })

    app.on('second-instance', () => {
      const win = windowManager.launcherWin
      if (win) {
        // Focus on the main window if the user tried to open another
        // 如果用户尝试打开另一个窗口，则聚焦主窗口
        if (win.isMinimized()) win.restore()
        win.focus()
      }
    })

    app.on('activate', () => {
      const allWindows = BrowserWindow.getAllWindows()
      if (allWindows.length) {
        allWindows[0].focus()
      } else {
        createWindow()
      }
    })

    // IPC Handlers - Log from Renderer
    ipcMain.on('log-from-renderer', (_, message) => {
      console.log('[Renderer]', message)
    })
    
    // ... existing IPC handlers would go here if they were inline, 
    // but looking at previous file content, there were just imports and then some handlers maybe?
    // Let's check if I missed any IPC handlers at the bottom of the file.
}
