import path from 'path'
import fs from 'fs-extra'
import { spawn, ChildProcess } from 'child_process'
import winreg from 'winreg'
import AdmZip from 'adm-zip'
import axios from 'axios'
import { paths, isDev } from '../utils/env'
import { WindowLike } from '../types'

let napcatProcess: ChildProcess | null = null
const napcatLogs: string[] = []

function getRootPath() {
  if (isDev) {
    return path.resolve(__dirname, '../../..')
  } else {
    return paths.resources
  }
}

function getNapCatDir() {
  const root = getRootPath()
  // 尝试多个位置 (Rust PeroLauncher 逻辑一致)
  const trials = [
    path.join(root, 'backend/nit_core/plugins/social_adapter/NapCat'),
    path.join(root, 'nit_core/plugins/social_adapter/NapCat'),
    path.join(root, '_up_/backend/nit_core/plugins/social_adapter/NapCat'),
    path.join(root, '_up_/nit_core/plugins/social_adapter/NapCat')
  ]

  for (const trial of trials) {
    if (fs.existsSync(trial)) {
      console.log(`[NapCat] 发现安装路径: ${trial}`)
      return trial
    }
  }

  console.log(`[NapCat] 未找到安装，默认使用: ${trials[0]}`)
  return trials[0]
}

async function getQQPath(): Promise<string> {
  if (process.platform !== 'win32') return ''

  const regKeys = [
    '\\Software\\WOW6432Node\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\QQ',
    '\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\QQ'
  ]

  for (const keyPath of regKeys) {
    try {
      const key = new winreg({
        hive: winreg.HKLM,
        key: keyPath
      })

      const item = await new Promise<winreg.RegistryItem | null>((resolve) => {
        key.get('UninstallString', (err, item) => {
          if (err) resolve(null)
          else resolve(item)
        })
      })

      if (item) {
        const uninstallPath = item.value.replace(/"/g, '') // 移除引号
        const binDir = path.dirname(uninstallPath)
        const qqInBin = path.join(binDir, 'QQ.exe')
        const qqInRoot = path.join(binDir, '..', 'QQ.exe')

        if (await fs.pathExists(qqInBin)) return qqInBin
        if (await fs.pathExists(qqInRoot)) return path.normalize(qqInRoot)
      }
    } catch {
      // 忽略注册表错误
    }
  }

  // 默认路径后备
  const possiblePaths = [
    'C:\\Program Files (x86)\\Tencent\\QQ\\Bin\\QQ.exe',
    'C:\\Program Files\\Tencent\\QQ\\Bin\\QQ.exe'
  ]

  for (const p of possiblePaths) {
    if (await fs.pathExists(p)) return p
  }

  return ''
}

export async function startNapCat(window: WindowLike) {
  if (napcatProcess) return

  const napcatDir = getNapCatDir()
  const qqPath = await getQQPath()

  if (!(await fs.pathExists(napcatDir))) {
    throw new Error(`NapCat 目录未找到: ${napcatDir}`)
  }

  if (qqPath) {
    try {
      if (!window.isDestroyed())
        window.webContents.send('napcat-log', `[系统] 在以下位置找到 QQ: ${qqPath}`)
    } catch {
      // 忽略
    }
    console.log(`[NapCat] 在以下位置找到 QQ: ${qqPath}`)
  } else {
    try {
      if (!window.isDestroyed())
        window.webContents.send('system-error', '未找到 QQ。NapCat 需要安装 QQ。')
    } catch {
      // ignore
    }
    throw new Error('默认路径或注册表中未找到 QQ。')
  }

  // 首先尝试 NapCat.Shell.exe
  const shellExe = path.join(napcatDir, 'NapCat.Shell.exe')
  const napcatBat = path.join(napcatDir, 'napcat.bat')
  const indexJs = path.join(napcatDir, 'index.js')
  const napcatMjs = path.join(napcatDir, 'napcat.mjs')

  console.log(`[NapCat] 正在检查入口点 ${napcatDir}`)
  console.log(`[NapCat] Shell 存在: ${fs.existsSync(shellExe)}`)
  console.log(`[NapCat] MJS 存在: ${fs.existsSync(napcatMjs)}`)
  console.log(`[NapCat] Bat 存在: ${fs.existsSync(napcatBat)}`)
  console.log(`[NapCat] Index 存在: ${fs.existsSync(indexJs)}`)

  let cmd = ''
  let args: string[] = []
  const env = { ...process.env }

  // [修复] 禁用 OpenTelemetry 以防止 libprotobuf UTF-8 错误
  env.OTEL_SDK_DISABLED = 'true'
  env.OTEL_TRACES_EXPORTER = 'none'
  env.OTEL_METRICS_EXPORTER = 'none'
  env.OTEL_LOGS_EXPORTER = 'none'

  if (fs.existsSync(shellExe)) {
    cmd = shellExe
    args = ['-q', qqPath]
  } else if (fs.existsSync(napcatMjs)) {
    // 优先直接用 node 执行 napcat.mjs (修复 CJS/ESM 冲突)
    cmd = 'node'
    // 移除 -q 参数以允许使用 NapCat 自身的配置
    args = ['napcat.mjs']

    // 复制 index.js 中的环境变量
    env.NAPCAT_WRAPPER_PATH = path.join(napcatDir, 'wrapper.node')
    env.NAPCAT_QQ_PACKAGE_INFO_PATH = path.join(napcatDir, 'package.json')
    env.NAPCAT_QQ_VERSION_CONFIG_PATH = path.join(napcatDir, 'config.json')
    env.NAPCAT_DISABLE_PIPE = '1'
  } else if (fs.existsSync(napcatBat)) {
    // 回退到 bat (v4.12.8+ 可能不稳定)
    console.warn('[NapCat] 正在回退到 napcat.bat，但这可能会在 v4.12.8+ 上失败')
    cmd = 'cmd.exe'
    args = ['/c', 'napcat.bat', '-q', qqPath]
  } else if (fs.existsSync(indexJs)) {
    cmd = 'node'
    args = ['index.js']
  } else {
    throw new Error('未找到有效的 NapCat 入口点。')
  }

  console.log(`[NapCat] 正在启动: ${cmd} ${args.join(' ')} 在 ${napcatDir}`)
  try {
    if (!window.isDestroyed()) window.webContents.send('napcat-log', `[系统] 正在启动 NapCat...`)
  } catch {
    // ignore
  }

  napcatProcess = spawn(cmd, args, {
    cwd: napcatDir,
    env: env,
    stdio: ['pipe', 'pipe', 'pipe'],
    windowsHide: true
  })

  napcatProcess.stdout?.on('data', (data) => {
    const line = data.toString().trim()
    if (!line) return
    napcatLogs.push(line)
    if (napcatLogs.length > 2000) napcatLogs.shift()
    try {
      if (!window.isDestroyed()) window.webContents.send('napcat-log', line)
    } catch {
      // ignore
    }
  })

  napcatProcess.stderr?.on('data', (data) => {
    const line = data.toString().trim()
    if (!line) return
    console.error(`[NapCat 错误] ${line}`)
    try {
      if (!window.isDestroyed()) window.webContents.send('napcat-log', `[错误] ${line}`)
    } catch {
      // ignore
    }
  })

  napcatProcess.on('close', (code) => {
    console.log(`[NapCat] 已退出，代码 ${code}`)
    napcatProcess = null
    try {
      if (!window.isDestroyed())
        window.webContents.send('napcat-log', `[系统] NapCat 已退出 (代码: ${code})`)
    } catch {
      // ignore
    }
  })
}

export function stopNapCat(): Promise<void> {
  return new Promise((resolve) => {
    if (napcatProcess) {
      napcatProcess.on('close', () => {
        napcatProcess = null
        resolve()
      })
      napcatProcess.kill()
      // 如果进程没能立刻关闭，设置一个超时
      setTimeout(() => {
        if (napcatProcess) {
          napcatProcess.kill('SIGKILL')
          napcatProcess = null
          resolve()
        }
      }, 2000)
    } else {
      resolve()
    }
  })
}

export function getNapCatLogs() {
  return napcatLogs
}

export function sendNapCatCommand(command: string) {
  if (napcatProcess && napcatProcess.stdin) {
    napcatProcess.stdin.write(command + '\n')
  } else {
    throw new Error('NapCat 未运行')
  }
}

export function checkNapCatInstalled() {
  const dir = getNapCatDir()
  const shellExe = path.join(dir, 'NapCat.Shell.exe')
  const mjs = path.join(dir, 'napcat.mjs')
  const indexJs = path.join(dir, 'index.js')
  return fs.existsSync(shellExe) || fs.existsSync(mjs) || fs.existsSync(indexJs)
}

export async function installNapCat(window: WindowLike) {
  const dir = getNapCatDir()
  const emit = (msg: string) => {
    console.log(`[NapCat 安装程序] ${msg}`)
    try {
      if (!window.isDestroyed()) window.webContents.send('napcat-log', msg)
    } catch {
      // ignore
    }
  }

  emit(`正在检查 NapCat: ${dir}`)

  if (checkNapCatInstalled()) {
    emit('NapCat 已安装。')
    return true
  }

  emit('未找到 NapCat。开始下载...')
  await fs.ensureDir(dir)

  const version = 'v4.12.8'
  const assetName = 'NapCat.Shell.Windows.Node.zip'

  // 要尝试的镜像列表
  const mirrors = [
    `https://gh-proxy.com/https://github.com/NapNeko/NapCatQQ/releases/download/${version}/${assetName}`,
    `https://mirror.ghproxy.com/https://github.com/NapNeko/NapCatQQ/releases/download/${version}/${assetName}`,
    `https://github.moeyy.xyz/https://github.com/NapNeko/NapCatQQ/releases/download/${version}/${assetName}`,
    `https://github.com/NapNeko/NapCatQQ/releases/download/${version}/${assetName}`
  ]

  const download = async (downloadUrl: string) => {
    const response = await axios({
      method: 'get',
      url: downloadUrl,
      responseType: 'arraybuffer',
      timeout: 60000, // 增加超时至 60s
      headers: {
        'User-Agent':
          'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
      },
      onDownloadProgress: (progressEvent) => {
        if (progressEvent.total) {
          const percent = Math.round((progressEvent.loaded / progressEvent.total) * 100)
          try {
            if (!window.isDestroyed()) {
              window.webContents.send('napcat-download-progress', {
                percent,
                status: `正在下载... ${percent}%`,
                url: downloadUrl
              })
            }
          } catch {
            // 忽略
          }
        }
      }
    })
    return response.data
  }

  let zipBuffer: Buffer | null = null

  for (const url of mirrors) {
    try {
      emit(`尝试下载: ${url}`)
      // 重置进度
      try {
        if (!window.isDestroyed())
          window.webContents.send('napcat-download-progress', {
            percent: 0,
            status: 'Connecting...',
            url
          })
      } catch {
        // 忽略
      }

      zipBuffer = await download(url)
      if (zipBuffer) break
    } catch (e: any) {
      emit(`失败: ${e.message}`)
      continue
    }
  }

  if (!zipBuffer) {
    emit('所有镜像下载失败。')
    // 发送失败
    try {
      if (!window.isDestroyed())
        window.webContents.send('napcat-download-progress', {
          percent: 0,
          status: 'Download Failed',
          error: true
        })
    } catch {
      // 忽略
    }
    throw new Error('所有镜像下载失败。')
  }

  emit('下载完成。正在解压...')
  try {
    if (!window.isDestroyed())
      window.webContents.send('napcat-download-progress', {
        percent: 100,
        status: '正在解压...',
        processing: true
      })
  } catch {
    // ignore
  }

  try {
    const zip = new AdmZip(zipBuffer)
    zip.extractAllTo(dir, true)

    // 处理嵌套文件夹逻辑
    const shellExe = path.join(dir, 'NapCat.Shell.exe')
    const nodeMjs = path.join(dir, 'napcat.mjs')

    if (!(await fs.pathExists(shellExe)) && !(await fs.pathExists(nodeMjs))) {
      const entries = await fs.readdir(dir, { withFileTypes: true })
      for (const entry of entries) {
        if (entry.isDirectory()) {
          const nestedPath = path.join(dir, entry.name)
          const nestedShell = path.join(nestedPath, 'NapCat.Shell.exe')
          const nestedNode = path.join(nestedPath, 'napcat.mjs')

          if ((await fs.pathExists(nestedShell)) || (await fs.pathExists(nestedNode))) {
            // 将内容向上移动
            await fs.copy(nestedPath, dir, { overwrite: true })
            await fs.remove(nestedPath)
            break
          }
        }
      }
    }

    emit('安装完成。')
    try {
      if (!window.isDestroyed())
        window.webContents.send('napcat-download-progress', {
          percent: 100,
          status: 'Installed',
          completed: true
        })
    } catch {
      // ignore
    }
    return true
  } catch (e: any) {
    emit(`安装失败: ${e.message}`)
    try {
      if (!window.isDestroyed())
        window.webContents.send('napcat-download-progress', {
          percent: 0,
          status: '安装失败',
          error: true
        })
    } catch {
      // ignore
    }
    return false
  }
}
