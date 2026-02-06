import { app } from 'electron'
import dayjs from 'dayjs'

export type LogLevel = 'INFO' | 'WARN' | 'ERROR' | 'DEBUG'
export type LogSource = 'Main' | 'Renderer' | 'Gateway' | 'Backend' | 'Plugin' | 'System'

class Logger {
  private static instance: Logger
  
  // Patterns to hide (Noise reduction)
  // Optimized: Combined regex for better performance
  private hiddenPattern: RegExp = new RegExp([
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
    'checkNapCatInstalled'
  ].join('|'))

  // Translation map (English -> Chinese)
  // Optimized: Use a Map for O(1) lookup of exact matches, and regex for patterns
  private translations: Array<{ from: RegExp | string, to: string }> = [
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

  constructor() {}

  static getInstance(): Logger {
    if (!Logger.instance) {
      Logger.instance = new Logger()
    }
    return Logger.instance
  }

  private shouldHide(message: string): boolean {
    // Fast path: Check length or common prefixes first
    if (message.length > 500) return false; // Don't filter long messages (likely important)
    if (message.startsWith('[vite]')) return true;
    
    return this.hiddenPattern.test(message)
  }

  private translate(message: string): string {
    // Fast path: if message is very short, skip translation
    if (message.length < 2) return message
    
    // Fast path: skip translation for known log formats to save CPU
    // e.g. [2026-...] [INFO] ...
    if (message.startsWith('[') && message.includes('] [')) return message;
    
    let translated = message
    // Most translations are specific phrases. We can check if the message *contains* key words first?
    // But since we have a list of replacements, iterating is necessary unless we rebuild the whole string.
    // However, we can optimize by only replacing if the source string is present.
    
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
    
    // Unified format: [HH:mm:ss] [SOURCE] [LEVEL] Message
    const formattedLog = `[${timestamp}] [${source}] [${level}] ${translatedMsg}`

    // Use console.log/error based on level to preserve terminal colors if available, 
    // or just standard output.
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
