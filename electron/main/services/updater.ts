import { autoUpdater } from 'electron-updater'
import { ipcMain, BrowserWindow } from 'electron'

// 日志记录器
autoUpdater.logger = console

export function setupUpdater() {
  autoUpdater.autoDownload = false
  autoUpdater.autoInstallOnAppQuit = true

  const sendToAll = (event: string, data: any) => {
    BrowserWindow.getAllWindows().forEach((win) => {
      if (!win.isDestroyed()) {
        win.webContents.send(event, data)
      }
    })
  }

  autoUpdater.on('checking-for-update', () => {
    sendToAll('update-message', { type: 'checking' })
  })

  autoUpdater.on('update-available', (info) => {
    sendToAll('update-message', { type: 'available', info })
  })

  autoUpdater.on('update-not-available', (info) => {
    sendToAll('update-message', { type: 'not-available', info })
  })

  autoUpdater.on('error', (err) => {
    sendToAll('update-message', { type: 'error', error: err.message })
  })

  autoUpdater.on('download-progress', (progressObj) => {
    sendToAll('update-message', { type: 'progress', progress: progressObj })
  })

  autoUpdater.on('update-downloaded', (info) => {
    sendToAll('update-message', { type: 'downloaded', info })
  })

  // 移除现有的处理程序以避免重复
  ipcMain.removeHandler('check_update')
  ipcMain.removeHandler('download_update')
  ipcMain.removeHandler('quit_and_install')

  ipcMain.handle('check_update', async () => {
    try {
      return await autoUpdater.checkForUpdates()
    } catch (e) {
      console.error('检查更新失败:', e)
      throw e
    }
  })

  ipcMain.handle('download_update', () => {
    autoUpdater.downloadUpdate()
  })

  ipcMain.handle('quit_and_install', () => {
    autoUpdater.quitAndInstall()
  })
}
