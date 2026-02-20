import steamworks from 'steamworks.js'
import { app } from 'electron'
import { getConfig, saveConfig } from './system.js'

let client: any = null

// 成就常量
// 使用 Spacewar (AppID 480) 进行测试，将我们的成就映射到现有成就上
export const ACHIEVEMENTS = {
  FIRST_ENCOUNTER: 'ACH_WIN_ONE_GAME', // 将 "初次见面" 映射到 "Win One Game"
  WEEKLY_COMPANION: 'ACH_TRAVEL_FAR_ACCUM', // 将 "每周伴侣" 映射到 "Travel Far Accum"
  MONTHLY_BESTIE: 'ACH_TRAVEL_FAR_SINGLE', // 将 "月度闺蜜" 映射到 "Travel Far Single"
  INTERACTION_MASTER: 'ACH_WIN_100_GAMES' // 将 "互动大师" 映射到 "Win 100 Games"
}

// 返回值说明:
// 'restarting': 应用正在通过 Steam 重启（当前进程应退出）
// 'success': Steam 初始化成功
// 'failed': Steam 初始化失败（在没有 Steam 的情况下继续运行）
export function initSteam(): 'restarting' | 'success' | 'failed' {
  const appId = 480 // 测试用 Spacewar ID。请替换为你的 Steam App ID。

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
