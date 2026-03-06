import path from 'path'
import fs from 'fs-extra'
import { isDev, isElectron } from '../utils/env'
import { logger } from '../utils/logger'
import { app } from 'electron'

export interface ModelInfo {
  name: string
  path: string
  type: 'pero' | 'folder'
}

export async function scanLocalModels(): Promise<ModelInfo[]> {
  const models: ModelInfo[] = []

  // 确定模型目录路径
  // 开发环境: public/assets/3d
  // 生产环境: resources/app/dist/assets/3d (如果未解压) 或者 app.asar/dist/assets/3d
  // 但是 vite build 会把 public 下的内容放到 dist 下
  // 所以在 Electron 生产环境中，资源位于 app.getAppPath() + /dist/assets/3d

  let modelsDir = ''

  if (isDev) {
    const root = path.resolve(__dirname, '../../..')
    modelsDir = path.join(root, 'public/assets/3d')
  } else {
    // 生产环境
    if (isElectron) {
      modelsDir = path.join(app.getAppPath(), 'dist/assets/3d')
    } else {
      // 纯 Node 环境或其他
      modelsDir = path.join(process.cwd(), 'dist/assets/3d')
    }
  }

  logger.info('Main', `[Models] 正在扫描模型，路径: ${modelsDir}`)

  if (!(await fs.pathExists(modelsDir))) {
    logger.warn('Main', `[Models] 未找到模型目录: ${modelsDir}`)
    return []
  }

  try {
    const files = await fs.readdir(modelsDir)
    for (const file of files) {
      const fullPath = path.join(modelsDir, file)
      const stat = await fs.stat(fullPath)

      if (file.endsWith('.pero')) {
        models.push({
          name: file.replace('.pero', ''),
          path: `assets/3d/${file}`, // 返回相对路径供前端使用
          type: 'pero'
        })
      } else if (stat.isDirectory()) {
        // 检查文件夹内是否有 manifest.json 或 main.json
        // 或者是否是有效的模型文件夹
        const hasManifest = await fs.pathExists(path.join(fullPath, 'manifest.json'))
        const hasMainJson = await fs.pathExists(path.join(fullPath, 'models/main.json'))

        if (hasManifest || hasMainJson) {
          models.push({
            name: file,
            path: `assets/3d/${file}/manifest.json`, // 如果有 manifest 优先
            type: 'folder'
          })

          // 如果没有 manifest.json，可能需要构造一个虚拟路径或者由前端处理
          // 这里简单起见，如果有 manifest.json 就指向它，否则可能是一个标准文件夹结构，
          // 但 BedrockLoader 通常需要一个入口。
          // 如果是文件夹结构，通常我们会期望有一个 manifest.json。
          // 如果没有 manifest.json，我们可能无法直接加载，除非前端有逻辑处理。
          // 之前的代码似乎默认加载 assets/3d/Rossi/manifest.json 如果存在。
        }
      }
    }
  } catch (e) {
    logger.error('Main', `[Models] 扫描模型失败: ${e}`)
  }

  return models
}
