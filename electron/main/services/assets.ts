import { protocol, net } from 'electron'
import { pathToFileURL } from 'url'
import path from 'path'
import fs from 'fs-extra'
import { logger } from '../utils/logger'
import { isDev, paths } from '../utils/env'
import { getWorkshopInstallPath } from './steam'

export interface AssetInfo {
  asset_id: string
  type: string
  source: 'official' | 'local' | 'workshop'
  display_name: string
  version: string
  path: string
  workshop_id?: string
  config?: any
}

function getRootPath() {
  if (isDev) {
    return path.resolve(__dirname, '../../..')
  } else {
    return paths.resources
  }
}

/**
 * 扫描 3D 模型资产
 * 包括内置模型和 Workshop 模型
 */
export async function scan3DModels(): Promise<AssetInfo[]> {
  const models: AssetInfo[] = []
  const root = getRootPath()

  // 1. 扫描内置模型 (public/assets/3d)
  const officialModelsDir = path.join(root, 'public/assets/3d')
  if (await fs.pathExists(officialModelsDir)) {
    const dirs = await fs.readdir(officialModelsDir)
    for (const dir of dirs) {
      const modelDir = path.join(officialModelsDir, dir)
      const stat = await fs.stat(modelDir).catch(() => null)
      if (stat?.isDirectory()) {
        // 检查 manifest.json 或 .pero 文件
        const manifestPath = path.join(modelDir, 'manifest.json')
        const peroPath = path.join(modelDir, `${dir}.pero`)

        if (await fs.pathExists(manifestPath)) {
          try {
            const manifest = await fs.readJson(manifestPath)
            models.push({
              asset_id: manifest.asset_id || `com.perocore.model.${dir.toLowerCase()}`,
              type: 'model_3d',
              source: 'official',
              display_name: manifest.display_name || manifest.metadata?.name || dir,
              version: manifest.version || '1.0.0',
              path: modelDir,
              config: manifest
            })
          } catch {
            logger.warn('Assets', `解析内置模型清单失败: ${manifestPath}`)
          }
        } else if (await fs.pathExists(peroPath)) {
          models.push({
            asset_id: `com.perocore.model.${dir.toLowerCase()}`,
            type: 'model_3d',
            source: 'official',
            display_name: dir,
            version: '1.0.0',
            path: peroPath
          })
        }
      }
    }
  }

  // 2. 扫描 .pero 文件 (根目录下的)
  const peroFiles = await fs.readdir(officialModelsDir).catch(() => [])
  for (const file of peroFiles) {
    if (file.endsWith('.pero')) {
      const name = file.replace('.pero', '')
      const filePath = path.join(officialModelsDir, file)
      // 避免重复添加
      if (!models.find((m) => m.path === filePath)) {
        models.push({
          asset_id: `com.perocore.model.${name.toLowerCase()}`,
          type: 'model_3d',
          source: 'official',
          display_name: name,
          version: '1.0.0',
          path: filePath
        })
      }
    }
  }

  // 3. 扫描 Workshop 模型
  const workshopPath = getWorkshopInstallPath()
  if (workshopPath && (await fs.pathExists(workshopPath))) {
    try {
      const workshopDirs = await fs.readdir(workshopPath)
      for (const workshopId of workshopDirs) {
        const itemDir = path.join(workshopPath, workshopId)
        const stat = await fs.stat(itemDir).catch(() => null)
        if (stat?.isDirectory()) {
          // 查找 .pero 或 manifest.json
          const files = await fs.readdir(itemDir)
          for (const file of files) {
            if (file.endsWith('.pero')) {
              const name = file.replace('.pero', '')
              models.push({
                asset_id: `com.workshop.model.${workshopId}`,
                type: 'model_3d',
                source: 'workshop',
                display_name: name,
                version: '1.0.0',
                path: path.join(itemDir, file),
                workshop_id: workshopId
              })
            }
          }
          // 检查 manifest.json
          const manifestPath = path.join(itemDir, 'manifest.json')
          if (await fs.pathExists(manifestPath)) {
            try {
              const manifest = await fs.readJson(manifestPath)
              if (!models.find((m) => m.workshop_id === workshopId)) {
                models.push({
                  asset_id: manifest.asset_id || `com.workshop.model.${workshopId}`,
                  type: 'model_3d',
                  source: 'workshop',
                  display_name: manifest.display_name || `Workshop ${workshopId}`,
                  version: manifest.version || '1.0.0',
                  path: itemDir,
                  workshop_id: workshopId,
                  config: manifest
                })
              }
            } catch {
              logger.warn('Assets', `解析创意工坊清单失败: ${manifestPath}`)
            }
          }
        }
      }
    } catch (e) {
      logger.warn('Assets', `扫描创意工坊目录失败: ${e}`)
    }
  }

  // 4. 扫描用户自定义模型 (@data/custom/models)
  const customModelsDir = path.join(paths.data, 'custom/models')
  if (await fs.pathExists(customModelsDir)) {
    const dirs = await fs.readdir(customModelsDir)
    for (const dir of dirs) {
      const modelDir = path.join(customModelsDir, dir)
      const stat = await fs.stat(modelDir).catch(() => null)
      if (stat?.isDirectory()) {
        const manifestPath = path.join(modelDir, 'manifest.json')
        if (await fs.pathExists(manifestPath)) {
          try {
            const manifest = await fs.readJson(manifestPath)
            models.push({
              asset_id: manifest.asset_id || `com.local.model.${dir.toLowerCase()}`,
              type: 'model_3d',
              source: 'local',
              display_name: manifest.display_name || dir,
              version: manifest.version || '1.0.0',
              path: modelDir,
              config: manifest
            })
          } catch {
            logger.warn('Assets', `解析自定义模型清单失败: ${manifestPath}`)
          }
        }
      }
    }
  }

  logger.info('Assets', `扫描到 ${models.length} 个 3D 模型`)
  return models
}

/**
 * 获取模型的可加载路径
 * 返回可直接用于 BedrockAvatar 的路径
 */
export function getModelLoadPath(model: AssetInfo): string {
  // 如果是 .pero 文件，直接返回路径
  if (model.path.endsWith('.pero')) {
    return model.path
  }
  // 否则查找目录下的 .pero 文件
  const peroFile = path.join(model.path, path.basename(model.path) + '.pero')
  if (fs.existsSync(peroFile)) {
    return peroFile
  }
  // 查找 manifest.json
  const manifestPath = path.join(model.path, 'manifest.json')
  if (fs.existsSync(manifestPath)) {
    return manifestPath
  }
  // 返回目录路径
  return model.path
}

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

    logger.info('AssetProtocol', `正在提供资源: ${filePath}`)

    try {
      return net.fetch(pathToFileURL(filePath).toString())
    } catch (error: any) {
      logger.error('AssetProtocol', `提供资源失败: ${filePath} - ${error.message}`)
      return new Response('未找到资源', { status: 404 })
    }
  })
}
