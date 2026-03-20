import { BrowserWindow, shell, screen } from 'electron'
import { join } from 'path'
import { existsSync } from 'fs'
import { logger } from '../utils/logger'

export class WindowManager {
  private static instance: WindowManager

  public launcherWin: BrowserWindow | null = null
  public strongholdWin: BrowserWindow | null = null
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
    // __dirname = dist-electron/main/windows, 需要向上2层到 dist-electron/
    return join(__dirname, '../../preload/index.js')
  }

  private getIconPath(): string {
    const iconName = 'Logo.png'
    const paths = [
      join(process.cwd(), 'public', iconName), // 开发环境
      join(process.cwd(), 'resources', iconName), // 生产环境
      join(process.resourcesPath, iconName), // 生产环境资源
      join(__dirname, '../../public', iconName), // 相对路径开发环境
      join(__dirname, '../../../public', iconName), // 相对路径深层开发环境
      join(__dirname, '../../', iconName) // 后备
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
      // 使用 app.getAppPath() 获取 asar 根路径，比相对路径更稳健
      const { app } = require('electron')
      const indexPath = join(app.getAppPath(), 'dist', 'index.html')
      return `file://${indexPath}#${route}`
    }
  }

  private setupWindowStateListeners(window: BrowserWindow) {
    window.on('maximize', () => {
      window.webContents.send('window-maximized-state-changed', true)
    })
    window.on('unmaximize', () => {
      window.webContents.send('window-maximized-state-changed', false)
    })
    window.on('restore', () => {
      // restore 也会在从最小化恢复时触发，所以检查是否是最大化状态
      window.webContents.send('window-maximized-state-changed', window.isMaximized())
    })
    window.on('resize', () => {
      // 某些情况下系统事件可能不完整，resize 是最后的保障
      window.webContents.send('window-maximized-state-changed', window.isMaximized())
    })
  }

  public createLauncherWindow(): BrowserWindow {
    if (this.launcherWin && !this.launcherWin.isDestroyed()) {
      if (!this.launcherWin.isVisible()) this.launcherWin.show()
      if (this.launcherWin.isMinimized()) this.launcherWin.restore()
      this.launcherWin.focus()
      return this.launcherWin
    }

    this.launcherWin = new BrowserWindow({
      title: '萌动链接：PeroperoChat！',
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
      } catch {
        // 忽略错误
      }
    }

    this.launcherWin.loadURL(this.getPageUrl('/launcher'))
    logger.info('Main', `正在加载 URL: ${this.getPageUrl('/launcher')}`)

    this.setupWindowStateListeners(this.launcherWin)

    this.launcherWin.on('ready-to-show', () => {
      logger.info('Main', '窗口 ready-to-show 事件已触发')
      if (this.launcherWin) {
        this.launcherWin.show()
      }
    })

    // 兜底方案：如果 5 秒内 ready-to-show 没触发，强制显示并记录警告
    setTimeout(() => {
      if (this.launcherWin && !this.launcherWin.isVisible() && !this.launcherWin.isDestroyed()) {
        logger.warn('Main', 'ready-to-show 超时，正在强制显示窗口')
        this.launcherWin.show()
      }
    }, 5000)

    this.launcherWin.webContents.on('did-fail-load', (event, errorCode, errorDescription) => {
      logger.error('Main', `Failed to load: ${errorDescription} (${errorCode})`)
    })

    // 处理外部链接
    this.launcherWin.webContents.setWindowOpenHandler(({ url }) => {
      if (url.startsWith('https:')) shell.openExternal(url)
      return { action: 'deny' }
    })

    this.launcherWin.on('closed', () => {
      this.launcherWin = null
    })

    return this.launcherWin
  }

  public closeLauncherWindow() {
    if (this.launcherWin && !this.launcherWin.isDestroyed()) {
      this.launcherWin.close()
    }
  }

  public createStrongholdWindow(): BrowserWindow {
    if (this.strongholdWin && !this.strongholdWin.isDestroyed()) {
      if (!this.strongholdWin.isVisible()) this.strongholdWin.show()
      if (this.strongholdWin.isMinimized()) this.strongholdWin.restore()
      this.strongholdWin.focus()
      return this.strongholdWin
    }

    this.strongholdWin = new BrowserWindow({
      title: '萌动链接：PeroperoChat！',
      icon: this.getIconPath(),
      width: 1200,
      height: 800,
      show: false,
      frame: false,
      center: true,
      transparent: true,
      hasShadow: true,
      backgroundColor: '#00000000',
      webPreferences: {
        preload: this.getPreloadPath(),
        nodeIntegration: true,
        contextIsolation: true
      }
    })

    if (process.platform === 'win32') {
      try {
        this.strongholdWin.setBackgroundMaterial('acrylic')
      } catch {
        // 忽略
      }
    }

    this.strongholdWin.loadURL(this.getPageUrl('/stronghold'))

    this.setupWindowStateListeners(this.strongholdWin)

    this.strongholdWin.on('ready-to-show', () => {
      this.strongholdWin?.show()
    })

    return this.strongholdWin
  }

  public createPetWindow(): BrowserWindow {
    if (this.petWin && !this.petWin.isDestroyed()) {
      if (!this.petWin.isVisible()) this.petWin.show()
      if (this.petWin.isMinimized()) this.petWin.restore()
      this.petWin.focus()
      return this.petWin
    }

    // 获取屏幕尺寸以初始定位宠物 (例如右下角)
    const primaryDisplay = screen.getPrimaryDisplay()
    const { width, height } = primaryDisplay.workAreaSize

    this.petWin = new BrowserWindow({
      title: '萌动链接：PeroperoChat！',
      icon: this.getIconPath(),
      width: 800,
      height: 800,
      x: width - 850,
      y: height - 850,
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
        webSecurity: false // 允许通过 fetch 加载本地资源
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

    // 30 FPS 鼠标追踪
    this.mouseTrackInterval = setInterval(() => {
      if (!this.petWin || this.petWin.isDestroyed()) {
        this.stopMouseTracking()
        return
      }

      try {
        const point = screen.getCursorScreenPoint()
        const bounds = this.petWin.getBounds()

        // 计算相对位置
        const relativeX = point.x - bounds.x
        const relativeY = point.y - bounds.y

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
      title: '萌动链接：PeroperoChat！',
      icon: this.getIconPath(),
      width: 1280,
      height: 800,
      show: false,
      frame: false,
      center: true,
      transparent: true,
      hasShadow: true,
      backgroundColor: '#00000000', // 允许亚克力效果透出
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
      } catch {
        // 忽略
      }
    }

    // [Steam] Steam Overlay 已在应用启动时全局初始化
    // 注意：Steam Overlay 通常只能依附于一个渲染进程。
    // 我们选择 DashboardView 作为主要依附对象，因为它是一个标准窗口，适合展示 Overlay。

    this.dashboardWin.loadURL(this.getPageUrl('/dashboard'))
    logger.info('Main', `Dashboard 正在加载 URL: ${this.getPageUrl('/dashboard')}`)

    this.setupWindowStateListeners(this.dashboardWin)

    this.dashboardWin.on('ready-to-show', () => {
      logger.info('Main', 'Dashboard ready-to-show')
      this.dashboardWin?.show()
    })

    // 如果 ready-to-show 未触发 (例如渲染器崩溃或加载缓慢)，则强制显示
    setTimeout(() => {
      if (this.dashboardWin && !this.dashboardWin.isDestroyed() && !this.dashboardWin.isVisible()) {
        logger.info('Main', '强制显示 Dashboard (超时)')
        this.dashboardWin.show()
      }
    }, 2000)

    this.dashboardWin.webContents.on('did-fail-load', (event, errorCode, errorDescription) => {
      logger.error('Main', `Dashboard 加载失败: ${errorDescription} (${errorCode})`)
    })

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
      title: '萌动链接：PeroperoChat！',
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
      } catch {
        // 忽略
      }
    }

    this.ideWin.loadURL(this.getPageUrl('/ide'))

    this.setupWindowStateListeners(this.ideWin)

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
