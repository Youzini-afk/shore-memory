import * as THREE from 'three'
import { IModelProvider, ParsedModelData } from './IModelProvider'

/**
 * 容器内文件结构
 * 对应 Rust Native 模块输出的 PeroContainerFile
 */
export interface PeroContainerFile {
  path: string
  data: Uint8Array
}

/**
 * 容器结构
 * 对应 Rust Native 模块输出的 PeroContainer
 */
export interface PeroContainer {
  files: PeroContainerFile[]
}

/**
 * .pero 容器提供者
 * 用于加载加密的 tar 打包文件夹（模型+纹理+动画+控制器等）
 * 所有资源从内存加载，无需解压到磁盘
 */
export class PeroContainerProvider implements IModelProvider {
  private containerUrl: string
  private boneFilterPatterns?: string[]
  private files = new Map<string, Uint8Array>()
  private loaded = false
  private textureCache = new Map<string, THREE.Texture>()

  constructor(containerUrl: string, boneFilterPatterns?: string[]) {
    this.containerUrl = containerUrl
    this.boneFilterPatterns = boneFilterPatterns
  }

  /**
   * 加载并解密容器
   */
  private async ensureLoaded(): Promise<void> {
    if (this.loaded) return

    try {
      // 1. 获取加密的容器数据
      const response = await fetch(this.containerUrl)
      if (!response.ok) {
        throw new Error(`加载容器失败: ${this.containerUrl}`)
      }
      const arrayBuffer = await response.arrayBuffer()

      // 2. 调用 Native 模块解密并解包
      console.time('解密并解包 .pero 容器')
      // @ts-ignore
      const container: PeroContainer = await window.electron.loadPeroContainer(
        new Uint8Array(arrayBuffer)
      )
      console.timeEnd('解密并解包 .pero 容器')

      // 3. 构建文件映射（标准化路径为小写）
      for (const file of container.files) {
        const normalizedPath = file.path.toLowerCase().replace(/\\/g, '/')
        this.files.set(normalizedPath, file.data)
        console.log(`[PeroContainer] 已加载文件: ${normalizedPath} (${file.data.length} bytes)`)
      }

      this.loaded = true
    } catch (e) {
      console.error('[PeroContainer] 加载容器失败:', e)
      throw e
    }
  }

  /**
   * 根据模式查找文件
   */
  private findFile(patterns: string[]): Uint8Array | undefined {
    for (const pattern of patterns) {
      const normalizedPattern = pattern.toLowerCase()
      // 精确匹配
      if (this.files.has(normalizedPattern)) {
        return this.files.get(normalizedPattern)
      }
      // 后缀匹配
      for (const [path, data] of this.files) {
        if (path.endsWith(normalizedPattern)) {
          return data
        }
      }
    }
    return undefined
  }

  /**
   * 查找所有匹配的文件
   */
  private findAllFiles(patterns: string[]): Map<string, Uint8Array> {
    const result = new Map<string, Uint8Array>()
    for (const pattern of patterns) {
      const normalizedPattern = pattern.toLowerCase()
      for (const [path, data] of this.files) {
        if (path.endsWith(normalizedPattern)) {
          result.set(path, data)
        }
      }
    }
    return result
  }

  async getManifest(): Promise<any> {
    await this.ensureLoaded()

    // 尝试查找 manifest 文件
    const manifestData = this.findFile(['manifest.json', 'model.json'])
    if (manifestData) {
      try {
        const text = new TextDecoder().decode(manifestData)
        return JSON.parse(text)
      } catch (e) {
        console.warn('[PeroContainer] 解析 manifest 失败:', e)
      }
    }

    // 返回默认 manifest
    return {
      name: 'PeroContainer',
      version: '3.0.0',
      secure: true,
      format: 'tar-container'
    }
  }

  async getModelData(): Promise<ParsedModelData> {
    await this.ensureLoaded()

    // 查找模型文件（优先查找 models/ 目录下的 main.json）
    const modelData =
      this.findFile(['models/main.json', 'main.json', '.geo.json', 'model.json']) ||
      this.findFile(['.json']) // 最后保底查找任意 .json

    if (!modelData) {
      console.error(
        '[PeroContainer] 容器内未找到模型文件, 可用文件:',
        Array.from(this.files.keys())
      )
      throw new Error('[PeroContainer] 容器内未找到模型文件')
    }

    try {
      // 使用 Rust Native 模块解析标准模型数据
      // 这会自动处理几何体计算、UV 映射（包括 per-face UV）、镜像等复杂逻辑
      console.time('Rust Parse Standard Model')
      console.log(`[PeroContainer] 准备解析模型, 数据大小: ${modelData.length} bytes`)
      // @ts-ignore
      const parsedData: ParsedModelData = await window.electron.loadStandardModel(
        modelData,
        this.boneFilterPatterns
      )
      console.timeEnd('Rust Parse Standard Model')

      if (!parsedData || !parsedData.bones || parsedData.bones.length === 0) {
        console.warn('[PeroContainer] 解析出的模型骨骼为空')
      } else {
        console.log(`[PeroContainer] 模型解析成功, 包含 ${parsedData.bones.length} 个骨骼`)
      }

      return parsedData
    } catch (e) {
      console.error('[PeroContainer] 解析模型失败:', e)
      throw e
    }
  }

  async getTexture(): Promise<THREE.Texture> {
    await this.ensureLoaded()

    // 查找纹理文件
    const textureData = this.findFile([
      'textures/texture.png',
      'texture.png',
      '.png',
      '.jpg',
      '.jpeg'
    ])
    if (!textureData) {
      throw new Error('[PeroContainer] 容器内未找到纹理文件')
    }

    // 检查缓存
    const cacheKey = this.containerUrl + '_texture'
    if (this.textureCache.has(cacheKey)) {
      return this.textureCache.get(cacheKey)!
    }

    return new Promise((resolve, reject) => {
      // 从内存数据创建 Blob URL
      // 使用 any 转型解决部分环境下 Uint8Array 与 BlobPart 的类型兼容性问题喵~
      const blob = new Blob([textureData as any], { type: 'image/png' })
      const url = URL.createObjectURL(blob)

      const loader = new THREE.TextureLoader()
      loader.load(
        url,
        (texture) => {
          texture.magFilter = THREE.NearestFilter
          texture.minFilter = THREE.NearestFilter
          texture.generateMipmaps = false // 禁用 Mipmaps 以获得更锐利的像素效果
          texture.colorSpace = THREE.SRGBColorSpace
          this.textureCache.set(cacheKey, texture)
          // 释放 Blob URL
          URL.revokeObjectURL(url)
          resolve(texture)
        },
        undefined,
        (error) => {
          console.error('[PeroContainer] 加载纹理失败:', error)
          URL.revokeObjectURL(url)
          reject(error)
        }
      )
    })
  }

  async getAnimations(): Promise<Map<string, any>> {
    await this.ensureLoaded()

    const animations = new Map<string, any>()

    // 查找所有动画文件
    const animFiles = this.findAllFiles(['.animation.json'])
    for (const [path, data] of animFiles) {
      try {
        const text = new TextDecoder().decode(data)
        const json = JSON.parse(text)
        if (json.animations) {
          for (const [key, value] of Object.entries(json.animations)) {
            animations.set(key, value)
          }
        }
      } catch (e) {
        console.warn(`[PeroContainer] 解析动画失败: ${path}`, e)
      }
    }

    return animations
  }

  /**
   * 获取动画控制器
   */
  async getAnimationControllers(): Promise<Map<string, any>> {
    await this.ensureLoaded()

    const controllers = new Map<string, any>()

    // 查找所有动画控制器文件
    const controllerFiles = this.findAllFiles(['.controller.json', 'controller.json'])
    for (const [path, data] of controllerFiles) {
      try {
        const text = new TextDecoder().decode(data)
        const json = JSON.parse(text)
        if (json.animation_controllers) {
          for (const [key, value] of Object.entries(json.animation_controllers)) {
            controllers.set(key, value)
          }
        }
      } catch (e) {
        console.warn(`[PeroContainer] 解析动画控制器失败: ${path}`, e)
      }
    }

    return controllers
  }

  /**
   * 获取渲染控制器
   */
  async getRenderControllers(): Promise<Map<string, any>> {
    await this.ensureLoaded()

    const controllers = new Map<string, any>()

    // 查找所有渲染控制器文件
    const controllerFiles = this.findAllFiles(['render_controllers.json'])
    for (const [path, data] of controllerFiles) {
      try {
        const text = new TextDecoder().decode(data)
        const json = JSON.parse(text)
        if (json.render_controllers) {
          for (const [key, value] of Object.entries(json.render_controllers)) {
            controllers.set(key, value)
          }
        }
      } catch (e) {
        console.warn(`[PeroContainer] 解析渲染控制器失败: ${path}`, e)
      }
    }

    return controllers
  }

  /**
   * 获取容器内的所有文件列表
   */
  async getFileList(): Promise<string[]> {
    await this.ensureLoaded()
    return Array.from(this.files.keys())
  }

  /**
   * 获取指定文件的数据
   */
  async getFile(path: string): Promise<Uint8Array | undefined> {
    await this.ensureLoaded()
    return this.files.get(path.toLowerCase())
  }
}
