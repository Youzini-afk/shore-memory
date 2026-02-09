import { TUI, ProcessTerminal, Container, Text, Editor } from '@mariozechner/pi-tui'
import chalk from 'chalk'
import { ServiceManager } from '../serviceManager'

// Theme Configuration
const theme = {
  text: (t: string) => chalk.hex('#E8E3D5')(t),
  dim: (t: string) => chalk.hex('#7B7F87')(t),
  accent: (t: string) => chalk.hex('#F6C453')(t),
  accentSoft: (t: string) => chalk.hex('#F2A65A')(t),
  error: (t: string) => chalk.hex('#F97066')(t),
  success: (t: string) => chalk.hex('#7DD3A5')(t),
  header: (t: string) => chalk.bold.bgHex('#2B2F36').hex('#F6C453')(t),
  prompt: (t: string) => chalk.bold.hex('#F6C453')(t)
}

const editorTheme = {
  borderColor: (t: string) => chalk.hex('#3C414B')(t),
  selectList: {
    selectedPrefix: (t: string) => chalk.hex('#F6C453')(t),
    selectedText: (t: string) => chalk.bold.hex('#F6C453')(t),
    description: (t: string) => chalk.hex('#7B7F87')(t),
    scrollInfo: (t: string) => chalk.hex('#7B7F87')(t),
    noMatch: (t: string) => chalk.hex('#7B7F87')(t)
  }
}

export class TuiManager {
  private tui: TUI
  private serviceManager: ServiceManager
  private logContainer: Container
  private header: Text
  private input: Editor
  private isRunning: boolean = true

  constructor(serviceManager: ServiceManager) {
    this.serviceManager = serviceManager

    // 1. 初始化 TUI 引擎 (pi-tui)
    this.tui = new TUI(new ProcessTerminal())

    // 2. 构建布局
    const root = new Container()

    // 头部 (状态栏)
    this.header = new Text(theme.header(' PeroCore CLI '), 1, 0)
    root.addChild(this.header)

    // 日志区域 (主要内容)
    this.logContainer = new Container()
    root.addChild(this.logContainer)

    // 输入区域
    this.input = new Editor(this.tui, editorTheme)
    // 注意: pi-tui Editor 不直接支持 'prompt' 属性。
    // 如果需要，我们依赖 UI 布局或自定义渲染。
    root.addChild(this.input)

    // 添加根节点到 TUI
    this.tui.addChild(root)
    this.tui.setFocus(this.input)

    // 3. 设置逻辑
    this.setupEvents()
    this.setupInput()

    // 4. 初始消息
    this.log(theme.accent('PeroCore CLI (pi-tui 版) 已启动。'))
    this.log(theme.dim('输入 /help 查看命令。'))

    // 5. 启动 TUI 循环
    this.tui.start()
  }

  public log(text: string) {
    // 限制历史记录为 200 行以防止内存问题
    if (this.logContainer.children.length > 200) {
      this.logContainer.children.shift()
    }
    // 添加新日志行 (高度 1, 宽度 0=全宽)
    this.logContainer.addChild(new Text(text, 1, 0))
  }

  private setupEvents() {
    this.serviceManager.on('log', (data: { source: string; message: string }) => {
      const source = data.source || 'unknown'
      const message = data.message || JSON.stringify(data)
      this.log(`${theme.accentSoft(`[${source}]`)} ${theme.text(message)}`)
    })

    this.serviceManager.on('error', (text: string) => {
      this.log(theme.error(text))
    })
  }

  private setupInput() {
    // 编辑器 onSubmit 回调
    this.input.onSubmit = (text: string) => {
      const cmd = text.trim()
      if (!cmd) return

      this.input.setText('') // Clear input
      this.handleCommand(cmd)
    }
  }

  private handleCommand(cmd: string) {
    this.log(theme.dim(`$ ${cmd}`))

    const parts = cmd.split(' ')
    const command = parts[0]
    const args = parts.slice(1)

    switch (command) {
      case '/exit':
        this.log(theme.error('正在退出...'))
        this.shutdown()
        break
      case '/clear':
        this.logContainer.clear()
        break
      case '/status':
        this.showStatus()
        break
      case '/restart':
        if (args[0]) {
          this.serviceManager.restartService(args[0])
          this.log(theme.accent(`正在重启 ${args[0]}...`))
        } else {
          this.log(theme.error('用法: /restart <service>'))
        }
        break
      case '/stop':
        this.serviceManager.stopAll()
        this.log(theme.accent('正在停止所有服务...'))
        break
      case '/help':
        this.showHelp()
        break
      default:
        this.log(theme.error(`未知命令: ${command}`))
    }
  }

  private showHelp() {
    const commands = [
      '/status - 显示服务状态',
      '/restart <service> - 重启服务',
      '/stop - 停止所有服务',
      '/clear - 清除日志',
      '/exit - 退出 CLI'
    ]
    commands.forEach((c) => this.log(theme.accentSoft(c)))
  }

  private async showStatus() {
    const services = this.serviceManager.getAllServices()
    for (const s of services) {
      const color =
        s.status === 'running' ? theme.success : s.status === 'error' ? theme.error : theme.dim
      this.log(`${theme.accent(s.name)}: ${color(s.status)}`)
    }
  }

  private shutdown() {
    this.isRunning = false
    process.exit(0)
  }
}
