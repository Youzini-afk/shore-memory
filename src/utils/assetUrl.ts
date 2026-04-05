/**
 * 解析资产路径为可加载的 URL
 *
 * - 相对路径（如 assets/3d/...）：在 Electron 生产环境下，由于页面通过 loadFile() 加载，
 *   fetch() 会自动基于 file:///app.asar/dist/index.html 解析相对路径，
 *   Electron 对 file:// 协议透明支持 asar 内文件读取，故无需额外转换。
 * - 绝对路径（如 C:\...）：需要转为 asset:// 协议，交由主进程的 net.fetch() 处理。
 *
 * @param path 原始路径（相对路径 assets/..., 绝对路径 C:/..., 或已解析的协议 URL）
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
    const isAbsolute = /^[a-zA-Z]:\\|^[a-zA-Z]:\/|^\//.test(path)

    if (isAbsolute) {
      // 规范化路径分隔符
      const normalizedPath = path.replace(/\\/g, '/')
      // 确保以 / 开头 (对于 Windows 盘符，如 C:/... 变成 /C:/...)
      const pathPart = normalizedPath.startsWith('/')
        ? normalizedPath
        : '/' + normalizedPath
      return `asset://${pathPart}`
    }

    // 相对路径：直接返回原路径
    // Electron loadFile() 页面的 fetch() 会基于 file:///app.asar/dist/ 自动解析
  }

  return path
}
