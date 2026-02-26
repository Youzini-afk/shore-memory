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
// @ts-ignore
// Native module access via IPC now
// const native = window.require ? window.require('../../native') : { loadPeroModel: () => { console.error('Native module not loaded'); return { bones: [] }; } }
// const { loadPeroModel } = native

/**
 * 安全模型提供者 (Rust Native)
 * 用于加载加密的 .pero 模型文件
 */
export class PeroSecureProvider implements IModelProvider {
  private config: any
  private textureCache = new Map<string, THREE.Texture>()
  private boneFilterPatterns: string[]
  private defaultKey = new TextEncoder().encode('12345678901234567890123456789012')

  constructor(config: any, boneFilterPatterns?: string[]) {
    this.config = config
    this.boneFilterPatterns = boneFilterPatterns || DEFAULT_BONE_FILTER_PATTERNS
  }

  // 辅助函数：十六进制字符串转 Uint8Array
  private hexToBytes(hex: string): Uint8Array {
    const bytes = new Uint8Array(hex.length / 2)
    for (let i = 0; i < hex.length; i += 2) {
      bytes[i / 2] = parseInt(hex.substring(i, i + 2), 16)
    }
    return bytes
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
      const response = await fetch(modelUrl)
      if (!response.ok) throw new Error(`Failed to load secure model: ${modelUrl}`)
      const arrayBuffer = await response.arrayBuffer()

      // 2. 获取解密密钥
      // 优先使用配置中的密钥，否则使用默认密钥
      // Priority: Config key > Default key
      let key: Uint8Array = this.defaultKey
      if (this.config.key) {
        if (typeof this.config.key === 'string') {
          key = this.hexToBytes(this.config.key) // Assume hex string if string
        } else if (this.config.key instanceof Uint8Array) {
          key = this.config.key
        }
      }

      // 3. 调用 Native 模块解密并解析 (通过 IPC)
      console.time('Rust Decrypt & Parse')
      // @ts-ignore
      const parsedData = await window.electron.loadPeroModel(new Uint8Array(arrayBuffer), key)
      console.timeEnd('Rust Decrypt & Parse')

      // 4. 转换/适配数据
      // Rust 返回的数据结构已经匹配 ParsedModelData 接口 (在 parser.rs 中定义)
      // 但我们需要处理 adapter 逻辑 (如果需要过滤骨骼)

      let bones = parsedData.bones

      bones.forEach((b: any) => {
        if (b.cubesJson && !b.cubes) {
          try {
            b.cubes = JSON.parse(b.cubesJson)
          } catch (e) {
            console.error(`解析骨骼 ${b.name} 的 cubesJson 失败:`, e)
          }
        }
      })

      bones = this.filterBones(bones)
      parsedData.bones = bones

      return parsedData
    } catch (e) {
      console.error('Failed to load/decrypt secure model:', e)
      throw e
    }
  }

  async getTexture(): Promise<THREE.Texture> {
    const url = this.config.texture
    if (!url) throw new Error('Texture URL not provided')

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
    // 动画数据目前仍假设为 JSON
    // 未来也可以加密
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
