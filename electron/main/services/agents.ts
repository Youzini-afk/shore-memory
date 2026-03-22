import path from 'path'
import fs from 'fs-extra'
import { isDev, isElectron, paths } from '../utils/env'
import { logger } from '../utils/logger'

function getRootPath() {
  if (isDev && isElectron) {
    // 开发环境: dist-electron/main/services -> ProjectRoot
    return path.resolve(__dirname, '../../..')
  } else {
    return paths.resources
  }
}

export async function scanLocalAgents() {
  const root = getRootPath()
  // 后端结构: backend/services/mdp/agents
  // 生产环境中，后端可能位于 resources/backend
  const backendAgentsDir = path.join(root, 'backend/services/mdp/agents')
  const globalConfigPath = path.join(root, 'backend/data/agent_launch_config.json')

  logger.info('Main', `[Agents] 正在扫描 Agents，路径: ${backendAgentsDir}`)
  logger.info('Main', `[Agents] 全局配置路径: ${globalConfigPath}`)

  if (!(await fs.pathExists(backendAgentsDir))) {
    logger.warn('Main', `[Agents] 未找到 Agents 目录: ${backendAgentsDir}`)
    return []
  }

  // 加载全局配置
  let globalConfig = { enabled_agents: [] as string[], active_agent: '' }
  try {
    if (await fs.pathExists(globalConfigPath)) {
      const loadedConfig = await fs.readJson(globalConfigPath)
      globalConfig = { ...globalConfig, ...loadedConfig }
      logger.info('Main', `[Agents] 已加载全局配置: ${JSON.stringify(globalConfig)}`)
    } else {
      logger.info('Main', '[Agents] 全局配置未找到，使用默认值')
    }
  } catch (e) {
    logger.warn('Main', `[Agents] 加载全局 Agent 配置失败: ${e}`)
  }

  const agents = []
  const files = await fs.readdir(backendAgentsDir)
  for (const file of files) {
    const agentDir = path.join(backendAgentsDir, file)
    try {
      const stat = await fs.stat(agentDir)
      if (stat.isDirectory()) {
        // 检查 config.json
        const configPath = path.join(agentDir, 'config.json')
        if (await fs.pathExists(configPath)) {
          try {
            const config = await fs.readJson(configPath)
            const id = file

            // 合并全局状态
            const isEnabled = globalConfig.enabled_agents.includes(id)
            const isActive = globalConfig.active_agent === id

            // 扫描头像
            let avatar = ''
            const avatarFiles = [
              'avatar.png',
              'avatar.jpg',
              'avatar.jpeg',
              'avatar.svg',
              'icon.png'
            ]
            const mimeMap: Record<string, string> = {
              '.png': 'image/png',
              '.jpg': 'image/jpeg',
              '.jpeg': 'image/jpeg',
              '.svg': 'image/svg+xml'
            }
            for (const name of avatarFiles) {
              const avatarPath = path.join(agentDir, name)
              if (await fs.pathExists(avatarPath)) {
                // 直接将文件读取为 base64 data URL，无需后端服务即可显示
                try {
                  const ext = path.extname(name).toLowerCase()
                  const mime = mimeMap[ext] || 'image/png'
                  const buf = await fs.readFile(avatarPath)
                  avatar = `data:${mime};base64,${buf.toString('base64')}`
                } catch {
                  // 回退到后端 API 路径
                  avatar = `/api/agents/${id}/avatar`
                }
                break
              }
            }

            agents.push({
              id: id,
              name: config.name || id,
              description: config.description || '',
              avatar: avatar || config.avatar || '',
              path: agentDir,
              is_enabled: isEnabled,
              is_active: isActive,
              ...config
            })
          } catch (e) {
            logger.error('Main', `无法读取 ${file} 的配置: ${e}`)
            agents.push({ id: file, name: file, description: '配置错误' })
          }
        }
      }
    } catch {
      // 忽略访问错误
    }
  }
  return agents
}

export async function getPlugins() {
  const root = getRootPath()
  // 后端结构: backend/nit_core/plugins
  const pluginsDir = path.join(root, 'backend/nit_core/plugins')

  logger.info('Plugin', `[插件] 正在扫描插件，路径: ${pluginsDir}`)

  if (!(await fs.pathExists(pluginsDir))) {
    logger.warn('Plugin', `[插件] 未找到目录: ${pluginsDir}`)
    return []
  }

  const plugins = []
  try {
    const files = await fs.readdir(pluginsDir)
    logger.info('Plugin', `[插件] 发现文件: ${files.join(', ')}`)

    for (const file of files) {
      // 跳过隐藏/缓存文件
      if (file.startsWith('__') || file.startsWith('.')) {
        continue
      }

      const pluginDir = path.join(pluginsDir, file)
      try {
        const stat = await fs.stat(pluginDir)
        if (stat.isDirectory()) {
          // 检查 description.json
          const descPath = path.join(pluginDir, 'description.json')
          if (await fs.pathExists(descPath)) {
            try {
              const desc = await fs.readJson(descPath)
              plugins.push({
                name: file,
                valid: true,
                ...desc
              })
              logger.info('Plugin', `[插件] 已加载 ${file}`)
            } catch (e) {
              logger.error('Plugin', `[插件] 解析 ${file} 的 description.json 失败: ${e}`)
              plugins.push({ name: file, valid: false, description: '无效配置' })
            }
          } else {
            // 猜测或列出
            logger.info('Plugin', `[插件] ${file} 缺少 description.json`)
            plugins.push({ name: file, valid: true, description: '自定义插件' })
          }
        }
      } catch (e) {
        logger.error('Plugin', `[插件] 处理 ${file} 时出错: ${e}`)
      }
    }
  } catch (e) {
    logger.error('Plugin', `[插件] 读取插件目录失败: ${e}`)
  }

  logger.info('Plugin', `[插件] 返回了 ${plugins.length} 个插件`)
  return plugins
}

export async function saveGlobalLaunchConfig(enabledAgents: string[], activeAgent: string) {
  const root = getRootPath()
  const dataDir = path.join(root, 'backend/data')
  const configPath = path.join(dataDir, 'agent_launch_config.json')

  logger.info('Main', `[Config] 正在保存全局配置到 ${configPath}`)
  logger.info('Main', `[Config] 数据: ${JSON.stringify({ enabledAgents, activeAgent })}`)

  try {
    await fs.ensureDir(dataDir)

    const config = {
      enabled_agents: enabledAgents,
      active_agent: activeAgent
    }

    await fs.writeJson(configPath, config, { spaces: 4 })
    logger.info('Main', `[Config] 保存成功`)
    return config
  } catch (e) {
    logger.error('Main', `[Config] 保存全局配置失败: ${e}`)
    throw e
  }
}

export async function saveAgentLaunchConfig(agentId: string, config: any) {
  const root = getRootPath()
  const backendAgentsDir = path.join(root, 'backend/services/mdp/agents')
  const agentDir = path.join(backendAgentsDir, agentId)
  const configPath = path.join(agentDir, 'config.json')

  if (!(await fs.pathExists(configPath))) {
    throw new Error(`未找到 Agent 配置: ${configPath}`)
  }

  // 合并现有配置和新配置
  const current = await fs.readJson(configPath)
  const newConfig = { ...current, ...config }
  await fs.writeJson(configPath, newConfig, { spaces: 4 })
  return newConfig
}
