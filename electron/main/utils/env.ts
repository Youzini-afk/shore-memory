import path from 'path'
import os from 'os'

export const isElectron = !!process.versions.electron

let appUserData: string
let appPath: string
let appExe: string

if (isElectron) {
    // Dynamic require to avoid issues when running in pure Node.js
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    const { app } = require('electron')
    appUserData = app.getPath('userData')
    appPath = app.getAppPath()
    appExe = app.getPath('exe')
} else {
    // CLI / Docker Environment
    const HOME = os.homedir()
    // Default to ~/.perocore or respect env var
    appUserData = process.env.PERO_USER_DATA || path.join(HOME, '.perocore')
    appPath = process.cwd()
    appExe = process.execPath
    
    // Ensure the directory exists in CLI mode
    try {
        const fs = require('fs')
        if (!fs.existsSync(appUserData)) {
            fs.mkdirSync(appUserData, { recursive: true })
        }
    } catch (e) {
        console.warn('[Env] 创建用户数据目录失败:', e)
    }
}

export const isPackaged = isElectron ? getApp().isPackaged : (process.env.NODE_ENV === 'production')
export const isDev = !isPackaged

export const paths = {
    userData: appUserData,
    app: appPath,
    exe: appExe,
    resources: isElectron ? process.resourcesPath : appPath, // Fallback for CLI
    data: path.join(appUserData, 'data'),
    logs: path.join(appUserData, 'logs')
}

/**
 * Safe wrapper for Electron's app object.
 * Returns null if not running in Electron.
 */
export function getApp() {
    if (isElectron) {
        // eslint-disable-next-line @typescript-eslint/no-var-requires
        return require('electron').app
    }
    return null
}

import { ipcRegistry } from './ipcRegistry'

/**
 * Safe wrapper for Electron's ipcMain.
 * Returns a mock or null if not running in Electron.
 */
export function getIpcMain() {
    if (isElectron) {
        // eslint-disable-next-line @typescript-eslint/no-var-requires
        return require('electron').ipcMain
    }
    // Connected to IpcRegistry for CLI mode
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
        // Remove listener stubs
        removeListener: () => {},
        removeHandler: () => {}
    }
}
