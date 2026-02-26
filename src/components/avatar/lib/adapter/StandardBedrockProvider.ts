import * as THREE from 'three'
import { IModelProvider, ParsedModelData, ParsedBone } from './IModelProvider'

const DEFAULT_BONE_FILTER_PATTERNS = [
  'GUI',
  'Hud',
  'Panel',
  'Button',
  'Text',
  'Start',
  'End',
  'background',
  'molang'
]

/**
 * 标准 Bedrock JSON 提供者
 * 用于加载普通的 .json 模型文件
 */
export class StandardBedrockProvider implements IModelProvider {
  private config: any
  private textureCache = new Map<string, THREE.Texture>()
  private boneFilterPatterns: string[]

  constructor(config: any, boneFilterPatterns?: string[]) {
    this.config = config
    this.boneFilterPatterns = boneFilterPatterns || DEFAULT_BONE_FILTER_PATTERNS
  }

  async getManifest(): Promise<any> {
    return {
      name: this.config.name,
      version: '1.0.0'
    }
  }

  async getModelData(): Promise<ParsedModelData> {
    const response = await fetch(this.config.model)
    if (!response.ok) throw new Error(`Failed to load model: ${this.config.model}`)
    const json = await response.json()

    // 适配器过滤逻辑 (Legacy Support)
    const geometries = json['minecraft:geometry'] || []
    let allBones: any[] = []
    let firstDesc: any = null

    geometries.forEach((geo: any) => {
      if (geo.bones) {
        allBones = allBones.concat(geo.bones)
      }
      if (!firstDesc && geo.description) {
        firstDesc = geo.description
      }
    })

    allBones = this.filterBones(allBones)

    // 转换为统一格式
    const parsedBones: ParsedBone[] = allBones.map((b: any) => ({
      name: b.name,
      parent: b.parent,
      pivot: b.pivot || [0, 0, 0],
      rotation: b.rotation,
      cubes: b.cubes
    }))

    const desc = firstDesc || { texture_width: 64, texture_height: 64 }
    return {
      textureWidth: desc.texture_width,
      textureHeight: desc.texture_height,
      bones: parsedBones
    }
  }

  async getTexture(): Promise<THREE.Texture> {
    const url = this.config.texture
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
          const res = await fetch(path)
          const json = await res.json()
          if (json.animations) {
            Object.entries(json.animations).forEach(([key, value]) => {
              animations.set(key, value)
            })
          }
        } catch (e) {
          console.warn(`Failed to load animation: ${path}`, e)
        }
      }
    }

    return animations
  }

  private filterBones(bones: any[]): any[] {
    return bones.filter((b: any) => {
      const name = b.name
      if (name === 'Start' || name === 'End') return false
      if (this.boneFilterPatterns.some((pattern: string) => name.includes(pattern))) return false
      return true
    })
  }
}
