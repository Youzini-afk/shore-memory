import * as THREE from 'three'
import { IModelProvider, ParsedModelData } from './IModelProvider'
import { resolveAssetUrl } from '../../../../utils/assetUrl'

/**
 * 安全模型提供者 (Rust Native)
 * 用于加载加密的 .pero 模型文件
 */
export class PeroSecureProvider implements IModelProvider {
  private config: any
  private textureCache = new Map<string, THREE.Texture>()
  private boneFilterPatterns: string[] | undefined

  constructor(config: any, boneFilterPatterns?: string[]) {
    this.config = config
    this.boneFilterPatterns = boneFilterPatterns
  }

  async getManifest(): Promise<any> {
    return {
      name: this.config.name,
      version: '1.0.0',
      secure: true
    }
  }

  async getModelData(): Promise<ParsedModelData> {
    const modelUrl = this.config.model
    if (!modelUrl) throw new Error('Model URL not provided in config')

    try {
      // 1. 获取加密的二进制数据
      const url = resolveAssetUrl(modelUrl)
      const response = await fetch(url)
      if (!response.ok) throw new Error(`Failed to load secure model: ${modelUrl}`)
      const arrayBuffer = await response.arrayBuffer()

      // 2. 调用 Native 模块解密并解析 (通过 IPC)
      // 注意：密钥现在已经在 Rust 内部管理，JS 层不再可见，也无法拦截
      console.time('Rust Decrypt & Parse')
      // @ts-ignore
      const parsedData = await window.electron.loadPeroModel(
        new Uint8Array(arrayBuffer),
        this.boneFilterPatterns
      )
      console.timeEnd('Rust Decrypt & Parse')

      // 3. 直接返回 Rust 解析后的对象
      return parsedData
    } catch (e) {
      console.error('Failed to load/decrypt secure model:', e)
      throw e
    }
  }

  async getTexture(): Promise<THREE.Texture> {
    const originalUrl = this.config.texture
    if (!originalUrl) throw new Error('Texture URL not provided')

    const url = resolveAssetUrl(originalUrl)

    if (this.textureCache.has(url)) {
      return this.textureCache.get(url)!
    }

    return new Promise((resolve, reject) => {
      new THREE.TextureLoader().load(
        url,
        (t) => {
          t.magFilter = THREE.NearestFilter
          t.minFilter = THREE.NearestFilter
          t.colorSpace = THREE.SRGBColorSpace
          this.textureCache.set(url, t)
          resolve(t)
        },
        undefined,
        reject
      )
    })
  }

  async getAnimations(): Promise<Map<string, any>> {
    const animations = new Map<string, any>()

    if (this.config.animation && Array.isArray(this.config.animation)) {
      for (const path of this.config.animation) {
        try {
          const url = resolveAssetUrl(path)
          const res = await fetch(url)
          const json = await res.json()
          if (json.animations) {
            Object.entries(json.animations).forEach(([key, value]) => {
              animations.set(key, value)
            })
          }
        } catch (e) {
          console.warn(`加载动画失败: ${path}`, e)
        }
      }
    }

    return animations
  }
}
