import fs from 'fs-extra'
import AdmZip from 'adm-zip'
import axios from 'axios'
import { join } from 'path'
import { paths, isDev } from '../utils/env'
import { WindowLike } from '../types'

const ES_URL = 'https://www.voidtools.com/ES-1.1.0.27.x64.zip'

function getRootPath() {
  if (isDev) {
    return process.cwd()
  } else {
    return paths.resources
  }
}

/**
 * 获取 ES 工具安装目录。
 * 优先查找预捆绑的位置（source/resources），
 * 用户安装时使用可写的 paths.data/tools/ 目录。
 */
export function getEsDir() {
  // 1. 检查预捆绑位置
  const root = getRootPath()
  const bundledPaths = [
    join(root, 'backend/nit_core/tools/core/FileSearch'),
    join(paths.resources, 'backend/nit_core/tools/core/FileSearch')
  ]
  for (const p of bundledPaths) {
    if (fs.existsSync(join(p, 'es.exe'))) return p
  }

  // 2. 检查用户安装位置
  const userInstallDir = join(paths.data, 'tools', 'FileSearch')
  if (fs.existsSync(join(userInstallDir, 'es.exe'))) return userInstallDir

  // 3. 后备方案：返回用户安装目录（用于 installEs 写入）
  return userInstallDir
}

export function checkEsInstalled() {
  const dir = getEsDir()
  const exe = join(dir, 'es.exe')
  return fs.existsSync(exe)
}

export async function installEs(window: WindowLike) {
  const dir = getEsDir()
  const emit = (msg: string) => {
    try {
      if (!window.isDestroyed()) window.webContents.send('es-log', msg)
    } catch {
      // 忽略
    }
  }

  emit(`正在检查 ES 工具: ${dir}`)

  if (checkEsInstalled()) {
    emit('ES 工具已安装。')
    return true
  }

  emit('未找到 ES 工具。正在开始下载...')
  await fs.ensureDir(dir)

  try {
    const response = await axios({
      method: 'get',
      url: ES_URL,
      responseType: 'arraybuffer'
    })

    const zipBuffer = Buffer.from(response.data)
    const zip = new AdmZip(zipBuffer)
    const zipEntries = zip.getEntries()

    let found = false
    for (const entry of zipEntries) {
      if (entry.entryName === 'es.exe') {
        zip.extractEntryTo(entry, dir, false, true)
        found = true
        break
      }
    }

    if (!found) {
      throw new Error('下载的 zip 中未找到 es.exe')
    }

    emit('ES 工具安装完成。')
    return true
  } catch (e: any) {
    emit(`下载/安装失败: ${e.message}`)
    return false
  }
}
