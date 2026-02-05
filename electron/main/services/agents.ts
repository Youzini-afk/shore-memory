import path from 'path'
import fs from 'fs-extra'
import { isDev, isElectron, paths } from '../utils/env'
import { logger } from '../utils/logger'

function getRootPath() {
    if (isDev && isElectron) {
        // Dev: dist-electron/main/services -> PeroCore-Electron
        // 开发环境: dist-electron/main/services -> PeroCore-Electron
        return path.resolve(__dirname, '../../..')
    } else {
        return paths.resources
    }
}

export async function scanLocalAgents() {
    const root = getRootPath()
    // Backend structure: backend/services/mdp/agents
    // In prod, backend is likely in resources/backend
    // 后端结构: backend/services/mdp/agents
    // 生产环境中，后端可能位于 resources/backend
    const backendAgentsDir = path.join(root, 'backend/services/mdp/agents')
    const globalConfigPath = path.join(root, 'backend/data/agent_launch_config.json')
    
    logger.info('Main', `[Agents] 正在扫描 Agents，路径: ${backendAgentsDir}`)
    logger.info('Main', `[Agents] 全局配置路径: ${globalConfigPath}`)

    if (!await fs.pathExists(backendAgentsDir)) {
        logger.warn('Main', `[Agents] 未找到 Agents 目录: ${backendAgentsDir}`)
        return []
    }
    
    // Load global config
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
                // Check for config.json
                // 检查 config.json
                const configPath = path.join(agentDir, 'config.json')
                if (await fs.pathExists(configPath)) {
                    try {
                        const config = await fs.readJson(configPath)
                        const id = file
                        
                        // Merge with global status
                        // 合并全局状态
                        const isEnabled = globalConfig.enabled_agents.includes(id)
                        const isActive = globalConfig.active_agent === id
                        
                        agents.push({
                            id: id,
                            name: config.name || id,
                            description: config.description || '',
                            avatar: config.avatar || '',
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
        } catch (e) {
            // Ignore access errors
            // 忽略访问错误
        }
    }
    return agents
}

export async function getPlugins() {
    const root = getRootPath()
    // Backend structure: backend/nit_core/plugins
    // 后端结构: backend/nit_core/plugins
    const pluginsDir = path.join(root, 'backend/nit_core/plugins')
    
    logger.info('Plugin', `[插件] 正在扫描插件，路径: ${pluginsDir}`)

    if (!await fs.pathExists(pluginsDir)) {
        logger.warn('Plugin', `[Plugins] Directory not found: ${pluginsDir}`)
        return []
    }
    
    const plugins = []
    try {
        const files = await fs.readdir(pluginsDir)
        logger.info('Plugin', `[Plugins] Files found: ${files.join(', ')}`)
        
        for (const file of files) {
            // Skip hidden/cache files
            // 跳过隐藏/缓存文件
            if (file.startsWith('__') || file.startsWith('.')) {
                continue
            }
            
            const pluginDir = path.join(pluginsDir, file)
            try {
                const stat = await fs.stat(pluginDir)
                if (stat.isDirectory()) {
                     // Check description.json
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
                            logger.info('Plugin', `[Plugins] Loaded ${file}`)
                        } catch (e) {
                            logger.error('Plugin', `[Plugins] Failed to parse description.json for ${file}: ${e}`)
                            plugins.push({ name: file, valid: false, description: "Invalid config" })
                        }
                    } else {
                        // Guess or list
                        // 猜测或列出
                        logger.info('Plugin', `[Plugins] ${file} missing description.json`)
                        plugins.push({ name: file, valid: true, description: "Custom Plugin" })
                    }
                }
            } catch (e) {
                logger.error('Plugin', `[Plugins] Error processing ${file}: ${e}`)
            }
        }
    } catch (e) {
        logger.error('Plugin', `[Plugins] Failed to read plugins dir: ${e}`)
    }
    
    logger.info('Plugin', `[Plugins] Returned ${plugins.length} plugins`)
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

    if (!await fs.pathExists(configPath)) {
        throw new Error(`Agent config not found: ${configPath}`)
    }

    // Merge existing with new
    // 合并现有配置和新配置
    const current = await fs.readJson(configPath)
    const newConfig = { ...current, ...config }
    await fs.writeJson(configPath, newConfig, { spaces: 4 })
    return newConfig
}
