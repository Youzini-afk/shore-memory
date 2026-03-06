import * as THREE from 'three'
import {
  IModelProvider,
  ParsedModelData
} from '../../../src/components/avatar/lib/adapter/IModelProvider'

/**
 * 专门为 Wiki 演示设计的模型提供者
 * 不依赖于 Electron 环境，在浏览器中直接解析 Bedrock JSON
 */
export class WikiModelProvider implements IModelProvider {
  private config: any
  private textureCache = new Map<string, THREE.Texture>()

  constructor(config: any) {
    this.config = config
  }

  async getManifest(): Promise<any> {
    return {
      name: this.config.name,
      version: '1.0.0'
    }
  }

  async getModelData(): Promise<ParsedModelData> {
    const response = await fetch(this.config.model)
    if (!response.ok) throw new Error(`加载模型失败: ${this.config.model}`)
    const json = await response.json()

    let geo: any = null

    // 兼容新版 minecraft:geometry 格式 (数组)
    if (json['minecraft:geometry'] && Array.isArray(json['minecraft:geometry'])) {
      geo = json['minecraft:geometry'][0]
    } else {
      // 兼容旧版 geometry.xxx 格式
      const geometryName = Object.keys(json).find((k) => k.startsWith('geometry.'))
      if (geometryName) {
        geo = json[geometryName]
      }
    }

    if (!geo) throw new Error('无效的 Bedrock 模型文件：未找到 geometry 数据')

    // 处理数据结构差异
    const description = geo.description || {}

    // 转换为 ParsedModelData 结构
    return {
      textureWidth: description.texture_width || geo.texturewidth || 64,
      textureHeight: description.texture_height || geo.textureheight || 64,
      bones: geo.bones.map((bone: any) => ({
        name: bone.name,
        parent: bone.parent,
        pivot: bone.pivot || [0, 0, 0],
        rotation: bone.rotation,
        cubes: bone.cubes
      }))
    }
  }

  async getTexture(): Promise<THREE.Texture> {
    if (this.textureCache.has(this.config.texture)) {
      return this.textureCache.get(this.config.texture)!
    }

    return new Promise((resolve, reject) => {
      new THREE.TextureLoader().load(
        this.config.texture,
        (t) => {
          t.magFilter = THREE.NearestFilter
          t.minFilter = THREE.NearestFilter
          t.colorSpace = THREE.SRGBColorSpace
          this.textureCache.set(this.config.texture, t)
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
          const res = await fetch(path)
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
