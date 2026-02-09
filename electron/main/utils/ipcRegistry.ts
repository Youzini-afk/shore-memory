import { isElectron } from './env'

// 定义处理程序类型
type IpcHandler = (event: any, ...args: any[]) => Promise<any> | any
type IpcListener = (event: any, ...args: any[]) => void

// CLI 模式下 IPC 处理程序的全局注册表
class IpcRegistry {
  private handlers: Map<string, IpcHandler> = new Map()
  private listeners: Map<string, IpcListener[]> = new Map()

  // 注册处理程序 (ipcMain.handle)
  registerHandler(channel: string, handler: IpcHandler) {
    if (!isElectron) {
      // console.log(`[IpcRegistry] 已注册处理程序: ${channel}`)
      this.handlers.set(channel, handler)
    }
  }

  // 注册监听器 (ipcMain.on)
  registerListener(channel: string, listener: IpcListener) {
    if (!isElectron) {
      // console.log(`[IpcRegistry] 已注册监听器: ${channel}`)
      if (!this.listeners.has(channel)) {
        this.listeners.set(channel, [])
      }
      this.listeners.get(channel)?.push(listener)
    }
  }

  // 调用处理程序 (由 WebBridge 调用)
  async invoke(channel: string, ...args: any[]) {
    const handler = this.handlers.get(channel)
    if (handler) {
      // 如果需要，创建模拟事件对象
      const event = { sender: { send: () => {} } }
      return await handler(event, ...args)
    }
    throw new Error(`未注册频道的处理程序: ${channel}`)
  }

  // 发出事件 (模拟 ipcMain.emit 或内部事件)
  emit(channel: string, ...args: any[]) {
    const listeners = this.listeners.get(channel)
    if (listeners) {
      const event = { sender: { send: () => {} } }
      listeners.forEach((l) => l(event, ...args))
    }
  }
}

export const ipcRegistry = new IpcRegistry()
