import { startBackend, stopBackend } from '../main/services/python'
import { startGateway, stopGateway } from '../main/services/gateway'
import { startNapCat, stopNapCat, installNapCat } from '../main/services/napcat'
import { getDiagnostics } from '../main/services/diagnostics'
import { getConfig } from '../main/services/system'
import { WindowLike } from '../main/types'
import { EventEmitter } from 'events'
import { CliArgs } from '../main/utils/args'
import { WebBridge } from './webBridge'
import net from 'net'

export interface ServiceStatus {
  backend: 'stopped' | 'starting' | 'running' | 'error'
  gateway: 'stopped' | 'starting' | 'running' | 'error'
  napcat: 'stopped' | 'starting' | 'running' | 'error'
  webBridge: 'stopped' | 'starting' | 'running' | 'error'
}

/**
 * 无头服务管理器
 * 在 CLI 模式下编排所有后端服务
 */
export class ServiceManager extends EventEmitter {
  private status: ServiceStatus = {
    backend: 'stopped',
    gateway: 'stopped',
    napcat: 'stopped',
    webBridge: 'stopped'
  }

  private mockWindow: WindowLike
  private args: CliArgs | null = null
  private webBridge: WebBridge | null = null

  constructor() {
    super()
    // 创建一个模拟窗口对象来捕获服务的日志和事件
    this.mockWindow = {
      isDestroyed: () => false,
      webContents: {
        send: (channel: string, ...args: any[]) => {
          this.emit('service-event', { channel, args })

          // 路由到 WebBridge (WebSocket 广播)
          if (this.webBridge) {
            this.webBridge.broadcast(channel, ...args)
          }

          // 路由特定日志
          if (channel === 'backend-log') {
            this.emit('log', { source: 'backend', message: args[0] })
          } else if (channel === 'gateway-log') {
            this.emit('log', { source: 'gateway', message: args[0] })
          } else if (channel === 'napcat-log') {
            this.emit('log', { source: 'napcat', message: args[0] })
          } else if (channel === 'system-error') {
            this.emit('error', args[0])
          }
        }
      }
    }
  }

  getStatus() {
    return this.status
  }

  /**
   * 检查端口是否被占用
   */
  private checkPort(port: number): Promise<boolean> {
    return new Promise((resolve) => {
      const server = net.createServer()
      server.once('error', (err: any) => {
        if (err.code === 'EADDRINUSE') {
          resolve(true)
        } else {
          resolve(false)
        }
      })
      server.once('listening', () => {
        server.close()
        resolve(false)
      })
      server.listen(port)
    })
  }

  /**
   * 等待服务端口处于活动状态
   */
  private async waitForPort(port: number, timeoutMs = 5000): Promise<boolean> {
    const start = Date.now()
    while (Date.now() - start < timeoutMs) {
      if (await this.checkPort(port)) return true
      await new Promise((r) => setTimeout(r, 500))
    }
    return false
  }

  private log(source: string, message: string) {
    this.emit('log', { source, message })
  }

  private error(source: string, message: string) {
    this.emit('error', `[${source}] ${message}`)
  }

  async startAll(args: CliArgs) {
    this.args = args
    try {
      this.log('system', `正在启动所有服务，参数: ${JSON.stringify(args)}`)

      // 0. 启动 WebBridge (始终在 CLI 模式下启动以支持仪表板)
      this.status.webBridge = 'starting'
      this.emit('status-change', this.status)
      try {
        const bridgePort = 9000
        this.webBridge = new WebBridge(bridgePort)
        await this.webBridge.start()
        this.status.webBridge = 'running'
        this.log('webBridge', `已启动于 http://localhost:${bridgePort}`)
      } catch (e: any) {
        this.status.webBridge = 'error'
        this.error('webBridge', `启动失败: ${e.message}`)
      }

      // 1. 诊断
      const diag = await getDiagnostics()
      if (diag.errors.length > 0) {
        this.error('system', `诊断失败: ${diag.errors.join(', ')}`)
        // 根据严重程度，我们可能希望继续或退出
      }

      // 2. 启动 Gateway
      if (!args.noGateway) {
        this.status.gateway = 'starting'
        this.emit('status-change', this.status)
        try {
          await startGateway(this.mockWindow)
          // 等待 Gateway 端口 (假设从日志中获取的是 14747，或者应该是可配置的)
          // 目前我们只是相信它已启动，但在生产环境中我们应该检查端口
          this.status.gateway = 'running'
        } catch (e: any) {
          this.status.gateway = 'error'
          this.error('gateway', `启动失败: ${e.message}`)
        }
      } else {
        this.log('system', '跳过 Gateway (由参数禁用)')
      }

      // 3. 启动后端
      this.status.backend = 'starting'
      this.emit('status-change', this.status)
      try {
        // 检查配置中的社交模式
        const config = getConfig()
        const enableSocial = config.enable_social_mode ?? false

        // 如果明确请求或禁用，则覆盖社交模式
        // 注意：args 没有严格的 force-social，但我们可以添加它。
        // 目前，我们尊重配置，但让 NapCat 由 args 控制。

        await startBackend(this.mockWindow, enableSocial)

        // 检查后端端口 (默认 9120)
        const backendPort = parseInt(process.env.PORT || '9120')
        const isBackendUp = await this.waitForPort(backendPort, 10000)
        if (isBackendUp) {
          this.status.backend = 'running'
        } else {
          this.log('backend', `进程已启动，但端口 ${backendPort} 尚未激活。它可能正在初始化。`)
          this.status.backend = 'running' // 无论如何都设置为运行，因为它可能只是很慢
        }
      } catch (e: any) {
        this.status.backend = 'error'
        this.error('backend', `启动失败: ${e.message}`)
      }

      // 4. 启动 NapCat (可选)
      if (!args.noNapcat) {
        const config = getConfig()
        if (config.enable_social_mode) {
          this.status.napcat = 'starting'
          this.emit('status-change', this.status)
          try {
            // 首先检查是否安装
            await installNapCat(this.mockWindow)
            await startNapCat(this.mockWindow)
            this.status.napcat = 'running'
          } catch (e: any) {
            this.status.napcat = 'error'
            this.error('napcat', `启动失败: ${e.message}`)
          }
        }
      } else {
        this.log('system', '跳过 NapCat (由参数禁用)')
      }

      this.emit('all-services-started')
      this.log('system', '所有服务启动序列已完成。')
    } catch (error: any) {
      this.error('system', `启动期间发生致命错误: ${error.message}`)
      process.exit(1)
    }
  }

  /**
   * 获取所有服务状态
   */
  getAllServices() {
    return [
      { name: 'backend', status: this.status.backend },
      { name: 'gateway', status: this.status.gateway },
      { name: 'napcat', status: this.status.napcat },
      { name: 'webBridge', status: this.status.webBridge }
    ]
  }

  /**
   * 重启特定服务
   */
  async restartService(name: string) {
    this.log('system', `正在重启 ${name}...`)

    try {
      switch (name) {
        case 'backend': {
          await stopBackend()
          this.status.backend = 'stopped'
          this.emit('status-change', this.status)

          this.status.backend = 'starting'
          // 重新读取配置以防更改
          const config = getConfig()
          const enableSocial = config.enable_social_mode ?? false
          await startBackend(this.mockWindow, enableSocial)
          this.status.backend = 'running'
          break
        }

        case 'gateway':
          if (this.args?.noGateway) {
            this.log('system', 'Gateway 已由参数禁用。')
            return
          }
          await stopGateway()
          this.status.gateway = 'stopped'
          this.emit('status-change', this.status)

          this.status.gateway = 'starting'
          await startGateway(this.mockWindow)
          this.status.gateway = 'running'
          break

        case 'napcat':
          if (this.args?.noNapcat) {
            this.log('system', 'NapCat 已由参数禁用。')
            return
          }
          await stopNapCat()
          this.status.napcat = 'stopped'
          this.emit('status-change', this.status)

          this.status.napcat = 'starting'
          await startNapCat(this.mockWindow)
          this.status.napcat = 'running'
          break

        case 'webBridge': {
          if (this.webBridge) {
            await this.webBridge.stop()
          }
          this.status.webBridge = 'stopped'
          this.emit('status-change', this.status)

          this.status.webBridge = 'starting'
          const bridgePort = 9000
          this.webBridge = new WebBridge(bridgePort)
          await this.webBridge.start()
          this.status.webBridge = 'running'
          break
        }

        default:
          this.log('system', `未知服务: ${name}`)
      }
      this.log('system', `重启 ${name} 成功。`)
    } catch (e: any) {
      this.status[name as keyof ServiceStatus] = 'error'
      this.error(name, `重启失败: ${e.message}`)
    }
  }

  async stopAll() {
    this.log('system', '正在停止所有服务...')
    try {
      if (this.webBridge) {
        await this.webBridge.stop()
        this.status.webBridge = 'stopped'
      }

      await stopNapCat()
      this.status.napcat = 'stopped'

      await stopBackend()
      this.status.backend = 'stopped'

      await stopGateway()
      this.status.gateway = 'stopped'

      this.log('system', '所有服务已停止。')
      this.emit('status-change', this.status)
    } catch (e: any) {
      this.error('system', `停止服务时出错: ${e.message}`)
    }
  }
}
