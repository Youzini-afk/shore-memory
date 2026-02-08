import { isElectron } from './env'

// Define handler types
type IpcHandler = (event: any, ...args: any[]) => Promise<any> | any
type IpcListener = (event: any, ...args: any[]) => void

// Global Registry for IPC Handlers in CLI Mode
class IpcRegistry {
  private handlers: Map<string, IpcHandler> = new Map()
  private listeners: Map<string, IpcListener[]> = new Map()

  // Register a handler (ipcMain.handle)
  registerHandler(channel: string, handler: IpcHandler) {
    if (!isElectron) {
      // console.log(`[IpcRegistry] Registered handler: ${channel}`)
      this.handlers.set(channel, handler)
    }
  }

  // Register a listener (ipcMain.on)
  registerListener(channel: string, listener: IpcListener) {
    if (!isElectron) {
      // console.log(`[IpcRegistry] Registered listener: ${channel}`)
      if (!this.listeners.has(channel)) {
        this.listeners.set(channel, [])
      }
      this.listeners.get(channel)?.push(listener)
    }
  }

  // Invoke a handler (called by WebBridge)
  async invoke(channel: string, ...args: any[]) {
    const handler = this.handlers.get(channel)
    if (handler) {
      // Create a mock event object if needed
      const event = { sender: { send: () => {} } }
      return await handler(event, ...args)
    }
    throw new Error(`No handler registered for channel: ${channel}`)
  }

  // Emit an event (simulating ipcMain.emit or internal events)
  emit(channel: string, ...args: any[]) {
    const listeners = this.listeners.get(channel)
    if (listeners) {
      const event = { sender: { send: () => {} } }
      listeners.forEach((l) => l(event, ...args))
    }
  }
}

export const ipcRegistry = new IpcRegistry()
