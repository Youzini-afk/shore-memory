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
    // [调试开关] 设为 true 强制走 JS 路径（跳过 Rust），用于排查渲染问题
    const FORCE_JS_PATH = false

    const url = resolveAssetUrl(this.config.model)
    const response = await fetch(url)
    if (!response.ok) throw new Error(`Failed to load model: ${this.config.model}`)
    const arrayBuffer = await response.arrayBuffer()

    // 优先尝试 Rust Native 模块解析（高性能路径）
    // @ts-ignore
    if (!FORCE_JS_PATH && window.electron?.loadStandardModel) {
      try {
        // @ts-ignore
        const parsedData = await window.electron.loadStandardModel(
          new Uint8Array(arrayBuffer),
          this.boneFilterPatterns
        )
        return parsedData
      } catch (e) {
        console.warn('[StandardBedrockProvider] Rust 解析失败，回退到 JS 路径:', e)
      }
    }

    // JS 回退路径：直接解析 Bedrock JSON，返回 cubes 数据供 AvatarRenderer 处理
    console.log('[StandardBedrockProvider] 使用 JS 路径解析模型')
    const jsonStr = new TextDecoder().decode(arrayBuffer)
    const json = JSON.parse(jsonStr)

    const geometry = json['minecraft:geometry']?.[0]
    if (!geometry) throw new Error('Invalid Bedrock model: missing minecraft:geometry')

    const desc = geometry.description || {}
    const textureWidth = desc.texture_width || 64
    const textureHeight = desc.texture_height || 64

    const filterPatterns = this.boneFilterPatterns || []
    const bones = (geometry.bones || [])
      .filter((b: any) => {
        if (filterPatterns.length === 0) return true
        return !filterPatterns.some((pattern: string) =>
          b.name.toLowerCase().includes(pattern.toLowerCase())
        )
      })
      .map((b: any) => ({
        name: b.name,
        parent: b.parent,
        pivot: b.pivot || [0, 0, 0],
        rotation: b.rotation,
        cubes: b.cubes || []
        // 注意：不提供 vertices/uvs/indices，让 AvatarRenderer 的 JS 回退路径处理
      }))

    return { textureWidth, textureHeight, bones }
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
