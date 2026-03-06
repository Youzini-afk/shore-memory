/**
 * 解析资产路径为可加载的 URL
 *
 * @param path 原始路径 (可能是相对路径 assets/..., 或绝对路径 C:/...)
 * @returns 可用于 fetch 或 img src 的 URL
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
    // Unix: /home/... -> asset:///home/...

    // 简单的绝对路径检测
    const isAbsolute = /^[a-zA-Z]:\\|^[a-zA-Z]:\/|^\//.test(path)

    if (isAbsolute) {
      // 规范化路径分隔符
      const normalizedPath = path.replace(/\\/g, '/')
      // 确保以 / 开头 (对于 Windows 盘符，如 C:/... 变成 /C:/...)
      const pathPart = normalizedPath.startsWith('/') ? normalizedPath : '/' + normalizedPath
      return `asset://${pathPart}`
    }
  }

  return path
}
