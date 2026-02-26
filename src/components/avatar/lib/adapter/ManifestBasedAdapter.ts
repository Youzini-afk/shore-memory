import * as THREE from 'three'
import { IModelAdapter } from './IModelAdapter'
import { IAvatarManifest, FeatureButton, PartDefinition } from './IAvatarManifest'
import { IRetargetingMap } from '../retargeting/RetargetingConfig'

/**
 * 基于 Manifest 的通用模型适配器
 * 从 IAvatarManifest 动态生成适配器行为
 * 消除硬编码，实现模型配置的完全外部化
 */
export class ManifestBasedAdapter implements IModelAdapter {
  name: string
  private manifest: IAvatarManifest

  constructor(manifest: IAvatarManifest) {
    this.manifest = manifest
    this.name = manifest.metadata.name
  }

  /**
   * 获取原始 Manifest
   */
  getManifest(): IAvatarManifest {
    return this.manifest
  }

  /**
   * 判断是否适用于该模型路径
   * 基于模型名称匹配
   */
  canHandle(modelPath: string): boolean {
    const modelName = this.manifest.metadata.name.toLowerCase()
    return modelPath.toLowerCase().includes(modelName)
  }

  /**
   * 过滤骨骼数据
   * 从 Manifest 的配置中读取需要过滤的骨骼模式
   */
  filterBones(bones: any[]): any[] {
    const filterPatterns = this.manifest.boneFilterPatterns || [
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

    return bones.filter((b: any) => {
      const name = b.name
      if (name === 'Start' || name === 'End') return false
      if (filterPatterns.some((pattern: string) => name.includes(pattern))) return false
      return true
    })
  }

  /**
   * 应用服装/部件状态
   * 基于 Manifest 中的 parts 定义动态控制可见性
   */
  applyClothingState(scene: THREE.Object3D, state: Record<string, boolean>): void {
    const parts = this.manifest.parts || []
    const shyParts = this.manifest.shyParts || []

    const isShy = this.calculateShyState(state)

    scene.traverse((child: any) => {
      const name = child.name
      if (!name) return

      let handled = false

      for (const part of parts) {
        if (part.meshes.some((meshName) => name.includes(meshName) || name === meshName)) {
          child.visible = state[part.id] ?? part.defaultVisible ?? true
          handled = true
          break
        }
      }

      if (!handled && shyParts.length > 0) {
        for (const shyPart of shyParts) {
          if (name.includes(shyPart.meshPattern)) {
            child.visible = isShy

            if (shyPart.zOffset && child.position.z > shyPart.zThreshold) {
              child.position.z += shyPart.zOffset
            }
          }
        }
      }
    })
  }

  /**
   * 计算害羞状态
   * 基于 Manifest 中的 shyTriggerParts 配置
   */
  private calculateShyState(state: Record<string, boolean>): boolean {
    const triggers = this.manifest.shyTriggerParts || []
    return triggers.some((partId) => state[partId] === false)
  }

  /**
   * 获取重定向配置
   */
  getRetargetingConfig(): IRetargetingMap {
    return this.manifest.retargetingMap
  }

  /**
   * 获取功能按钮列表
   */
  getFeatureButtons(): FeatureButton[] {
    return this.manifest.featureButtons || []
  }

  /**
   * 获取部件定义列表
   */
  getParts(): PartDefinition[] {
    return this.manifest.parts || []
  }

  /**
   * 获取资源路径配置
   */
  getResources() {
    return this.manifest.resources
  }
}

/**
 * 扩展 IAvatarManifest 接口以支持更多配置
 */
declare module './IAvatarManifest' {
  interface IAvatarManifest {
    boneFilterPatterns?: string[]
    shyParts?: Array<{
      meshPattern: string
      zOffset?: number
      zThreshold?: number
    }>
    shyTriggerParts?: string[]
    animation_controllers?: string | string[]
  }
}
