import { app } from 'electron'
import path from 'path'
import fs from 'fs'
import { getConfig, saveConfig } from './system.js'

let steamworks: any = null
try {
  // 安全检查：在加载 steamworks.js 之前，先检查 steam_api64.dll 是否存在
  // 如果 DLL 缺失，require() 可能在 native 层直接 segfault，连 try-catch 都拦不住
  const exeDir = path.dirname(process.execPath)
  const dllPath = path.join(exeDir, 'steam_api64.dll')
  const hasSteamDll = fs.existsSync(dllPath)

  if (!hasSteamDll && app.isPackaged) {
    // 生产环境下没有 Steam DLL，说明这是非 Steam 版本（如 GitHub Release）
    // 跳过加载 steamworks.js 以避免原生层崩溃
    console.log('[Steam] steam_api64.dll 未找到，跳过 Steamworks 加载 (非 Steam 版本)')
    steamworks = null
  } else {
    steamworks = require('steamworks.js')
  }
} catch (e) {
  console.error('[Steam] 无法加载 steamworks.js 模块 (可能缺少 steam_api64.dll):', e)
  steamworks = null
}

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
  if (!steamworks) return 'failed'

  const appId = 4457100 // PeroCore Steam App ID

  // 1. 检查是否显式禁用了 Steam
  if (process.env.PERO_DISABLE_STEAM || process.env.IS_DOCKER || process.env.DOCKER_ENV) {
    console.log('[Steam] Steam 已被禁用 (环境变量)')
    return 'failed'
  }

  // 2. 检查是否在生产环境中运行
  if (app.isPackaged) {
    // 智能检测是否为 Steam 构建：
    // - 检查安装路径中是否包含 'steamapps' (标准的 Steam 库路径)
    // - 检查是否存在 steam_appid.txt (开发环境或手动调试)
    const exePath = app.getPath('exe').toLowerCase()
    const isSteamLibraryPath = exePath.includes('steamapps')
    const hasAppIdFile =
      require('fs').existsSync(path.join(path.dirname(app.getPath('exe')), 'steam_appid.txt')) ||
      require('fs').existsSync(path.join(process.cwd(), 'steam_appid.txt'))

    // 如果不是在 Steam 库中，且没有 steam_appid.txt，我们推断这是一个非 Steam 版本（如 GitHub Release）
    // 此时我们绝对不应该触发 restartAppIfNecessary，否则会强行启动 Steam 并导致应用退出
    if (!isSteamLibraryPath && !hasAppIdFile) {
      console.log('[Steam] 检测为非 Steam 环境启动，跳过强制重启逻辑')
    } else {
      // 只有在确认为 Steam 环境时，才执行重启检查
      if (steamworks.restartAppIfNecessary(appId)) {
        console.log('[Steam] 应用未通过 Steam 启动，正在请求 Steam 重启...')
        return 'restarting'
      }
    }
  }

  try {
    // 为 Electron 启用 Steam 覆盖层 (Overlay)
    // 必须在应用 ready 之前调用
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
    console.warn('[Steam] Steam 是否正在运行？或当前用户未拥有此 AppID')
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
  } catch {
    return 0
  }
}

export function getItemInstallInfo(itemId: number) {
  if (!client) return null
  try {
    return client.workshop.installInfo(itemId)
  } catch {
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

// ==========================================
// Cloud Sync (云同步)
// ==========================================

/**
 * 检查 Steam 云是否为当前账户启用
 */
export function isCloudEnabledForAccount(): boolean {
  if (!client) return false
  try {
    return client.cloud.isEnabledForAccount()
  } catch (e) {
    console.error('[Steam] 检查云同步账户状态失败:', e)
    return false
  }
}

/**
 * 检查 Steam 云是否为当前应用启用
 */
export function isCloudEnabledForApp(): boolean {
  if (!client) return false
  try {
    return client.cloud.isEnabledForApp()
  } catch (e) {
    console.error('[Steam] 检查云同步应用状态失败:', e)
    return false
  }
}

/**
 * 读取云存储中的文件
 * @param name 文件名 (相对路径)
 * @returns 文件内容字符串，如果文件不存在则返回 null
 */
export function readCloudFile(name: string): string | null {
  if (!client) return null
  try {
    if (!client.cloud.fileExists(name)) {
      return null
    }
    return client.cloud.readFile(name)
  } catch (e) {
    console.error(`[Steam] 读取云文件失败 ${name}:`, e)
    return null
  }
}

/**
 * 写入文件到云存储
 * @param name 文件名 (相对路径)
 * @param content 文件内容字符串
 * @returns 是否写入成功
 */
export function writeCloudFile(name: string, content: string): boolean {
  if (!client) return false
  try {
    const success = client.cloud.writeFile(name, content)
    if (success) {
      console.log(`[Steam] 云文件写入成功: ${name}`)
    }
    return success
  } catch (e) {
    console.error(`[Steam] 写入云文件失败 ${name}:`, e)
    return false
  }
}

/**
 * 删除云存储中的文件
 * @param name 文件名 (相对路径)
 * @returns 是否删除成功
 */
export function deleteCloudFile(name: string): boolean {
  if (!client) return false
  try {
    return client.cloud.deleteFile(name)
  } catch (e) {
    console.error(`[Steam] 删除云文件失败 ${name}:`, e)
    return false
  }
}

/**
 * 检查云存储中是否存在文件
 * @param name 文件名 (相对路径)
 */
export function cloudFileExists(name: string): boolean {
  if (!client) return false
  try {
    return client.cloud.fileExists(name)
  } catch {
    return false
  }
}

/**
 * 列出云存储中的所有文件
 */
export function listCloudFiles(): Array<{ name: string; size: bigint }> {
  if (!client) return []
  try {
    const files = client.cloud.listFiles()
    return files.map((f: any) => ({ name: f.name, size: f.size }))
  } catch (e) {
    console.error('[Steam] 列出云文件失败:', e)
    return []
  }
}
