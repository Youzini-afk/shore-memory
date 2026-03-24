import { paths } from '../utils/env'
import fs from 'fs-extra'
import path from 'path'

/**
 * systeminformation 延迟加载。
 * 该模块含有 native 绑定，如果在 ASAR 打包后加载失败，
 * 不应影响整个应用启动。因此改为在第一次使用时才 require()。
 */
let _si: typeof import('systeminformation') | null = null
let _siLoadFailed = false

function getSI(): typeof import('systeminformation') | null {
  if (_si) return _si
  if (_siLoadFailed) return null
  try {
    _si = require('systeminformation')
    return _si
  } catch (e) {
    _siLoadFailed = true
    console.error('[System] systeminformation 模块加载失败，系统监控功能将不可用:', e)
    return null
  }
}

export interface SystemStats {
  cpu_usage: number
  memory_used: number
  memory_total: number
}

// 缓存 CPU 负载 (定期更新以降低开销)
let lastCpuLoad = 0
let cpuMonitorStarted = false

function ensureCpuMonitor() {
  if (cpuMonitorStarted) return
  cpuMonitorStarted = true
  const si = getSI()
  if (!si) return
  setInterval(async () => {
    try {
      const load = await si.currentLoad()
      lastCpuLoad = load.currentLoad
    } catch {
      // 忽略
    }
  }, 5000)
}

export async function getSystemStats(): Promise<SystemStats> {
  ensureCpuMonitor()
  try {
    const si = getSI()
    if (!si) return { cpu_usage: 0, memory_used: 0, memory_total: 0 }
    const mem = await si.mem()
    return {
      cpu_usage: parseFloat(lastCpuLoad.toFixed(1)),
      memory_used: mem.active,
      memory_total: mem.total
    }
  } catch {
    return { cpu_usage: 0, memory_used: 0, memory_total: 0 }
  }
}

export function getBackendLogs(): string[] {
  // 目前返回空 (待办: 实现日志存储)
  return []
}

export function getConfig(): any {
  const configPath = path.join(paths.userData, 'data/config.json')
  let config: any = {}

  if (fs.existsSync(configPath)) {
    try {
      config = fs.readJsonSync(configPath)
    } catch {
      config = {}
    }
  }

  // [引导逻辑] 确保默认值存在喵~ 🌸
  // 引导状态：false (新用户) -> 'launcher_done' (Launcher引导结束) -> true (全部引导结束)
  if (config.onboarding_completed === undefined) {
    config.onboarding_completed = false
  }
  if (config.eula_accepted === undefined) {
    config.eula_accepted = false
  }

  return config
}

export function saveConfig(config: any) {
  // 将配置保存到文件
  const dataDir = path.join(paths.userData, 'data')
  fs.ensureDirSync(dataDir)
  fs.writeJsonSync(path.join(dataDir, 'config.json'), config, { spaces: 2 })
}

export function getGatewayToken(): string {
  const tokenPath = path.join(paths.data, 'gateway_token.json')

  // 首先检查 ENV (如果由 startGateway 在同一进程中设置)
  if (process.env.GATEWAY_TOKEN_PATH && fs.existsSync(process.env.GATEWAY_TOKEN_PATH)) {
    try {
      const data = fs.readJsonSync(process.env.GATEWAY_TOKEN_PATH)
      return data.token || ''
    } catch {
      // 忽略
    }
  }

  if (fs.existsSync(tokenPath)) {
    try {
      const data = fs.readJsonSync(tokenPath)
      return data.token || ''
    } catch {
      return ''
    }
  }
  return ''
}
