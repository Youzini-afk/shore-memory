/**
 * 解析资产路径为可加载的 URL
 *
 * 在 Electron 生产模式下，渲染进程的 fetch() 无法直接访问 asar 内的文件，
 * 必须通过自定义 asset:// 协议转发给主进程的 net.fetch() 来读取。
 * 静态资源（public/ 目录内容）在构建后位于 app.asar/dist/ 下，
 * 因此需要在路径中插入 dist/ 段。
 *
 * @param path 原始路径（相对路径 assets/..., 绝对路径 C:/..., 或已解析的协议 URL）
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
    // Windows: C:\... -> asset:///C:/...
    const isAbsolute = /^[a-zA-Z]:\\|^[a-zA-Z]:\/|^\//.test(path)

    if (isAbsolute) {
      const normalizedPath = path.replace(/\\/g, '/')
      const pathPart = normalizedPath.startsWith('/')
        ? normalizedPath
        : '/' + normalizedPath
      return `asset://${pathPart}`
    }

    // [修复] 相对路径 (如 assets/3d/Pero/models/main.json)
    // 开发模式下：Vite Dev Server 通过 HTTP 自动处理 public/ 目录，直接返回原路径即可
    // 生产模式下：文件在 app.asar/dist/ 内，需要通过 asset:// 协议 + 完整绝对路径访问
    const isDev = !!(import.meta as any).env?.DEV
    if (!isDev && _cachedAppPath) {
      const normalizedAppPath = _cachedAppPath.replace(/\\/g, '/')
      const appPathPart = normalizedAppPath.startsWith('/')
        ? normalizedAppPath
        : '/' + normalizedAppPath
      // 关键：静态资源在 Vite 构建后位于 dist/ 目录下
      return `asset://${appPathPart}/dist/${path}`
    }
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
    console.log(`[resolveAssetUrl] appPath 已缓存: ${_cachedAppPath}`)
  }
}
