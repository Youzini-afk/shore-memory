import {
  TUI,
  ProcessTerminal,
  Container,
  Text,
  Editor,
  Key,
  matchesKey
} from '@mariozechner/pi-tui'
import chalk from 'chalk'
import si from 'systeminformation'
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

    // 1. Initialize TUI Engine (pi-tui)
    this.tui = new TUI(new ProcessTerminal())

    // 2. Build Layout
    const root = new Container()

    // Header (Status Bar)
    this.header = new Text(theme.header(' PeroCore CLI '), 1, 0)
    root.addChild(this.header)

    // Log Area (Main Content)
    this.logContainer = new Container()
    root.addChild(this.logContainer)

    // Input Area
    this.input = new Editor(this.tui, editorTheme)
    // Note: pi-tui Editor doesn't support 'prompt' property directly.
    // We rely on the UI layout or custom rendering if needed.
    root.addChild(this.input)

    // Add Root to TUI
    this.tui.addChild(root)
    this.tui.setFocus(this.input)

    // 3. Setup Logic
    this.setupEvents()
    this.setupInput()

    // 4. Initial Message
    this.log(theme.accent('PeroCore CLI (pi-tui edition) started.'))
    this.log(theme.dim('Type /help for commands.'))

    // 5. Start TUI Loop
    this.tui.start()
  }

  public log(text: string) {
    // Limit history to 200 lines to prevent memory issues
    if (this.logContainer.children.length > 200) {
      this.logContainer.children.shift()
    }
    // Add new log line (Height 1, Width 0=Full)
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
    // Editor onSubmit callback
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
        this.log(theme.error('Exiting...'))
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
          this.log(theme.accent(`Restarting ${args[0]}...`))
        } else {
          this.log(theme.error('Usage: /restart <service>'))
        }
        break
      case '/stop':
        this.serviceManager.stopAll()
        this.log(theme.accent('Stopping all services...'))
        break
      case '/help':
        this.showHelp()
        break
      default:
        this.log(theme.error(`Unknown command: ${command}`))
    }
  }

  private showHelp() {
    const commands = [
      '/status - Show service status',
      '/restart <service> - Restart a service',
      '/stop - Stop all services',
      '/clear - Clear logs',
      '/exit - Exit CLI'
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
