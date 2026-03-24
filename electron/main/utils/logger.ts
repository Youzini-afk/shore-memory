import dayjs from 'dayjs'
import fs from 'fs-extra'
import path from 'path'
import os from 'os'

export type LogLevel = 'INFO' | 'WARN' | 'ERROR' | 'DEBUG'
export type LogSource =
  | 'Main'
  | 'Renderer'
  | 'Gateway'
  | 'Backend'
  | 'Plugin'
  | 'System'
  | 'ModelDownload'
  | 'Native'
  | 'AssetProtocol'
  | 'Assets'

class Logger {
  private static instance: Logger
  private logFile: string | null = null
  private secondaryLogFile: string | null = null   // 开发模式下同时写入 %APPDATA%

  // 隐藏模式 (降噪)
  // 优化: 组合正则以获得更好的性能
  private hiddenPattern: RegExp = new RegExp(
    [
      '\\[vite\\]',
      'page reload',
      'Found \\d+ errors\\. Watching for file changes',
      'Files found:',
      'sys\\.argv:',
      'ENABLE_SOCIAL_MODE 环境变量:',
      'Logging initialized at level',
      'Using Gateway Token:',
      'Connecting to Gateway',
      'Connected to Gateway',
      'checkNapCatInstalled result:',
      'Python found at:',
      'Python Version:',
      '发现安装路径:',
      '工作区:',
      '资源目录:',
      '已索引 Agent Prompt:',
      '已添加 Agent 目录到加载路径:',
      'MDP: 已',
      '从 .* 加载 了 \\d+ 个 MDP 提示词',
      '正在扫描类别:',
      'Discovered plugin',
      'Loading URL:',
      'ready-to-show',
      'did-fail-load',
      'Force showing Dashboard',
      '托盘图标候选路径',
      '选定的托盘图标路径',
      'checkNapCatInstalled',
      '令牌无效',
      'Received envelope from'
    ].join('|')
  )

  // 翻译映射 (英语 -> 中文)
  // 优化: 使用 Map 进行精确匹配的 O(1) 查找，正则用于模式匹配
  private translations: Array<{ from: RegExp | string; to: string }> = [
    { from: 'Window ready-to-show event fired', to: '窗口准备就绪' },
    { from: 'Loading URL', to: '正在加载页面' },
    { from: 'Dashboard loading URL', to: '仪表盘正在加载' },
    { from: 'Dashboard ready-to-show', to: '仪表盘准备就绪' },
    { from: 'Dashboard failed to load', to: '仪表盘加载失败' },
    { from: 'Force showing Dashboard', to: '强制显示仪表盘' },
    { from: 'Gateway process exited with code', to: '网关进程退出，代码' },
    { from: 'Generated New Gateway Access Token', to: '已生成新的网关访问令牌' },
    { from: 'PeroGateway started on', to: 'PeroGateway 已启动于' },
    { from: 'Invalid token from', to: '令牌无效，来自' },
    { from: 'Expected:', to: '期望值:' },
    { from: 'Scheduler started', to: '调度器已启动' },
    { from: 'Loaded config from ENV', to: '已从环境变量加载配置' },
    { from: 'Loaded plugin', to: '已加载插件' },
    { from: 'Returned', to: '返回了' },
    { from: 'plugins', to: '个插件' },
    { from: 'Files found', to: '发现文件' },
    { from: 'Gateway Token Path', to: '网关令牌路径' },
    { from: 'Service initialized', to: '服务已初始化' },
    { from: 'Starting Gateway from', to: '正在启动 Gateway' },
    { from: 'Removing old token file', to: '正在删除旧令牌文件' },
    { from: 'Waiting for token file creation', to: '正在等待令牌文件生成' },
    { from: 'Gateway started successfully', to: 'Gateway 启动成功' },
    { from: 'Logging initialized', to: '日志系统已初始化' },
    { from: 'Python found at', to: '发现 Python 环境' },
    { from: 'Python Version', to: 'Python 版本' },
    { from: 'checkNapCatInstalled result', to: 'NapCat 安装检查结果' }
  ]

  constructor() {
    this.initializeLogFile()
  }

  private initializeLogFile() {
    try {
      // 动态获取路径，避免循环依赖
      // 注意: logger 在 env.ts 之前被加载，不能直接 import paths，需自行检测模式
      let primaryDir = ''
      let systemDir = ''   // %APPDATA% 路径（用于开发模式双写）

      try {
        const { app } = require('electron')
        if (app) {
          const exePath = app.getPath('exe')
          const portableMarker = path.join(path.dirname(exePath), '.portable')

          if (fs.existsSync(portableMarker)) {
            // 便携模式：日志存在 exe 同目录
            primaryDir = path.dirname(exePath)
          } else if (!app.isPackaged) {
            // 开发模式：主日志在 backend/data/logs/，同时写 %APPDATA% 副本
            const projectRoot = path.resolve(__dirname, '../../..')
            primaryDir = path.join(projectRoot, 'backend')
            systemDir = app.getPath('userData')   // %APPDATA%/...
          } else {
            // 发行模式
            primaryDir = app.getPath('userData')
          }
        }
      } catch {
        // 非 Electron 环境
        primaryDir = process.env.PERO_USER_DATA || path.join(os.homedir(), '.perocore')
      }

      // 初始化主日志文件
      if (primaryDir) {
        const logDir = path.join(primaryDir, 'data', 'logs')
        if (!fs.existsSync(logDir)) {
          fs.mkdirSync(logDir, { recursive: true })
        }
        this.logFile = path.join(logDir, 'main.log')
        fs.writeFileSync(this.logFile, `--- Log started at ${new Date().toISOString()} ---\n`)
      }

      // 初始化开发模式副本日志文件（%APPDATA%）
      if (systemDir && systemDir !== primaryDir) {
        const sysLogDir = path.join(systemDir, 'logs')
        if (!fs.existsSync(sysLogDir)) {
          fs.mkdirSync(sysLogDir, { recursive: true })
        }
        this.secondaryLogFile = path.join(sysLogDir, 'main.log')
        fs.writeFileSync(this.secondaryLogFile, `--- Log started at ${new Date().toISOString()} (dev secondary) ---\n`)
      }
    } catch (e) {
      console.error('[Logger] 初始化日志文件失败:', e)
    }
  }

  static getInstance(): Logger {
    if (!Logger.instance) {
      Logger.instance = new Logger()
    }
    return Logger.instance
  }

  private shouldHide(message: string): boolean {
    // 快速路径: 首先检查长度或公共前缀
    if (message.length > 500) return false // 不过滤长消息 (可能很重要)
    if (message.startsWith('[vite]')) return true

    return this.hiddenPattern.test(message)
  }

  private translate(message: string): string {
    // 快速路径: 如果消息很短，跳过翻译
    if (message.length < 2) return message

    // 快速路径: 跳过已知日志格式的翻译以节省 CPU
    // 例如 [2026-...] [INFO] ...
    if (message.startsWith('[') && message.includes('] [')) return message

    let translated = message
    for (const { from, to } of this.translations) {
      if (typeof from === 'string') {
        if (translated.includes(from)) {
          translated = translated.replace(from, to)
        }
      } else {
        if (from.test(translated)) {
          translated = translated.replace(from, to)
        }
      }
    }
    return translated
  }

  public log(source: LogSource, level: LogLevel, message: string) {
    if (this.shouldHide(message)) {
      return
    }

    const translatedMsg = this.translate(message)
    const timestamp = dayjs().format('HH:mm:ss')

    // 统一格式: [HH:mm:ss] [SOURCE] [LEVEL] 消息
    const formattedLog = `[${timestamp}] [${source}] [${level}] ${translatedMsg}`

    // 写入主日志文件
    if (this.logFile) {
      try {
        fs.appendFileSync(this.logFile, formattedLog + '\n')
      } catch {
        // 忽略写入失败
      }
    }

    // 写入副本日志文件（开发模式下同时写入 %APPDATA%）
    if (this.secondaryLogFile) {
      try {
        fs.appendFileSync(this.secondaryLogFile, formattedLog + '\n')
      } catch {
        // 忽略写入失败
      }
    }

    // 根据级别使用 console.log/error 以保留终端颜色 (如果可用)，
    // 或者只是标准输出。
    if (level === 'ERROR') {
      console.error(formattedLog)
    } else if (level === 'WARN') {
      console.warn(formattedLog)
    } else {
      console.log(formattedLog)
    }
  }

  public info(source: LogSource, message: string) {
    this.log(source, 'INFO', message)
  }

  public warn(source: LogSource, message: string) {
    this.log(source, 'WARN', message)
  }

  public error(source: LogSource, message: string) {
    this.log(source, 'ERROR', message)
  }

  public debug(source: LogSource, message: string) {
    this.log(source, 'DEBUG', message)
  }
}

export const logger = Logger.getInstance()
