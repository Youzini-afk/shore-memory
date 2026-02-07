import { spawn, ChildProcess } from 'child_process'
import path from 'path'
import fs from 'fs-extra'
import { isPackaged, paths } from '../utils/env'
import { WindowLike } from '../types'
import { logger } from '../utils/logger'

let gatewayProcess: ChildProcess | null = null
const logHistory: string[] = []
const MAX_LOGS = 1000

export function getGatewayLogs() {
    return [...logHistory]
}

export async function startGateway(window: WindowLike) {
    if (gatewayProcess) {
        return
    }

    let gatewayPath = ''
    const isWin = process.platform === 'win32'
    const execName = isWin ? 'gateway.exe' : 'gateway'
    
    if (isPackaged) {
        // Production: resources/bin/gateway(.exe)
        gatewayPath = path.join(paths.resources, 'bin', execName)
    } else {
        // Development: 优先查找 ../PeroLink/gateway(.exe)
        // process.cwd() 通常是项目根目录 (PeroCore-Electron)
        
        // Priority 1: ../PeroLink/gateway.exe
        const path1 = path.join(process.cwd(), '../PeroLink', execName)
        // Priority 2: ./gateway/gateway.exe
        const path2 = path.join(process.cwd(), 'gateway', execName)
        
        if (await fs.pathExists(path1)) {
            gatewayPath = path1
        } else if (await fs.pathExists(path2)) {
            gatewayPath = path2
        } else {
             gatewayPath = path1 // 默认回退
        }
    }

    // Check if gateway exists
    if (!(await fs.pathExists(gatewayPath))) {
        // Dev Fallback: 尝试在其他常见位置查找
        const altPaths = [
            path.join(__dirname, '../../../../PeroLink', execName),
            path.join(__dirname, '../../../../PeroCore-Electron/gateway', execName),
             path.join(process.cwd(), 'gateway', execName)
        ]
        
        let found = false
        for (const p of altPaths) {
            if (await fs.pathExists(p)) {
                gatewayPath = p
                found = true
                break
            }
        }
        
        if (!found) {
            const error = `Gateway 可执行文件未找到: ${gatewayPath}`
            logger.error('Gateway', error)
            try { if (!window.isDestroyed()) window.webContents.send('system-error', error) } catch(e){}
            throw new Error(error)
        }
    }

    logger.info('Gateway', `正在从以下路径启动 Gateway: ${gatewayPath}`)

    // Define token path explicitly to ensure consistency
    const tokenPath = isPackaged 
        ? path.join(paths.userData, 'data/gateway_token.json')
        : path.join(process.cwd(), 'data/gateway_token.json')

    // Ensure directory exists
    await fs.ensureDir(path.dirname(tokenPath))

    // 删除旧的令牌文件防止读取过时数据
    try {
        if (await fs.pathExists(tokenPath)) {
            await fs.remove(tokenPath)
        }
    } catch (e) {
        logger.warn('Gateway', `Failed to remove old token file: ${e}`)
    }
    logger.info('Gateway', `Gateway Token Path: ${tokenPath}`)

    // Spawn Gateway
    gatewayProcess = spawn(gatewayPath, [], {
        stdio: ['ignore', 'pipe', 'pipe'],
        detached: false,
        windowsHide: true,
        env: {
            ...process.env,
            GATEWAY_TOKEN_PATH: tokenPath
        }
    })

    // Wait for token file to be created
    let retries = 0
    let tokenCreated = false
    while (retries < 50) { // Wait up to 5 seconds
        if (await fs.pathExists(tokenPath)) {
            // Give it a tiny bit more time to ensure write is complete
            await new Promise(r => setTimeout(r, 100))
            tokenCreated = true
            break
        }
        await new Promise(r => setTimeout(r, 100))
        retries++
    }

    if (!tokenCreated) {
        const error = `Gateway 启动超时或失败: 无法生成令牌文件 (${tokenPath})`
        logger.error('Gateway', error)
        // Check if process exited
        if (gatewayProcess.exitCode !== null) {
            logger.error('Gateway', `Gateway process exited with code ${gatewayProcess.exitCode}`)
        }
        throw new Error(error)
    }

    gatewayProcess.stdout?.on('data', (data) => {
        const lines = data.toString().split('\n')
        lines.forEach((line: string) => {
            const trimmed = line.trim()
            if (!trimmed) return
            
            logger.info('Gateway', trimmed)
            // Optional: send to frontend if needed
            // window.webContents.send('gateway-log', line)
            
            if (logHistory.length >= MAX_LOGS) logHistory.shift()
            logHistory.push(trimmed)
        })
    })

    gatewayProcess.stderr?.on('data', (data) => {
        const lines = data.toString().split('\n')
        lines.forEach((line: string) => {
            const trimmed = line.trim()
            if (!trimmed) return

            // Go log.Println outputs to stderr by default. We need to distinguish actual errors from logs.
            // Heuristic: Check for common error keywords.
            const lowerLine = trimmed.toLowerCase()
            const isError = lowerLine.includes('error') || 
                           lowerLine.includes('panic') || 
                           lowerLine.includes('fail') || 
                           lowerLine.includes('fatal') ||
                           lowerLine.includes('exception') ||
                           lowerLine.includes('invalid') // Token errors often have 'invalid'

            if (isError) {
                logger.error('Gateway', trimmed)
            } else {
                logger.info('Gateway', trimmed)
            }
            
            if (logHistory.length >= MAX_LOGS) logHistory.shift()
            logHistory.push(trimmed)
        })
    })

    gatewayProcess.on('close', (code) => {
        logger.info('Gateway', `Gateway 已退出，退出码: ${code}`)
        gatewayProcess = null
    })
    
    // Give it a moment to start
    return new Promise((resolve) => setTimeout(resolve, 500))
}

import treeKill from 'tree-kill'

export function stopGateway() {
    if (gatewayProcess) {
        logger.info('Gateway', 'Stopping Gateway...')
        if (gatewayProcess.pid) {
             treeKill(gatewayProcess.pid, 'SIGKILL', (err) => {
                if (err) logger.error('Gateway', `Error killing gateway process tree: ${err}`)
             })
        } else {
             gatewayProcess.kill()
        }
        gatewayProcess = null
    }
}


