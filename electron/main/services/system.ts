import { paths } from '../utils/env'
import si from 'systeminformation'
import fs from 'fs-extra'
import path from 'path'

export interface SystemStats {
  cpu_usage: number
  memory_used: number
  memory_total: number
}

// 缓存 CPU 负载 (定期更新以降低开销)
let lastCpuLoad = 0

setInterval(async () => {
  try {
    const load = await si.currentLoad()
    lastCpuLoad = load.currentLoad
  } catch {
    // 忽略
  }
}, 5000)

export async function getSystemStats(): Promise<SystemStats> {
  try {
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
  // 开发环境路径
  const devPath = path.join(process.cwd(), 'data/gateway_token.json')
  // 生产环境路径 (在 exe 旁边或 userData 中)
  const prodPath = path.join(paths.userData, 'data/gateway_token.json')

  // 首先检查 ENV (如果由 startGateway 在同一进程中设置，但此处不太可能)
  if (process.env.GATEWAY_TOKEN_PATH && fs.existsSync(process.env.GATEWAY_TOKEN_PATH)) {
    try {
      const data = fs.readJsonSync(process.env.GATEWAY_TOKEN_PATH)
      return data.token || ''
    } catch {
      // 忽略
    }
  }

  const tokenPath = fs.existsSync(devPath) ? devPath : prodPath

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
