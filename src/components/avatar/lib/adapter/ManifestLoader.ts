import { IAvatarManifest, FeatureButton, PartDefinition } from './IAvatarManifest'
import { IRetargetingMap } from '../retargeting/RetargetingConfig'
import { resolveAssetUrl } from '../../../../utils/assetUrl'

/**
 * Manifest 加载器
 * 用于从不同来源加载模型配置清单
 */
export class ManifestLoader {
  /**
   * 从 JSON 文件加载 Manifest
   * @param path JSON 文件路径
   */
  static async fromJson(path: string): Promise<IAvatarManifest> {
    const url = resolveAssetUrl(path)
    const response = await fetch(url)
    if (!response.ok) {
      throw new Error(`加载 Manifest 失败: ${path}`)
    }
    const manifest = await response.json()
    return ManifestLoader.validate(manifest)
  }

  /**
   * 从 .pero 文件加载 Manifest
   * .pero 文件的元数据段包含 Manifest 信息
   * @param path .pero 文件路径
   * @param decryptor 解密函数（可选，用于安全加载）
   */
  static async fromPero(
    path: string,
    decryptor?: (data: ArrayBuffer) => Promise<IAvatarManifest>
  ): Promise<IAvatarManifest> {
    if (decryptor) {
      const url = resolveAssetUrl(path)
      const response = await fetch(url)
      const data = await response.arrayBuffer()
      return decryptor(data)
    }

    throw new Error('加载 .pero Manifest 需要提供解密器')
  }

  /**
   * 验证 Manifest 结构完整性
   * @param manifest 待验证的 Manifest 对象
   */
  static validate(manifest: any): IAvatarManifest {
    if (!manifest.metadata) {
      throw new Error('Manifest 缺少 metadata 字段')
    }
    if (!manifest.metadata.name) {
      throw new Error('Manifest metadata 缺少 name 字段')
    }
    if (!manifest.resources) {
      throw new Error('Manifest 缺少 resources 字段')
    }
    if (!manifest.resources.model) {
      throw new Error('Manifest resources 缺少 model 字段')
    }
    if (!manifest.resources.texture) {
      throw new Error('Manifest resources 缺少 texture 字段')
    }
    if (!manifest.retargetingMap) {
      console.warn('Manifest 缺少 retargetingMap，将使用空映射')
      manifest.retargetingMap = { mapping: {} }
    }
    if (!manifest.featureButtons) {
      console.warn('Manifest 缺少 featureButtons，将使用空数组')
      manifest.featureButtons = []
    }

    return manifest as IAvatarManifest
  }

  /**
   * 从适配器获取的 Manifest 片段构建完整 Manifest
   * 用于兼容旧的适配器模式
   * @param adapterManifest 适配器提供的 Manifest 片段
   * @param resources 资源路径配置
   */
  static buildFromAdapter(
    adapterManifest: Partial<IAvatarManifest>,
    resources: {
      model: string
      texture: string
      animations?: string[]
      animation_controllers?: string | string[]
    }
  ): IAvatarManifest {
    return {
      metadata: adapterManifest.metadata || {
        name: 'Unknown',
        version: '1.0.0'
      },
      featureButtons: adapterManifest.featureButtons || [],
      parts: adapterManifest.parts || [],
      retargetingMap: adapterManifest.retargetingMap || { mapping: {} },
      resources: {
        model: resources.model,
        texture: resources.texture,
        animations: resources.animations
      },
      animation_controllers: resources.animation_controllers
    } as IAvatarManifest & { animation_controllers?: string | string[] }
  }
}

/**
 * 扩展 IAvatarManifest 以支持控制器配置
 */
declare module './IAvatarManifest' {
  interface IAvatarManifest {
    animation_controllers?: string | string[]
  }
}
