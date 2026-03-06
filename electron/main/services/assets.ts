import { protocol, net } from 'electron'
import { pathToFileURL } from 'url'
import { logger } from '../utils/logger'

export function registerAssetProtocol() {
  protocol.handle('asset', (request) => {
    let url = request.url.replace('asset://', '')

    // 处理 Windows 盘符 (例如 /C:/Users... -> C:/Users...)
    // 浏览器通常会把 asset://C:/... 变成 asset://c:/... (小写)
    // 或者 asset:///C:/... -> /C:/...

    // 如果 URL 以 / 开头，且是 Windows 盘符格式 (/C:/...), 去掉开头的 /
    if (process.platform === 'win32' && /^\/[a-zA-Z]:/.test(url)) {
      url = url.slice(1)
    }

    // 解码 URL (处理空格等特殊字符)
    const filePath = decodeURIComponent(url)

    logger.info('AssetProtocol', `Serving asset: ${filePath}`)

    try {
      return net.fetch(pathToFileURL(filePath).toString())
    } catch (error: any) {
      logger.error('AssetProtocol', `Failed to serve asset: ${filePath} - ${error.message}`)
      return new Response('Not Found', { status: 404 })
    }
  })
}
