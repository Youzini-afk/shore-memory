import steamworks from 'steamworks.js'
import { app } from 'electron'
import path from 'path'
import { getConfig, saveConfig } from './system.js'

let client: any = null
let isInitialized = false

// 成就常量
// 注意：请确保在 Steamworks 后台配置了对应的成就 ID
export const ACHIEVEMENTS = {
  FIRST_ENCOUNTER: 'FIRST_ENCOUNTER', // 初次见面
  WEEKLY_COMPANION: 'WEEKLY_COMPANION', // 每周伴侣
  MONTHLY_BESTIE: 'MONTHLY_BESTIE', // 月度闺蜜
  INTERACTION_MASTER: 'INTERACTION_MASTER' // 互动大师
}

// 返回值说明:
// 'restarting': 应用正在通过 Steam 重启（当前进程应退出）
// 'success': Steam 初始化成功
// 'failed': Steam 初始化失败（在没有 Steam 的情况下继续运行）
export function initSteam(): 'restarting' | 'success' | 'failed' {
  if (isInitialized) return 'success'

  const appId = 4457100 // PeroCore Steam App ID

  // 处理生产环境下的 Steam 重启逻辑
  // 如果应用不是通过 Steam 启动的，这将触发重启并返回 true
  if (app.isPackaged && steamworks.restartAppIfNecessary(appId)) {
    return 'restarting'
  }

  try {
    // 检查是否在 Docker 环境中运行
    if (process.env.DOCKER_ENV || process.env.IS_DOCKER) {
      console.log('[Steam] 检测到 Docker 环境，跳过 Steam 初始化。')
      return 'failed'
    }

    // 为 Electron 启用 Steam 覆盖层 (Overlay)
    // 必须在应用 ready 之前调用
    // 注意：Overlay 通常只会在第一个创建的窗口或者被标记为主窗口的上下文中生效
    // 在我们的架构中，我们希望它主要在 DashboardView 或 LauncherView 生效
    // Pet3DView 作为一个透明悬浮窗，如果被注入 Overlay 可能会有渲染问题
    steamworks.electronEnableSteamOverlay()

    // 初始化 Steamworks
    client = steamworks.init(appId)
    isInitialized = true

    console.log('[Steam] ============================================')
    console.log('[Steam] 初始化成功')
    console.log('[Steam] 当前用户:', client.localplayer.getName())
    console.log('[Steam] Steam ID:', client.localplayer.getSteamId().steamId64)
    console.log('[Steam] ============================================')

    // 检查 "初次见面" 成就
    checkFirstEncounter()

    return 'success'
  } catch (error) {
    // 忽略特定错误
    if (String(error).includes('already initialized')) {
      isInitialized = true
      return 'success'
    }
    console.warn('[Steam] ============================================')
    console.warn('[Steam] 初始化失败:', error)
    console.warn('[Steam] Steam 是否正在运行？steam_appid.txt 是否存在？')
    console.warn('[Steam] ============================================')
    return 'failed'
  }
}

export function getSteamClient() {
  return client
}

export function unlockAchievement(achievementName: string) {
  if (!client) return false
  try {
    const success = client.achievement.activate(achievementName)
    if (success) {
      console.log(`[Steam] 成就已解锁: ${achievementName}`)
    }
    return success
  } catch (error) {
    console.error(`[Steam] 解锁成就失败 ${achievementName}:`, error)
    return false
  }
}

export function getSteamUser() {
  if (!client) return null
  try {
    return {
      name: client.localplayer.getName(),
      steamId: client.localplayer.getSteamId().steamId64
    }
  } catch {
    return null
  }
}

function checkFirstEncounter() {
  if (!client) return

  try {
    const config = getConfig()
    // 确保 achievements 对象存在
    const achievements = config.steam_achievements || {}

    // 如果配置文件里没有记录，或者记录为 false，尝试解锁
    if (!achievements.first_encounter) {
      // 解锁成就
      // 注意：在 Spacewar 中，ACH_WIN_ONE_GAME 是一个可以重复触发的成就，但对于我们的逻辑来说，只在本地没记录时触发一次
      const success = unlockAchievement(ACHIEVEMENTS.FIRST_ENCOUNTER)

      if (success) {
        console.log('[Steam] 检测到首次运行！解锁“初次见面”成就。')

        // 更新本地配置
        const newConfig = {
          ...config,
          steam_achievements: {
            ...achievements,
            first_encounter: true
          }
        }
        saveConfig(newConfig)
      }
    }
  } catch (e) {
    console.warn('[Steam] 检查成就时出错:', e)
  }
}

// ==========================================
// Workshop (创意工坊)
// ==========================================

export function getSubscribedItems() {
  if (!client) return []
  try {
    return client.workshop.getSubscribedItems()
  } catch (e) {
    console.error('[Steam] 获取已订阅物品失败:', e)
    return []
  }
}

export function getItemState(itemId: number) {
  if (!client) return 0
  try {
    return client.workshop.state(itemId)
  } catch (e) {
    return 0
  }
}

export function getItemInstallInfo(itemId: number) {
  if (!client) return null
  try {
    return client.workshop.installInfo(itemId)
  } catch (e) {
    return null
  }
}

export function subscribeToItem(itemId: number) {
  if (!client) return
  try {
    client.workshop.subscribe(itemId)
  } catch (e) {
    console.error(`[Steam] 订阅物品失败 ${itemId}:`, e)
  }
}

export function unsubscribeFromItem(itemId: number) {
  if (!client) return
  try {
    client.workshop.unsubscribe(itemId)
  } catch (e) {
    console.error(`[Steam] 取消订阅物品失败 ${itemId}:`, e)
  }
}

export function downloadItem(itemId: number, highPriority = false) {
  if (!client) return
  try {
    client.workshop.download(itemId, highPriority)
  } catch (e) {
    console.error(`[Steam] 下载物品失败 ${itemId}:`, e)
  }
}

export function getWorkshopInstallPath(): string | null {
  if (!client) return null
  try {
    // 4457100 is PeroCore Steam App ID
    // appInstallDir usually returns path to .../steamapps/common/PeroCore
    const installDir = client.apps.appInstallDir(4457100)
    if (!installDir) return null

    // We assume the workshop content is in .../steamapps/workshop/content/4457100
    // This assumes the standard Steam library folder structure
    const steamAppsDir = path.dirname(path.dirname(installDir))
    const workshopDir = path.join(steamAppsDir, 'workshop', 'content', '4457100')
    return workshopDir
  } catch (e) {
    console.warn('[Steam] 获取 Workshop 安装路径失败:', e)
    return null
  }
}
