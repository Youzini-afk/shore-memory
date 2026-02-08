import { BrowserWindow, app, shell, screen } from 'electron'
import { join } from 'path'
import { existsSync } from 'fs'
import { is } from '@electron-toolkit/utils'
import { logger } from '../utils/logger'

export class WindowManager {
  private static instance: WindowManager

  public launcherWin: BrowserWindow | null = null
  public petWin: BrowserWindow | null = null
  public dashboardWin: BrowserWindow | null = null
  public ideWin: BrowserWindow | null = null

  private mouseTrackInterval: NodeJS.Timeout | null = null

  private constructor() {}

  public static getInstance(): WindowManager {
    if (!WindowManager.instance) {
      WindowManager.instance = new WindowManager()
    }
    return WindowManager.instance
  }

  private getPreloadPath(): string {
    return join(__dirname, '../../preload/index.js')
  }

  private getIconPath(): string {
    // Prefer ICO on Windows for better quality/compatibility
    const iconName = process.platform === 'win32' ? 'icon.ico' : 'icon.png'
    const paths = [
      join(process.cwd(), 'public', iconName), // Dev
      join(process.cwd(), 'resources', iconName), // Prod
      join(process.resourcesPath, iconName), // Prod resources
      join(__dirname, '../../public', iconName), // Relative dev
      join(__dirname, '../../../public', iconName), // Relative dev deep
      join(__dirname, '../../', iconName) // Fallback
    ]
    for (const p of paths) {
      if (existsSync(p)) {
        return p
      }
    }
    return ''
  }

  private getPageUrl(route: string = ''): string {
    if (process.env.VITE_DEV_SERVER_URL) {
      return `${process.env.VITE_DEV_SERVER_URL}#${route}`
    } else {
      return `file://${join(__dirname, '../../../dist/index.html')}#${route}`
    }
  }

  public createLauncherWindow(): BrowserWindow {
    if (this.launcherWin && !this.launcherWin.isDestroyed()) {
      if (!this.launcherWin.isVisible()) this.launcherWin.show()
      if (this.launcherWin.isMinimized()) this.launcherWin.restore()
      this.launcherWin.focus()
      return this.launcherWin
    }

    this.launcherWin = new BrowserWindow({
      title: 'Pero Launcher',
      icon: this.getIconPath(),
      width: 900,
      height: 600,
      // 等待 ready-to-show
      show: false,
      frame: false,
      center: true,
      transparent: true,
      hasShadow: true,
      // 允许亚克力透出
      backgroundColor: '#00000000',
      webPreferences: {
        preload: this.getPreloadPath(),
        nodeIntegration: true,
        contextIsolation: true,
        backgroundThrottling: false
      }
    })

    // 亚克力效果
    if (process.platform === 'win32') {
      try {
        this.launcherWin.setBackgroundMaterial('acrylic')
      } catch (e) {
        // 忽略错误
      }
    }

    this.launcherWin.loadURL(this.getPageUrl('/launcher'))
    logger.info('Main', `Loading URL: ${this.getPageUrl('/launcher')}`)

    this.launcherWin.on('ready-to-show', () => {
      logger.info('Main', 'Window ready-to-show event fired')
      this.launcherWin?.show()
    })

    this.launcherWin.webContents.on('did-fail-load', (event, errorCode, errorDescription) => {
      logger.error('Main', `Failed to load: ${errorDescription} (${errorCode})`)
    })

    // Handle external links
    // 处理外部链接
    this.launcherWin.webContents.setWindowOpenHandler(({ url }) => {
      if (url.startsWith('https:')) shell.openExternal(url)
      return { action: 'deny' }
    })

    return this.launcherWin
  }

  public createPetWindow(): BrowserWindow {
    if (this.petWin && !this.petWin.isDestroyed()) {
      if (!this.petWin.isVisible()) this.petWin.show()
      if (this.petWin.isMinimized()) this.petWin.restore()
      this.petWin.focus()
      return this.petWin
    }

    // Get screen size to position pet initially (e.g. bottom right)
    // 获取屏幕尺寸以初始定位宠物 (例如右下角)
    const { screen } = require('electron')
    const primaryDisplay = screen.getPrimaryDisplay()
    const { width, height } = primaryDisplay.workAreaSize

    this.petWin = new BrowserWindow({
      title: 'Pero Pet',
      icon: this.getIconPath(),
      width: 600,
      height: 600,
      x: width - 650,
      y: height - 650,
      // type: 'toolbar', // 已移除: 'toolbar' 可能在某些 Windows 版本上导致可见性问题
      frame: false,
      transparent: true, // 恢复透明
      backgroundColor: '#00000000', // 显式设置 ARGB 透明
      alwaysOnTop: true,
      skipTaskbar: true,
      hasShadow: false,
      resizable: false, // 恢复不可调整大小
      webPreferences: {
        preload: this.getPreloadPath(),
        nodeIntegration: true,
        contextIsolation: true,
        backgroundThrottling: false,
        webSecurity: false // Allow loading local resources via fetch
      }
    })

    // 根据用户请求，默认加载 Pet3DView
    this.petWin.loadURL(this.getPageUrl('/pet-3d'))

    // 打开 DevTools 以调试渲染器崩溃/错误
    // this.petWin.webContents.openDevTools({ mode: 'detach' })

    this.petWin.setAlwaysOnTop(true, 'screen-saver')

    // 忽略鼠标事件以实现透明点击穿透
    // 默认: 忽略所有，让特定元素通过 IPC 捕获
    // 常用模式: 渲染器根据悬停/点击发送 IPC 来设置忽略状态。

    // 初始状态: 可交互
    this.petWin.setIgnoreMouseEvents(false)

    // 强制显示
    this.petWin.show()

    // 修复某些系统上的可见性问题
    this.petWin.on('ready-to-show', () => {
      this.petWin?.show()
      this.petWin?.setAlwaysOnTop(true, 'screen-saver')
    })

    this.startMouseTracking()

    this.petWin.on('closed', () => {
      this.stopMouseTracking()
      this.petWin = null
    })

    return this.petWin
  }

  private startMouseTracking() {
    if (this.mouseTrackInterval) return

    // 30 FPS mouse tracking
    // 30 FPS 鼠标追踪
    this.mouseTrackInterval = setInterval(() => {
      if (!this.petWin || this.petWin.isDestroyed()) {
        this.stopMouseTracking()
        return
      }

      try {
        const point = screen.getCursorScreenPoint()
        const bounds = this.petWin.getBounds()

        // Calculate relative position
        // 计算相对位置
        const relativeX = point.x - bounds.x
        const relativeY = point.y - bounds.y

        // Send to renderer
        // 发送到渲染进程
        this.petWin.webContents.send('global-mouse-move', { x: relativeX, y: relativeY })
      } catch (e) {
        logger.error('Main', `鼠标追踪错误: ${e}`)
      }
    }, 33)
  }

  private stopMouseTracking() {
    if (this.mouseTrackInterval) {
      clearInterval(this.mouseTrackInterval)
      this.mouseTrackInterval = null
    }
  }

  public createDashboardWindow(): BrowserWindow {
    if (this.dashboardWin && !this.dashboardWin.isDestroyed()) {
      if (this.dashboardWin.isMinimized()) this.dashboardWin.restore()
      this.dashboardWin.focus()
      return this.dashboardWin
    }

    this.dashboardWin = new BrowserWindow({
      title: 'Pero Dashboard',
      icon: this.getIconPath(),
      width: 1280,
      height: 800,
      show: false,
      frame: false,
      center: true,
      transparent: true,
      hasShadow: true,
      backgroundColor: '#00000000', // Allow acrylic to show through // 允许亚克力效果透出
      webPreferences: {
        preload: this.getPreloadPath(),
        nodeIntegration: true,
        contextIsolation: true,
        backgroundThrottling: false
      }
    })

    if (process.platform === 'win32') {
      try {
        this.dashboardWin.setBackgroundMaterial('acrylic')
      } catch (e) {
        // Ignore
        // 忽略
      }
    }

    this.dashboardWin.loadURL(this.getPageUrl('/dashboard'))
    logger.info('Main', `Dashboard loading URL: ${this.getPageUrl('/dashboard')}`)

    this.dashboardWin.on('ready-to-show', () => {
      logger.info('Main', 'Dashboard ready-to-show')
      this.dashboardWin?.show()
    })

    // Force show if ready-to-show doesn't fire (e.g. renderer crash or slow load)
    setTimeout(() => {
      if (this.dashboardWin && !this.dashboardWin.isDestroyed() && !this.dashboardWin.isVisible()) {
        logger.info('Main', 'Force showing Dashboard (timeout)')
        this.dashboardWin.show()
      }
    }, 2000)

    this.dashboardWin.webContents.on('did-fail-load', (event, errorCode, errorDescription) => {
      logger.error('Main', `Dashboard failed to load: ${errorDescription} (${errorCode})`)
    })

    // Handle external links
    // 处理外部链接
    this.dashboardWin.webContents.setWindowOpenHandler(({ url }) => {
      if (url.startsWith('https:')) shell.openExternal(url)
      return { action: 'deny' }
    })

    return this.dashboardWin
  }

  public createIDEWindow(): BrowserWindow {
    if (this.ideWin && !this.ideWin.isDestroyed()) {
      if (this.ideWin.isMinimized()) this.ideWin.restore()
      this.ideWin.focus()
      return this.ideWin
    }

    this.ideWin = new BrowserWindow({
      title: 'Pero IDE',
      icon: this.getIconPath(),
      width: 1400,
      height: 900,
      show: false,
      frame: false,
      center: true,
      transparent: true,
      hasShadow: true,
      webPreferences: {
        preload: this.getPreloadPath(),
        nodeIntegration: true,
        contextIsolation: true,
        backgroundThrottling: false
      }
    })

    if (process.platform === 'win32') {
      try {
        this.ideWin.setBackgroundMaterial('acrylic')
      } catch (e) {}
    }

    this.ideWin.loadURL(this.getPageUrl('/ide'))

    this.ideWin.on('ready-to-show', () => {
      this.ideWin?.show()
    })

    this.ideWin.webContents.setWindowOpenHandler(({ url }) => {
      if (url.startsWith('https:')) shell.openExternal(url)
      return { action: 'deny' }
    })

    return this.ideWin
  }
}

export const windowManager = WindowManager.getInstance()
