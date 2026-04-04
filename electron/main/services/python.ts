import { spawn, ChildProcess } from 'child_process'
import path from 'path'
import fs from 'fs-extra'
import { getDiagnostics } from './diagnostics'
import { WindowLike } from '../types'
import { logger } from '../utils/logger'
import { getGatewayToken } from './system'
import { getWorkshopInstallPath } from './steam'
import { appEvents } from '../events'
import { isDev, paths } from '../utils/env'

const workspaceRoot = isDev ? path.resolve(__dirname, '../../..') : paths.resources

function fixPath(p: string): string {
  return path.normalize(p)
}

let backendProcess: ChildProcess | null = null
const logHistory: string[] = []
const MAX_LOGS = 2000

export function getBackendLogs() {
  return [...logHistory]
}

export async function startBackend(window: WindowLike, enableSocialMode: boolean) {
  // 1. 诊断
  const diag = await getDiagnostics()
  if (diag.errors.length > 0) {
    throw new Error(`启动失败！诊断错误：\n${diag.errors.join('\n')}`)
  }

  if (backendProcess) {
    return
  }

  const pythonPath = diag.python_path
  const scriptPath = diag.script_path
  const dataDir = diag.data_dir
  const backendRoot = path.dirname(scriptPath)

  // 配置路径
  const dbPath = path.join(dataDir, 'perocore.db')
  const configPath = path.join(dataDir, 'config.json')
  const logDir = path.join(dataDir, 'logs')
  const logFile = path.join(logDir, 'backend.log')

  // 确保日志目录存在
  await fs.ensureDir(logDir)

  // 初始配置复制（如果需要）
  if (!(await fs.pathExists(configPath))) {
    // ... 类似于 Rust 的资源复制逻辑
    // 暂时简化
  }

  // 环境变量设置
  const env = { ...process.env }

  // [环境隔离] 移除可能污染我们嵌入式 Python 实例的系统或用户环境变量
  Object.keys(env).forEach((key) => {
    if (key.startsWith('PYTHON') && key !== 'PATH' && key !== 'PYTHONPATH') {
      delete env[key]
    }
  })

  // 核心 Python 环境设置
  const pythonDir = path.dirname(pythonPath)
  const resourceDir = fixPath(isDev ? workspaceRoot : process.resourcesPath)
  const isEmbeddedPython =
    pythonPath.includes(path.join('resources', 'python')) ||
    pythonPath.includes(path.join('resources\\python'))

  if (isDev) {
    // 开发模式：使用 venv，需要设置 PYTHONHOME
    env['PYTHONHOME'] = pythonDir
    env['PYTHONPATH'] = workspaceRoot
  } else if (isEmbeddedPython) {
    // 嵌入式 Python：不设置 PYTHONHOME！
    // 嵌入式 Python 通过 ._pth 文件自我配置，外部的 PYTHONHOME 会干扰其内部路径发现机制
    delete env['PYTHONHOME']
    // PYTHONPATH 指向 resources/ 和 resources/backend/，扯展两种导入风格
    env['PYTHONPATH'] = `${resourceDir}${path.delimiter}${path.join(resourceDir, 'backend')}`
  } else {
    // 系统 Python 回退：与开发模式相同处理
    env['PYTHONHOME'] = pythonDir
    env['PYTHONPATH'] = `${resourceDir}${path.delimiter}${path.join(resourceDir, 'backend')}`
  }

  const workshopPath = getWorkshopInstallPath()

  logger.info('Backend', `Workshop Path: ${workshopPath || 'Not Found (Steam not running?)'}`)

  env['PYTHONNOUSERSITE'] = '1'
  env['PYTHONUNBUFFERED'] = '1'
  env['PYTHONUTF8'] = '1'
  env['PORT'] = '9120'
  env['ENABLE_SOCIAL_MODE'] = enableSocialMode.toString()
  env['PERO_DATA_DIR'] = dataDir
  env['PERO_WORKSHOP_DIR'] = workshopPath || ''
  env['PERO_DATABASE_PATH'] = dbPath
  env['PERO_CONFIG_PATH'] = configPath
  env['PERO_LOG_FILE'] = logFile
  env['GATEWAY_TOKEN'] = getGatewayToken()

  // 启动子进程
  const child = spawn(pythonPath, ['-u', scriptPath], {
    cwd: backendRoot,
    env: env as any,
    stdio: ['ignore', 'pipe', 'pipe'],
    detached: false, // 确保随父进程退出
    windowsHide: true
  })

  child.on('error', (err) => {
    logger.error('Backend', `启动 Python 进程失败: ${err.message}`)
    try {
      if (window && !window.isDestroyed()) {
        window.webContents.send('system-error', `后端启动失败 (Spawn Error): ${err.message}`)
      }
    } catch {
      // 忽略
    }
  })

  // 批量日志发送器以防止 IPC 洪水
  let logBatch: string[] = []
  let batchTimer: NodeJS.Timeout | null = null
  const BATCH_INTERVAL = 300 // 300ms
  const MAX_BATCH_SIZE = 500 // 最大 500 行

  const sendBatch = () => {
    if (logBatch.length === 0) return

    try {
      if (window && !window.isDestroyed()) {
        // 作为数组发送以减少 IPC 开销
        window.webContents.send('backend-log-batch', [...logBatch])
      }
    } catch {
      // 忽略
    }
    logBatch = []
    batchTimer = null
  }

  const queueLog = (msg: string) => {
    logBatch.push(msg)
    if (logBatch.length >= MAX_BATCH_SIZE) {
      if (batchTimer) clearTimeout(batchTimer)
      sendBatch()
    } else if (!batchTimer) {
      batchTimer = setTimeout(sendBatch, BATCH_INTERVAL)
    }
  }

  // 日志处理队列以防止事件循环阻塞
  const processingQueue: string[] = []
  let isProcessingLogs = false

  const processLogQueue = async () => {
    if (isProcessingLogs) return
    isProcessingLogs = true

    try {
      while (processingQueue.length > 0) {
        // 优化：分块处理
        const content = processingQueue.shift()
        if (!content) continue

        const lines = content.split(/\r?\n/)
        const MAX_LINES_PER_TICK = 200

        for (let i = 0; i < lines.length; i += MAX_LINES_PER_TICK) {
          const chunk = lines.slice(i, i + MAX_LINES_PER_TICK)

          chunk.forEach((line: string) => {
            const trimmedLine = line.trim()
            if (trimmedLine.length === 0 && line.length === 0) return

            // 优化：正则前快速检查
            let match = null
            if (line.startsWith('[')) {
              const pyLogRegex =
                /^\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\] \[(INFO|WARNING|ERROR|DEBUG)\] (.*)/
              match = line.match(pyLogRegex)
            }

            if (match) {
              const levelStr = match[1]
              const msg = match[2]
              let level: 'INFO' | 'WARN' | 'ERROR' | 'DEBUG' = 'INFO'

              if (levelStr === 'WARNING') level = 'WARN'
              else if (levelStr === 'ERROR') level = 'ERROR'
              else if (levelStr === 'DEBUG') level = 'DEBUG'

              logger.log('Backend', level, msg)
            } else {
              logger.info('Backend', line)
            }

            queueLog(line)

            if (logHistory.length >= MAX_LOGS) logHistory.shift()
            logHistory.push(line)
          })

          // 关键: 让出事件循环以允许 UI 更新和 IPC
          await new Promise((resolve) => setImmediate(resolve))
        }
      }
    } catch (err) {
      logger.error('Backend', `日志处理错误: ${err}`)
    } finally {
      isProcessingLogs = false
      // 检查是否有新日志
      if (processingQueue.length > 0) {
        setImmediate(processLogQueue)
      }
    }
  }

  child.stdout?.on('data', (data) => {
    const content = data.toString()
    processingQueue.push(content)
    processLogQueue()
  })

  child.stderr?.on('data', (data) => {
    const content = data.toString()
    const lines = content.split(/\r?\n/)

    lines.forEach((line: string) => {
      if (line.trim().length === 0 && line.length === 0) return

      logger.error('Backend', line)

      // 将错误加入队列以进行批量发送 (带前缀)
      queueLog(`[ERROR] ${line}`)

      if (logHistory.length >= MAX_LOGS) logHistory.shift()
      logHistory.push(`[ERROR] ${line}`)

      if (line.includes('Error') || line.includes('Exception') || line.includes('Traceback')) {
        try {
          if (window && !window.isDestroyed()) {
            window.webContents.send('system-error', `后端错误: ${line}`)
          }
        } catch {
          // 忽略
        }
      }
    })
  })

  child.on('close', (code) => {
    logger.info('Backend', `后端已退出，退出码: ${code}`)

    // 如果 backendProcess 仍然引用当前进程，说明是意外退出（不是通过 stopBackend 停止的）
    if (backendProcess && backendProcess.pid === child.pid) {
      logger.error('Backend', '后端意外崩溃，触发联动停止')
      appEvents.emit('backend-crashed', code)
    }

    backendProcess = null
  })

  backendProcess = child
}

import treeKill from 'tree-kill'

export function stopBackend(): Promise<void> {
  return new Promise((resolve) => {
    if (backendProcess) {
      logger.info('Backend', '正在停止后端...')
      if (backendProcess.pid) {
        // 强制使用 tree-kill 确保所有子进程都被杀死
        try {
          treeKill(backendProcess.pid, 'SIGKILL', (err) => {
            if (err) {
              logger.error('Backend', `杀死后端进程树时出错: ${err}`)
              // 回退尝试
              try {
                process.kill(backendProcess!.pid!)
              } catch {
                // 忽略
              }
            }
            backendProcess = null
            resolve()
          })
        } catch (e) {
          logger.error('Backend', `Tree kill 异常: ${e}`)
          backendProcess = null
          resolve()
        }
      } else {
        backendProcess.kill()
        backendProcess = null
        resolve()
      }
    } else {
      resolve()
    }
  })
}
