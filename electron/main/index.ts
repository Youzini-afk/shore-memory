import { app, BrowserWindow, shell, ipcMain, screen, Notification } from 'electron'
import { release } from 'os'
import { join } from 'path'
import { startBackend, stopBackend, getBackendLogs } from './services/python.js'
import { startGateway, stopGateway } from './services/gateway.js'
import { getDiagnostics } from './services/diagnostics.js'
import { getSystemStats, getConfig, saveConfig, getGatewayToken } from './services/system.js'
import {
  scanLocalAgents,
  getPlugins,
  saveAgentLaunchConfig,
  saveGlobalLaunchConfig
} from './services/agents.js'
import {
  startNapCat,
  stopNapCat,
  getNapCatLogs,
  sendNapCatCommand,
  installNapCat
} from './services/napcat.js'
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
import { logger } from './utils/logger'

// Check for CLI mode immediately
const args = parseArgs(process.argv)

if (args.cliMode) {
  // CLI Mode: Start ServiceManager and avoid GUI
  logger.info('Main', 'Detected CLI mode flag. Starting in Headless Mode...')
  startCli()
  // In CLI mode, we rely on Node's event loop (via readline) to keep running.
  // We do NOT hook into Electron's app lifecycle for window creation.
} else {
  // GUI Mode (Original Logic)

  // 禁用 Windows 7 的 GPU 加速
  if (release().startsWith('6.1')) app.disableHardwareAcceleration()

  // 透明支持的标准标志
  app.commandLine.appendSwitch('disable-renderer-backgrounding')

  // 移除了导致 AMD 显卡不透明问题的激进 GPU 禁用标志
  // app.commandLine.appendSwitch('disable-software-rasterizer')
  // app.commandLine.appendSwitch('disable-gpu-compositing')

  // 禁用自动填充和原生窗口遮挡计算
  app.commandLine.appendSwitch('disable-features', 'Autofill')
  app.commandLine.appendSwitch('disable-features', 'CalculateNativeWinOcclusion')

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
      try {
        if (!win.isDestroyed())
          win.webContents.send('main-process-message', new Date().toLocaleString())
      } catch (e) {}
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
    logger.info('Renderer', message)
  })

  ipcMain.on('show-notification', (_, { title, body }) => {
    new Notification({ title, body }).show()
  })

  ipcMain.handle('resize-pet-window', (event, { width, height }) => {
    const win = BrowserWindow.fromWebContents(event.sender)
    if (win) {
      logger.info('Main', `IPC: Resizing window to ${width}x${height}`)
      try {
        // 临时允许调整大小以确保操作系统接受更改 (特别是在具有透明窗口的 Windows 上)
        win.setResizable(true)
        win.setMinimumSize(200, 200) // 重置限制

        // Use setBounds for better atomic update
        // 使用 setBounds 进行更好的原子更新
        const bounds = win.getBounds()
        win.setBounds({
          x: bounds.x,
          y: bounds.y,
          width: Math.round(width),
          height: Math.round(height)
        })

        // Revert resizable state
        // 恢复可调整大小状态
        win.setResizable(false)
        return true
      } catch (e) {
        logger.error('Main', `IPC: Resize failed: ${e}`)
        return false
      }
    }
    return false
  })

  ipcMain.handle('emit_event', (_, { event, payload }) => {
    BrowserWindow.getAllWindows().forEach((win) => {
      if (!win.isDestroyed()) win.webContents.send(event, payload)
    })
  })

  ipcMain.handle('chat-message', async (_, args) => {
    try {
      const token = getGatewayToken()
      const port = 9120
      const { message } = args

      logger.info('Main', `IPC: 正在发送聊天消息到后端: ${message}`)

      await axios.post(
        `http://localhost:${port}/api/ide/chat`,
        {
          messages: [{ role: 'user', content: message }],
          source: 'desktop',
          session_id: 'default'
        },
        {
          headers: {
            Authorization: `Bearer ${token}`,
            'Content-Type': 'application/json'
          }
        }
      )
      return { status: 'ok' }
    } catch (error: any) {
      logger.error('Main', `IPC: chat-message 失败: ${error.message}`)
      throw error
    }
  })

  // IPC Handlers - Tauri Adapter
  // IPC 处理程序 - Tauri 适配器
  logger.info('Main', '主进程: 正在注册 IPC 处理程序...')
  ipcMain.handle('get_diagnostics', async () => {
    return await getDiagnostics()
  })

  ipcMain.handle('start_backend', async (_, args) => {
    // Tauri invoke passes args as object { enableSocialMode: true }
    // Tauri invoke 将 args 作为对象传递 { enableSocialMode: true }
    const win = windowManager.launcherWin
    if (!win) return
    try {
      // Start Gateway first
      await startGateway(win)
      // Then start Backend
      await startBackend(win, args?.enableSocialMode ?? false)
      return null // Ok(())
    } catch (e: any) {
      throw e.message
    }
  })

  ipcMain.handle('start_gateway', async (event) => {
    const win = BrowserWindow.fromWebContents(event.sender)
    if (win) await startGateway(win)
  })

  ipcMain.handle('stop_backend', async () => {
    stopBackend()
    stopGateway()
  })

  ipcMain.handle('quit_app', () => {
    app.quit()
  })

  ipcMain.handle('get_system_stats', async () => {
    return await getSystemStats()
  })

  ipcMain.handle('get_config', () => {
    const config = getConfig()
    logger.info('Main', `IPC: get_config 返回配置: ${JSON.stringify(config)}`)
    return config
  })

  ipcMain.handle('get_gateway_token', () => {
    return getGatewayToken()
  })

  ipcMain.handle('save_config', (_, args) => {
    logger.info('Main', `IPC: save_config 收到数据: ${JSON.stringify(args)}`)
    // Frontend sends { config: ... } to match Tauri signature
    // 前端发送 { config: ... } 以匹配 Tauri 签名
    let config = args.config || args

    // Robust unwrapping/cleaning logic
    // 健壮的解包/清理逻辑
    if (config && typeof config === 'object' && 'config' in config) {
      const keys = Object.keys(config)
      // If config has other keys, 'config' property is likely garbage
      // 如果 config 有其他键，'config' 属性可能是垃圾数据
      if (keys.length > 1) {
        delete config.config
      } else {
        // If config ONLY has 'config' property, it is likely a wrapper
        // 如果 config 只有 'config' 属性，它可能是一个包装器
        config = config.config
      }
    }

    logger.info('Main', `IPC: 正在保存处理后的配置: ${JSON.stringify(config)}`)
    saveConfig(config)
    return null
  })

  // Mocks for missing handlers to prevent errors
  // 缺失处理程序的模拟，以防止错误
  ipcMain.handle('get_plugins', async () => {
    return await getPlugins()
  })
  ipcMain.handle('check_es', () => checkEsInstalled())
  ipcMain.handle('get_backend_logs', () => getBackendLogs())
  ipcMain.handle('scan_local_agents', async () => {
    return await scanLocalAgents()
  })
  ipcMain.handle('check_napcat', async () => {
    const diag = await getDiagnostics()
    return diag.napcat_installed
  })

  ipcMain.handle('save_agent_launch_config', async (_, args) => {
    // Check if arguments match the global config signature: { enabledAgents, activeAgent }
    // 检查参数是否匹配全局配置签名: { enabledAgents, activeAgent }
    if (args && Array.isArray(args.enabledAgents) && typeof args.activeAgent === 'string') {
      return await saveGlobalLaunchConfig(args.enabledAgents, args.activeAgent)
    }

    // Fallback or specific agent config: { agentId, config }
    // 后备或特定代理配置: { agentId, config }
    if (args && args.agentId && args.config) {
      return await saveAgentLaunchConfig(args.agentId, args.config)
    }

    throw new Error('Invalid arguments for save_agent_launch_config')
  })

  // [Fix] Add missing handler for save_global_launch_config called by LauncherView
  ipcMain.handle('save_global_launch_config', async (_, args) => {
    if (args && Array.isArray(args.enabledAgents) && typeof args.activeAgent === 'string') {
      return await saveGlobalLaunchConfig(args.enabledAgents, args.activeAgent)
    }
    throw new Error('Invalid arguments for save_global_launch_config')
  })

  ipcMain.handle('install_es', async () => {
    const win = windowManager.launcherWin
    if (!win) return false
    return await installEs(win)
  })

  ipcMain.handle('install_napcat', async () => {
    const win = windowManager.launcherWin
    if (!win) return false
    try {
      return await installNapCat(win)
    } catch (e: any) {
      return false
    }
  })

  ipcMain.handle('start_napcat', async () => {
    const win = windowManager.launcherWin
    if (!win) return
    try {
      await startNapCat(win)
    } catch (e: any) {
      throw e.message
    }
  })

  ipcMain.handle('stop_napcat_wrapper', async () => {
    stopNapCat()
  })

  ipcMain.handle('get_napcat_logs', () => {
    return getNapCatLogs()
  })

  ipcMain.handle('send_napcat_command_wrapper', (_, args) => {
    // Check if args is string or object { command: string }
    // 检查 args 是字符串还是对象 { command: string }
    const cmd = typeof args === 'string' ? args : args?.command
    if (cmd) sendNapCatCommand(cmd)
  })

  ipcMain.handle('open_root_folder', () => {
    shell.openPath(process.cwd())
  })

  ipcMain.handle('open_pet_window', () => {
    windowManager.createPetWindow()
    return true
  })

  ipcMain.handle('hide_pet_window', () => {
    windowManager.petWin?.hide()
  })

  ipcMain.handle('open_dashboard_window', () => {
    windowManager.createDashboardWindow()
  })

  ipcMain.handle('open_dashboard', () => {
    windowManager.createDashboardWindow()
  })

  ipcMain.handle('open_ide_window', () => {
    windowManager.createIDEWindow()
  })

  ipcMain.handle('set_ignore_mouse', (event, ignore: boolean) => {
    const window = BrowserWindow.fromWebContents(event.sender)
    window?.setIgnoreMouseEvents(ignore, { forward: true })
  })

  ipcMain.handle('set_fix_window_topmost', (event) => {
    const window = BrowserWindow.fromWebContents(event.sender)
    window?.setAlwaysOnTop(true, 'screen-saver')
  })

  let dragInterval: NodeJS.Timeout | null = null

  ipcMain.on('window-drag-start', (event, { offsetX, offsetY }) => {
    const window = BrowserWindow.fromWebContents(event.sender)
    if (!window) return

    if (dragInterval) clearInterval(dragInterval)

    // Cache size for setBounds optimization (smoother on Windows)
    // 缓存大小以进行 setBounds 优化 (在 Windows 上更平滑)
    const { width, height } = window.getBounds()

    // Polling mouse position in main process to move window directly
    // This avoids IPC latency loop and provides native-like smoothness
    // 在主进程中轮询鼠标位置以直接移动窗口
    // 避免 IPC 延迟，提供原生般流畅体验
    dragInterval = setInterval(() => {
      try {
        if (window.isDestroyed()) {
          if (dragInterval) clearInterval(dragInterval)
          return
        }

        const cursor = screen.getCursorScreenPoint()
        // Use setBounds which is often atomic and smoother than setPosition
        // 使用 setBounds，它通常是原子的，并且比 setPosition 更平滑
        window.setBounds({
          x: cursor.x - Math.round(offsetX),
          y: cursor.y - Math.round(offsetY),
          width,
          height
        })
      } catch (e) {
        logger.error('Main', `拖拽错误: ${e}`)
        if (dragInterval) clearInterval(dragInterval)
      }
    }, 1) // 1ms interval (max smoothness) // 1ms 间隔 (最大平滑度)
  })

  ipcMain.on('window-drag-end', () => {
    if (dragInterval) {
      clearInterval(dragInterval)
      dragInterval = null
    }
  })

  // Keep old handlers for compatibility or fallback
  // 保留旧的处理程序以实现兼容性或回退
  ipcMain.on('window-move-fast', (event, { x, y }) => {
    const window = BrowserWindow.fromWebContents(event.sender)
    if (window) {
      window.setPosition(Math.round(x), Math.round(y))
    }
  })

  ipcMain.handle('window-move', (event, { x, y }) => {
    const window = BrowserWindow.fromWebContents(event.sender)
    if (window) {
      // console.log(`[IPC] Moving window to: ${x}, ${y}`)
      window.setPosition(Math.round(x), Math.round(y))
    }
  })

  // Window Controls
  // 窗口控制
  ipcMain.handle('window-minimize', (event) => {
    const window = BrowserWindow.fromWebContents(event.sender)
    window?.minimize()
  })
  ipcMain.handle('window-maximize', (event) => {
    const window = BrowserWindow.fromWebContents(event.sender)
    if (window?.isMaximized()) {
      window.unmaximize()
    } else {
      window?.maximize()
    }
  })
  ipcMain.handle('window-close', (event) => {
    const window = BrowserWindow.fromWebContents(event.sender)
    window?.close()
  })
  ipcMain.handle('window-is-maximized', (event) => {
    const window = BrowserWindow.fromWebContents(event.sender)
    return window?.isMaximized()
  })

  ipcMain.handle('show_window', (event) => {
    const window = BrowserWindow.fromWebContents(event.sender)
    if (window) {
      window.show()
      window.focus()
    }
  })

  ipcMain.handle('window-show', (event) => {
    const window = BrowserWindow.fromWebContents(event.sender)
    if (window) {
      window.show()
      window.focus()
    }
  })

  ipcMain.handle('window-focus', (event) => {
    const window = BrowserWindow.fromWebContents(event.sender)
    window?.focus()
  })

  ipcMain.handle('close_dashboard', () => {
    windowManager.dashboardWin?.close()
  })

  ipcMain.handle('get_app_version', () => {
    return app.getVersion()
  })

  ipcMain.handle('open-win', (_, arg) => {
    // Use window manager later? For now simple implementation
    // 稍后使用窗口管理器？目前是简单的实现
    const childWindow = new BrowserWindow({
      webPreferences: {
        preload: join(__dirname, '../preload/index.js')
      }
    })
    if (process.env.VITE_DEV_SERVER_URL) {
      childWindow.loadURL(`${process.env.VITE_DEV_SERVER_URL}#${arg}`)
    } else {
      childWindow.loadFile(join(__dirname, '../../dist/index.html'), { hash: arg })
    }
  })
}
