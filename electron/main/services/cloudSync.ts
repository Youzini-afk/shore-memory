import fs from 'fs-extra'
import path from 'path'
import { paths } from '../utils/env'
import {
  getSteamClient,
  isCloudEnabledForAccount,
  isCloudEnabledForApp,
  readCloudFile,
  writeCloudFile,
  deleteCloudFile,
  cloudFileExists,
  listCloudFiles
} from './steam'

/**
 * 云同步配置
 * 方案 B: 完整同步 (包含向量索引)
 */
const SYNC_CONFIG = {
  // 需要同步的文件列表 (相对于 data 目录)
  files: [
    // 数据库文件
    'perocore.db',
    'social_storage_v2.db',
    'pero.db',
    // 配置文件
    'agent_launch_config.json',
    // 记忆索引
    'memory/tags.json',
    'memory/tags.index',
    // Agent 记忆索引 (动态扫描)
    // 'memory/agents/{agent_id}/memory.index'
  ],
  // 需要同步的目录 (递归)
  directories: [
    'workspace', // 日记、周报等用户生成内容
    'memory/agents' // Agent 记忆索引
  ],
  // 排除的文件模式
  excludePatterns: [
    /\.db-shm$/, // SQLite 共享内存文件
    /\.db-wal$/, // SQLite 预写日志
    /gateway_token\.json$/, // 网关 Token (敏感信息)
    /models_cache/, // 模型缓存 (太大)
    /sandbox/ // 沙盒临时文件
  ]
}

export interface SyncResult {
  success: boolean
  uploaded: string[]
  downloaded: string[]
  failed: string[]
  errors: string[]
}

export interface CloudSyncStatus {
  enabled: boolean
  enabledForAccount: boolean
  enabledForApp: boolean
  lastSyncTime: number | null
  totalFiles: number
  totalSize: bigint
}

/**
 * 云同步服务
 * 负责将用户数据同步到 Steam Cloud
 */
class CloudSyncService {
  private dataDir: string
  private lastSyncTime: number | null = null
  private syncInProgress: boolean = false

  constructor() {
    this.dataDir = paths.data
  }

  /**
   * 获取云同步状态
   */
  getStatus(): CloudSyncStatus {
    const enabledForAccount = isCloudEnabledForAccount()
    const enabledForApp = isCloudEnabledForApp()
    const files = listCloudFiles()

    return {
      enabled: enabledForAccount && enabledForApp,
      enabledForAccount,
      enabledForApp,
      lastSyncTime: this.lastSyncTime,
      totalFiles: files.length,
      totalSize: files.reduce((sum, f) => sum + f.size, BigInt(0))
    }
  }

  /**
   * 获取需要同步的所有文件路径
   */
  private getSyncFiles(): string[] {
    const files: string[] = []

    // 添加配置中指定的文件
    for (const file of SYNC_CONFIG.files) {
      const filePath = path.join(this.dataDir, file)
      if (fs.existsSync(filePath) && !this.isExcluded(file)) {
        files.push(file)
      }
    }

    // 扫描目录
    for (const dir of SYNC_CONFIG.directories) {
      const dirPath = path.join(this.dataDir, dir)
      if (fs.existsSync(dirPath)) {
        this.scanDirectory(dir, files)
      }
    }

    return files
  }

  /**
   * 递归扫描目录
   */
  private scanDirectory(relativeDir: string, files: string[]): void {
    const dirPath = path.join(this.dataDir, relativeDir)
    const entries = fs.readdirSync(dirPath, { withFileTypes: true })

    for (const entry of entries) {
      const relativePath = path.join(relativeDir, entry.name)

      if (entry.isDirectory()) {
        this.scanDirectory(relativePath, files)
      } else if (entry.isFile() && !this.isExcluded(relativePath)) {
        files.push(relativePath.replace(/\\/g, '/'))
      }
    }
  }

  /**
   * 检查文件是否应该被排除
   */
  private isExcluded(relativePath: string): boolean {
    for (const pattern of SYNC_CONFIG.excludePatterns) {
      if (pattern.test(relativePath)) {
        return true
      }
    }
    return false
  }

  /**
   * 将文件路径转换为云存储键名
   */
  private pathToCloudKey(relativePath: string): string {
    // 将路径分隔符统一为正斜杠，并添加前缀
    return 'perocore/' + relativePath.replace(/\\/g, '/')
  }

  /**
   * 读取本地文件内容
   */
  private readLocalFile(relativePath: string): string | null {
    const filePath = path.join(this.dataDir, relativePath)
    try {
      // 检查是否为文本文件
      if (this.isTextFile(relativePath)) {
        return fs.readFileSync(filePath, 'utf-8')
      } else {
        // 二进制文件，转换为 base64
        const buffer = fs.readFileSync(filePath)
        return 'base64:' + buffer.toString('base64')
      }
    } catch (e) {
      console.error(`[CloudSync] 读取本地文件失败 ${relativePath}:`, e)
      return null
    }
  }

  /**
   * 写入本地文件
   */
  private writeLocalFile(relativePath: string, content: string): boolean {
    const filePath = path.join(this.dataDir, relativePath)
    try {
      // 确保目录存在
      fs.ensureDirSync(path.dirname(filePath))

      // 检查是否为 base64 编码的二进制文件
      if (content.startsWith('base64:')) {
        const buffer = Buffer.from(content.slice(7), 'base64')
        fs.writeFileSync(filePath, buffer)
      } else {
        fs.writeFileSync(filePath, content, 'utf-8')
      }
      return true
    } catch (e) {
      console.error(`[CloudSync] 写入本地文件失败 ${relativePath}:`, e)
      return false
    }
  }

  /**
   * 判断文件是否为文本文件
   */
  private isTextFile(filePath: string): boolean {
    const textExtensions = ['.json', '.md', '.txt', '.py', '.js', '.ts']
    const ext = path.extname(filePath).toLowerCase()
    return textExtensions.includes(ext)
  }

  /**
   * 上传所有本地数据到云端
   */
  async uploadToCloud(): Promise<SyncResult> {
    if (this.syncInProgress) {
      return {
        success: false,
        uploaded: [],
        downloaded: [],
        failed: [],
        errors: ['同步正在进行中']
      }
    }

    this.syncInProgress = true
    const result: SyncResult = {
      success: true,
      uploaded: [],
      downloaded: [],
      failed: [],
      errors: []
    }

    try {
      const files = this.getSyncFiles()
      console.log(`[CloudSync] 开始上传 ${files.length} 个文件到云端...`)

      for (const file of files) {
        const cloudKey = this.pathToCloudKey(file)
        const content = this.readLocalFile(file)

        if (content === null) {
          result.failed.push(file)
          result.errors.push(`无法读取文件: ${file}`)
          continue
        }

        if (writeCloudFile(cloudKey, content)) {
          result.uploaded.push(file)
          console.log(`[CloudSync] 上传成功: ${file}`)
        } else {
          result.failed.push(file)
          result.errors.push(`上传失败: ${file}`)
        }
      }

      // 上传同步元数据
      const metadata = {
        lastSyncTime: Date.now(),
        version: 1,
        fileCount: result.uploaded.length
      }
      writeCloudFile('perocore/sync_metadata.json', JSON.stringify(metadata, null, 2))

      this.lastSyncTime = metadata.lastSyncTime
      result.success = result.failed.length === 0

      console.log(`[CloudSync] 上传完成: ${result.uploaded.length} 成功, ${result.failed.length} 失败`)
    } catch (e) {
      result.success = false
      result.errors.push(`上传过程出错: ${e}`)
      console.error('[CloudSync] 上传过程出错:', e)
    } finally {
      this.syncInProgress = false
    }

    return result
  }

  /**
   * 从云端下载所有数据到本地
   */
  async downloadFromCloud(): Promise<SyncResult> {
    if (this.syncInProgress) {
      return {
        success: false,
        uploaded: [],
        downloaded: [],
        failed: [],
        errors: ['同步正在进行中']
      }
    }

    this.syncInProgress = true
    const result: SyncResult = {
      success: true,
      uploaded: [],
      downloaded: [],
      failed: [],
      errors: []
    }

    try {
      // 读取同步元数据
      const metadataStr = readCloudFile('perocore/sync_metadata.json')
      if (metadataStr) {
        const metadata = JSON.parse(metadataStr)
        console.log(`[CloudSync] 云端元数据: 最后同步时间 ${new Date(metadata.lastSyncTime).toLocaleString()}`)
      }

      // 获取云端文件列表
      const cloudFiles = listCloudFiles()
      const perocoreFiles = cloudFiles.filter(f => f.name.startsWith('perocore/'))

      console.log(`[CloudSync] 开始从云端下载 ${perocoreFiles.length} 个文件...`)

      for (const cloudFile of perocoreFiles) {
        // 跳过元数据文件
        if (cloudFile.name === 'perocore/sync_metadata.json') {
          continue
        }

        // 将云端键名转换为本地相对路径
        const relativePath = cloudFile.name.replace('perocore/', '')
        const content = readCloudFile(cloudFile.name)

        if (content === null) {
          result.failed.push(relativePath)
          result.errors.push(`无法下载文件: ${relativePath}`)
          continue
        }

        if (this.writeLocalFile(relativePath, content)) {
          result.downloaded.push(relativePath)
          console.log(`[CloudSync] 下载成功: ${relativePath}`)
        } else {
          result.failed.push(relativePath)
          result.errors.push(`写入失败: ${relativePath}`)
        }
      }

      result.success = result.failed.length === 0
      this.lastSyncTime = Date.now()

      console.log(`[CloudSync] 下载完成: ${result.downloaded.length} 成功, ${result.failed.length} 失败`)
    } catch (e) {
      result.success = false
      result.errors.push(`下载过程出错: ${e}`)
      console.error('[CloudSync] 下载过程出错:', e)
    } finally {
      this.syncInProgress = false
    }

    return result
  }

  /**
   * 执行双向同步 (先下载云端数据，再上传本地数据)
   */
  async sync(): Promise<SyncResult> {
    console.log('[CloudSync] 开始双向同步...')

    // 先下载云端数据
    const downloadResult = await this.downloadFromCloud()

    // 再上传本地数据
    const uploadResult = await this.uploadToCloud()

    return {
      success: downloadResult.success && uploadResult.success,
      uploaded: uploadResult.uploaded,
      downloaded: downloadResult.downloaded,
      failed: [...downloadResult.failed, ...uploadResult.failed],
      errors: [...downloadResult.errors, ...uploadResult.errors]
    }
  }

  /**
   * 清除云端所有数据
   */
  async clearCloudData(): Promise<boolean> {
    try {
      const cloudFiles = listCloudFiles()
      const perocoreFiles = cloudFiles.filter(f => f.name.startsWith('perocore/'))

      for (const file of perocoreFiles) {
        deleteCloudFile(file.name)
        console.log(`[CloudSync] 已删除云端文件: ${file.name}`)
      }

      console.log(`[CloudSync] 已清除 ${perocoreFiles.length} 个云端文件`)
      return true
    } catch (e) {
      console.error('[CloudSync] 清除云端数据失败:', e)
      return false
    }
  }
}

// 导出单例
export const cloudSyncService = new CloudSyncService()
