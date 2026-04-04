import { contextBridge, ipcRenderer } from 'electron'

contextBridge.exposeInMainWorld('electron', {
  invoke: (channel: string, ...args: any[]) => ipcRenderer.invoke(channel, ...args),
  send: (channel: string, ...args: any[]) => ipcRenderer.send(channel, ...args),
  on: (channel: string, listener: (event: any, ...args: any[]) => void) => {
    ipcRenderer.on(channel, listener)
    return () => ipcRenderer.removeListener(channel, listener)
  },
  loadPeroModel: (buffer: Uint8Array, filterPatterns?: string[]) =>
    ipcRenderer.invoke('native-load-pero-model', buffer, filterPatterns),
  loadStandardModel: (buffer: Uint8Array, filterPatterns?: string[]) =>
    ipcRenderer.invoke('native-load-standard-model', buffer, filterPatterns),
  loadPeroContainer: (buffer: Uint8Array) =>
    ipcRenderer.invoke('native-load-pero-container', buffer),
  scanLocalModels: () => ipcRenderer.invoke('scan-local-models'),
  // 暴露应用根路径，供渲染进程将相对 assets/ 路径转换为 asset:// 绝对路径
  appPath: () => ipcRenderer.invoke('get-app-path')
})
