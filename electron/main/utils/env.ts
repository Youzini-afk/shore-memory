import path from 'path'
import os from 'os'

export const isElectron = !!process.versions.electron

let appUserData: string
let appPath: string
let appExe: string

if (isElectron) {
  // 动态 require 以避免在纯 Node.js 中运行时出现问题
  // eslint-disable-next-line @typescript-eslint/no-var-requires, @typescript-eslint/no-require-imports
  const { app } = require('electron')
  appUserData = app.getPath('userData')
  appPath = app.getAppPath()
  appExe = app.getPath('exe')
} else {
  // CLI / Docker 环境
  const HOME = os.homedir()
  // 默认为 ~/.perocore 或遵循环境变量
  appUserData = process.env.PERO_USER_DATA || path.join(HOME, '.perocore')
  appPath = process.cwd()
  appExe = process.execPath

  // 确保目录在 CLI 模式下存在
  try {
    // eslint-disable-next-line @typescript-eslint/no-var-requires, @typescript-eslint/no-require-imports
    const fs = require('fs')
    if (!fs.existsSync(appUserData)) {
      fs.mkdirSync(appUserData, { recursive: true })
    }
  } catch (e) {
    console.warn('[Env] 创建用户数据目录失败:', e)
  }
}

export const isPackaged = isElectron ? getApp().isPackaged : process.env.NODE_ENV === 'production'
export const isDev = !isPackaged

export const paths = {
  userData: appUserData,
  app: appPath,
  exe: appExe,
  resources: isElectron ? process.resourcesPath : appPath, // CLI 的后备方案
  data: path.join(appUserData, 'data'),
  logs: path.join(appUserData, 'logs')
}

/**
 * Electron app 对象的安全包装器。
 * 如果未在 Electron 中运行，则返回 null。
 */
export function getApp() {
  if (isElectron) {
    // eslint-disable-next-line @typescript-eslint/no-var-requires, @typescript-eslint/no-require-imports
    return require('electron').app
  }
  return null
}

import { ipcRegistry } from './ipcRegistry'

/**
 * Electron ipcMain 的安全包装器。
 * 如果未在 Electron 中运行，则返回模拟对象或 null。
 */
export function getIpcMain() {
  if (isElectron) {
    // eslint-disable-next-line @typescript-eslint/no-var-requires, @typescript-eslint/no-require-imports
    return require('electron').ipcMain
  }
  // 连接到 CLI 模式的 IpcRegistry
  return {
    handle: (channel: string, listener: any) => {
      ipcRegistry.registerHandler(channel, listener)
    },
    on: (channel: string, listener: any) => {
      ipcRegistry.registerListener(channel, listener)
    },
    emit: (channel: string, ...args: any[]) => {
      ipcRegistry.emit(channel, ...args)
    },
    // 移除监听器存根
    removeListener: () => {},
    removeHandler: () => {}
  }
}
