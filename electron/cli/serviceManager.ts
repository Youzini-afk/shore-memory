import { startBackend, stopBackend, getBackendLogs } from '../main/services/python'
import { startGateway, stopGateway, getGatewayLogs } from '../main/services/gateway'
import { startNapCat, stopNapCat, getNapCatLogs, installNapCat } from '../main/services/napcat'
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
 * Headless Service Manager
 * Orchestrates all backend services in CLI mode
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
    // Create a mock window object to capture logs and events from services
    this.mockWindow = {
      isDestroyed: () => false,
      webContents: {
        send: (channel: string, ...args: any[]) => {
          this.emit('service-event', { channel, args })

          // Route to WebBridge (WebSocket broadcast)
          if (this.webBridge) {
            this.webBridge.broadcast(channel, ...args)
          }

          // Route specific logs
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
   * Checks if a port is in use
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
   * Waits for a service port to be active
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
      this.log('system', `Starting all services with args: ${JSON.stringify(args)}`)

      // 0. Start WebBridge (Always start in CLI mode to support dashboard)
      this.status.webBridge = 'starting'
      this.emit('status-change', this.status)
      try {
        const bridgePort = 9000
        this.webBridge = new WebBridge(bridgePort)
        await this.webBridge.start()
        this.status.webBridge = 'running'
        this.log('webBridge', `Started at http://localhost:${bridgePort}`)
      } catch (e: any) {
        this.status.webBridge = 'error'
        this.error('webBridge', `Failed to start: ${e.message}`)
      }

      // 1. Diagnostics
      const diag = await getDiagnostics()
      if (diag.errors.length > 0) {
        this.error('system', `Diagnostics failed: ${diag.errors.join(', ')}`)
        // We might want to continue or exit depending on severity
      }

      // 2. Start Gateway
      if (!args.noGateway) {
        this.status.gateway = 'starting'
        this.emit('status-change', this.status)
        try {
          await startGateway(this.mockWindow)
          // Wait for Gateway port (assuming 14747 from logs, or should be configurable)
          // For now we just trust it started, but in production we should check port
          this.status.gateway = 'running'
        } catch (e: any) {
          this.status.gateway = 'error'
          this.error('gateway', `Failed to start: ${e.message}`)
        }
      } else {
        this.log('system', 'Skipping Gateway (disabled by args)')
      }

      // 3. Start Backend
      this.status.backend = 'starting'
      this.emit('status-change', this.status)
      try {
        // Check config for social mode
        const config = getConfig()
        const enableSocial = config.enable_social_mode ?? false

        // Override social mode if explicitly requested or disabled
        // Note: args doesn't strictly have force-social, but we could add it.
        // For now, we respect config, but let NapCat be controlled by args.

        await startBackend(this.mockWindow, enableSocial)

        // Check backend port (default 9120)
        const backendPort = parseInt(process.env.PORT || '9120')
        const isBackendUp = await this.waitForPort(backendPort, 10000)
        if (isBackendUp) {
          this.status.backend = 'running'
        } else {
          this.log(
            'backend',
            `Process started but port ${backendPort} is not yet active. It might be initializing.`
          )
          this.status.backend = 'running' // Set running anyway as it might just be slow
        }
      } catch (e: any) {
        this.status.backend = 'error'
        this.error('backend', `Failed to start: ${e.message}`)
      }

      // 4. Start NapCat (Optional)
      if (!args.noNapcat) {
        const config = getConfig()
        if (config.enable_social_mode) {
          this.status.napcat = 'starting'
          this.emit('status-change', this.status)
          try {
            // Check if installed first
            await installNapCat(this.mockWindow)
            await startNapCat(this.mockWindow)
            this.status.napcat = 'running'
          } catch (e: any) {
            this.status.napcat = 'error'
            this.error('napcat', `Failed to start: ${e.message}`)
          }
        }
      } else {
        this.log('system', 'Skipping NapCat (disabled by args)')
      }

      this.emit('all-services-started')
      this.log('system', 'All services startup sequence completed.')
    } catch (error: any) {
      this.error('system', `Fatal error during startup: ${error.message}`)
      process.exit(1)
    }
  }

  /**
   * Get all services status
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
   * Restart a specific service
   */
  async restartService(name: string) {
    this.log('system', `Restarting ${name}...`)

    try {
      switch (name) {
        case 'backend':
          await stopBackend()
          this.status.backend = 'stopped'
          this.emit('status-change', this.status)

          this.status.backend = 'starting'
          // Re-read config in case it changed
          const config = getConfig()
          const enableSocial = config.enable_social_mode ?? false
          await startBackend(this.mockWindow, enableSocial)
          this.status.backend = 'running'
          break

        case 'gateway':
          if (this.args?.noGateway) {
            this.log('system', 'Gateway is disabled by args.')
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
            this.log('system', 'NapCat is disabled by args.')
            return
          }
          await stopNapCat()
          this.status.napcat = 'stopped'
          this.emit('status-change', this.status)

          this.status.napcat = 'starting'
          await startNapCat(this.mockWindow)
          this.status.napcat = 'running'
          break

        case 'webBridge':
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

        default:
          this.log('system', `Unknown service: ${name}`)
      }
      this.log('system', `Restarted ${name} successfully.`)
    } catch (e: any) {
      this.status[name as keyof ServiceStatus] = 'error'
      this.error(name, `Restart failed: ${e.message}`)
    }
  }

  async stopAll() {
    this.log('system', 'Stopping all services...')
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

      this.log('system', 'All services stopped.')
      this.emit('status-change', this.status)
    } catch (e: any) {
      this.error('system', `Error stopping services: ${e.message}`)
    }
  }
}
