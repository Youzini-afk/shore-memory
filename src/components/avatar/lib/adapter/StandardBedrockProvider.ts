import * as THREE from 'three'
import { IModelProvider, ParsedModelData } from './IModelProvider'
import { resolveAssetUrl } from '../../../../utils/assetUrl'

/**
 * 标准 Bedrock JSON 提供者
 * 用于加载普通的 .json 模型文件
 */
export class StandardBedrockProvider implements IModelProvider {
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
      version: '1.0.0'
    }
  }

  async getModelData(): Promise<ParsedModelData> {
    const url = resolveAssetUrl(this.config.model)
    const response = await fetch(url)
    if (!response.ok) throw new Error(`Failed to load model: ${this.config.model}`)
    const arrayBuffer = await response.arrayBuffer()

    // 调用 Native 模块解析并生成几何体 (通过 IPC)
    // 直接返回解析后的对象，不再需要前端解包
    // @ts-ignore
    const parsedData = await window.electron.loadStandardModel(
      new Uint8Array(arrayBuffer),
      this.boneFilterPatterns
    )

    return parsedData
  }

  async getTexture(): Promise<THREE.Texture> {
    const url = resolveAssetUrl(this.config.texture)
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

    // 如果配置中有动画列表
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
