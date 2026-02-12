import path from 'path'
import fs from 'fs-extra'
import { execSync } from 'child_process'
import which from 'which'
import { checkNapCatInstalled } from './napcat.js'
import { isDev, paths, isElectron } from '../utils/env'
import { logger } from '../utils/logger'

export interface DiagnosticReport {
  python_exists: boolean
  python_path: string
  python_version: string
  script_exists: boolean
  script_path: string
  port_9120_free: boolean
  data_dir_writable: boolean
  data_dir: string
  core_available: boolean
  vc_redist_installed: boolean
  napcat_installed: boolean
  webview2_installed: boolean // 兼容性保留字段
  node_exists: boolean
  node_path: string
  node_version: string
  errors: string[]
}

const workspaceRoot = isDev
  ? path.resolve(__dirname, '../../..') // dist-electron/main -> electron -> 根目录
  : isElectron
    ? path.dirname(paths.exe)
    : paths.app

// 规范化路径
function fixPath(p: string): string {
  return path.normalize(p)
}

function getResourceDir(): string {
  return isDev ? workspaceRoot : paths.resources
}

export async function getDiagnostics(): Promise<DiagnosticReport> {
  const errors: string[] = []
  const resourceDir = getResourceDir()

  logger.info('Main', `[诊断] 工作区: ${workspaceRoot}`)
  logger.info('Main', `[诊断] 资源目录: ${resourceDir}`)

  // 1. Python 路径
  let pythonPath = ''
  let pythonExists = false
  let devVenvPythonExists = false

  // 检查开发环境虚拟环境
  const devVenvPython = path.join(workspaceRoot, 'backend/venv/Scripts/python.exe')
  const dotVenvPython = path.join(workspaceRoot, 'backend/.venv/Scripts/python.exe')

  logger.info('Main', `[诊断] 检查虚拟环境路径: ${devVenvPython} 和 ${dotVenvPython}`)

  if (await fs.pathExists(devVenvPython)) {
    devVenvPythonExists = true
    pythonPath = devVenvPython
    pythonExists = true
  } else if (await fs.pathExists(dotVenvPython)) {
    devVenvPythonExists = true
    pythonPath = dotVenvPython
    pythonExists = true
  } else {
    // 检查发布资源（多个位置）
    const trials = [
      path.join(resourceDir, 'python/python.exe'),
      path.join(resourceDir, '_up_/python/python.exe')
    ]

    for (const trial of trials) {
      if (await fs.pathExists(trial)) {
        pythonPath = trial
        pythonExists = true
        break
      }
    }
  }

  // 后备方案: 系统 Python
  if (!pythonExists) {
    try {
      const systemPython = await which('python')
      if (systemPython) {
        pythonPath = systemPython
        pythonExists = true
      }
    } catch {
      try {
        const systemPython3 = await which('python3')
        if (systemPython3) {
          pythonPath = systemPython3
          pythonExists = true
        }
      } catch {
        // 忽略
      }
    }
  }

  pythonPath = fixPath(pythonPath)

  // 检查 Python 版本和核心
  let pythonVersion = 'Unknown'
  let coreAvailable = false

  if (pythonExists) {
    logger.info('Main', `[诊断] Python 发现于: ${pythonPath}`)
    try {
      const versionOutput = execSync(`"${pythonPath}" --version`, {
        encoding: 'utf8',
        stdio: 'pipe'
      }).trim()
      pythonVersion = versionOutput
      logger.info('Main', `[诊断] Python 版本: ${pythonVersion}`)
    } catch (e: any) {
      logger.error('Main', `[诊断] Python 版本检查失败: ${e.message}`)
      errors.push('Python 解释器无法运行，可能缺少系统组件 (如 VCRUNTIME140.dll)')
    }

    try {
      const coreCheck = execSync(`"${pythonPath}" -c "import pero_memory_core; print('OK')"`, {
        encoding: 'utf8',
        stdio: 'pipe'
      }).trim()
      if (coreCheck.includes('OK')) {
        coreAvailable = true
      } else {
        logger.warn('Main', `[诊断] pero_memory_core 导入失败: 输出未包含 OK`)
        // errors.push('关键核心组件 pero_memory_core 未找到，记忆功能将受限') // 不阻塞启动
      }
    } catch (e: any) {
      logger.warn('Main', `[诊断] pero_memory_core 检查失败: ${e.message}`)
      // errors.push('关键核心组件 pero_memory_core 未找到，记忆功能将受限') // 不阻塞启动
    }
  } else {
    logger.error('Main', `[诊断] 未找到 Python。`)
    errors.push(`Python 解释器未找到。探测路径: ${pythonPath}`)
  }

  // 2. 脚本路径
  let scriptPath = ''
  const scriptTrials = [
    path.join(workspaceRoot, 'backend/main.py'),
    path.join(resourceDir, 'backend/main.py'),
    path.join(resourceDir, 'main.py'),
    path.join(resourceDir, '_up_/backend/main.py'),
    path.join(process.resourcesPath, 'backend/main.py') // 为打包后的应用添加明确的 resourcesPath 检查
  ]

  for (const trial of scriptTrials) {
    if (await fs.pathExists(trial)) {
      scriptPath = trial
      break
    }
  }
  scriptPath = fixPath(scriptPath)
  const scriptExists = await fs.pathExists(scriptPath)
  if (!scriptExists) {
    errors.push(`后端主脚本未找到: ${scriptPath}`)
  }

  // 3. 检查端口 9120
  // 在 Node 中，我们可以尝试启动服务器或使用 net.connect。
  // 简单检查：尝试连接，如果成功则端口被占用。
  const port9120Free = await checkPortFree(9120)
  if (!port9120Free) {
    errors.push('端口 9120 已被占用，请检查是否有其他 PeroCore 实例在运行')
  }

  // 4. 数据目录
  let dataDir = ''
  if (!devVenvPythonExists) {
    dataDir = path.join(paths.userData, 'data')
    logger.info('Main', `[诊断] 使用生产环境数据目录: ${dataDir}`)
  } else {
    dataDir = path.join(workspaceRoot, 'backend/data')
    logger.info('Main', `[诊断] 使用开发环境数据目录: ${dataDir}`)
  }
  dataDir = fixPath(dataDir)
  await fs.ensureDir(dataDir)

  let dataDirWritable = false
  try {
    const testFile = path.join(dataDir, '.write_test')
    await fs.writeFile(testFile, '')
    await fs.remove(testFile)
    dataDirWritable = true
  } catch {
    errors.push(`数据目录不可写: ${dataDir}`)
  }

  // 5. VC++ Redist (仅限 Windows)
  let vcRedistInstalled = true
  if (process.platform === 'win32') {
    const systemRoot = process.env.SystemRoot || 'C:\\Windows'
    const vcRuntime = path.join(systemRoot, 'System32/vcruntime140.dll')
    const vcRuntime1 = path.join(systemRoot, 'System32/vcruntime140_1.dll') // Python 3.10+ 需要此文件
    const sysWow64 = path.join(systemRoot, 'SysWOW64/vcruntime140.dll')

    vcRedistInstalled = (await fs.pathExists(vcRuntime)) || (await fs.pathExists(sysWow64))
    const vcRedist1Installed = await fs.pathExists(vcRuntime1)

    if (!vcRedistInstalled) {
      errors.push('关键系统组件缺失: VCRUNTIME140.dll。请安装 Visual C++ Redistributable。')
    }
    if (!vcRedist1Installed) {
      logger.warn('Main', '[诊断] 在 System32 中未找到 vcruntime140_1.dll')
      errors.push('关键系统组件缺失: VCRUNTIME140_1.dll。请安装最新版 Visual C++ Redistributable。')
    }
  }

  // 6. 检查 Node.js
  let nodePath = ''
  let nodeExists = false
  let nodeVersion = 'Unknown'

  // NapCat 通常捆绑了 node，或者我们查找系统 node
  // 注意：NapCat 逻辑将是分开的，但这里我们检查通用的 node 可用性
  const nodeTrials = [
    path.join(resourceDir, 'nodejs/node.exe'),
    path.join(resourceDir, 'bin/node.exe'),
    path.join(resourceDir, 'node.exe')
  ]

  for (const trial of nodeTrials) {
    if (await fs.pathExists(trial)) {
      nodePath = trial
      nodeExists = true
      break
    }
  }

  if (!nodeExists) {
    try {
      nodePath = await which('node')
      nodeExists = true
    } catch {
      // 在路径中未找到
    }
  }

  if (nodeExists) {
    try {
      nodeVersion = execSync(`"${nodePath}" --version`, { encoding: 'utf8' }).trim()
    } catch {
      // 忽略
    }
  }

  // 检查 NapCat
  let napcatInstalled = false
  try {
    napcatInstalled = checkNapCatInstalled()
    logger.info('Main', `[诊断] checkNapCatInstalled 结果: ${napcatInstalled}`)
  } catch (e) {
    logger.error('Main', `[诊断] checkNapCatInstalled 错误: ${e}`)
  }

  return {
    python_exists: pythonExists,
    python_path: pythonPath,
    python_version: pythonVersion,
    script_exists: scriptExists,
    script_path: scriptPath,
    port_9120_free: port9120Free,
    data_dir_writable: dataDirWritable,
    data_dir: dataDir,
    core_available: coreAvailable,
    vc_redist_installed: vcRedistInstalled,
    napcat_installed: napcatInstalled,
    webview2_installed: true, // Electron 捆绑了 Chromium
    node_exists: nodeExists,
    node_path: nodePath,
    node_version: nodeVersion,
    errors
  }
}

import net from 'net'
function checkPortFree(port: number): Promise<boolean> {
  return new Promise((resolve) => {
    const server = net.createServer()
    server.once('error', (err: any) => {
      if (err.code === 'EADDRINUSE') {
        resolve(false)
      } else {
        resolve(true) // 其他错误视为端口空闲
      }
    })
    server.once('listening', () => {
      server.close()
      resolve(true)
    })
    server.listen(port)
  })
}
