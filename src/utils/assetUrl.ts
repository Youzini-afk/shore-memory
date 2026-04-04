/**
 * 解析资产路径为可加载的 URL
 *
 * @param path 原始路径 (可能是相对路径 assets/..., 或绝对路径 C:/...，或已解析的 URL)
 * @returns 可用于 fetch 或 img src 的 URL
 */

// 缓存 appPath，避免每次都发起 IPC 调用
let _cachedAppPath: string | null = null

async function getAppPath(): Promise<string> {
  if (_cachedAppPath) return _cachedAppPath
  try {
    // @ts-ignore
    const p = await window.electron.appPath()
    _cachedAppPath = p
    return p
  } catch {
    return ''
  }
}

/**
 * 同步版本（用于已缓存或非 Electron 场景）
 * 注意：在 Electron 下首次调用前需先调用 initAssetUrlCache() 预热
 */
export function resolveAssetUrl(path: string): string {
  if (!path) return path

  // 如果已经是 http/https/asset/data 协议，直接返回
  if (/^(http|https|asset|data):/.test(path)) {
    return path
  }

  // 检查是否在 Electron 环境
  const isElectron = (window as any).electron !== undefined

  if (isElectron) {
    // 如果是绝对路径 (Windows 盘符或 Unix 根路径)
    // Windows: C:\... -> asset://C:/...
    const isAbsolute = /^[a-zA-Z]:\\|^[a-zA-Z]:\/|^\//.test(path)

    if (isAbsolute) {
      const normalizedPath = path.replace(/\\/g, '/')
      const pathPart = normalizedPath.startsWith('/') ? normalizedPath : '/' + normalizedPath
      return `asset://${pathPart}`
    }

    // [修复] 相对路径 (如 assets/3d/Pero.pero) 在 Electron Portable 下走 file:// 会失败，
    // 因为 fetch 的基准 URL 是 dist/index.html 所在目录，而非 asar 根目录。
    // 需要将其转为 asset:// 绝对路径，基于已缓存的 appPath。
    if (_cachedAppPath) {
      const normalizedAppPath = _cachedAppPath.replace(/\\/g, '/')
      const appPathPart = normalizedAppPath.startsWith('/') ? normalizedAppPath : '/' + normalizedAppPath
      return `asset://${appPathPart}/${path}`
    }

    // appPath 尚未缓存（首帧可能发生），降级保底返回原路径
    console.warn(`[resolveAssetUrl] appPath 未缓存，无法解析相对路径: ${path}`)
  }

  return path
}

/**
 * 在 Electron 环境下，应在应用初始化时调用此函数预热 appPath 缓存，
 * 确保 resolveAssetUrl 同步版本能正确处理相对路径。
 */
export async function initAssetUrlCache(): Promise<void> {
  const isElectron = (window as any).electron !== undefined
  if (isElectron && !_cachedAppPath) {
    await getAppPath()
  }
}
