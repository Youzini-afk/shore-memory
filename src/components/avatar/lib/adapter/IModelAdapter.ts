import * as THREE from 'three'
import { IRetargetingMap } from '../retargeting/RetargetingConfig'
import { FeatureButton, PartDefinition, IAvatarManifest } from './IAvatarManifest'

/**
 * 模型适配器接口
 * 用于封装不同模型的特定逻辑，如骨骼过滤、部件可见性控制等
 */
export interface IModelAdapter {
  /**
   * 适配器名称
   */
  name: string

  /**
   * 判断是否适用于该模型路径
   * @param modelPath 模型文件路径
   */
  canHandle(modelPath: string): boolean

  /**
   * 过滤骨骼数据
   * 在模型加载前调用，用于移除不需要的骨骼（如 GUI、辅助骨骼）
   * @param bones 原始骨骼数据数组
   * @returns 过滤后的骨骼数据数组
   */
  filterBones(bones: any[]): any[]

  /**
   * 应用服装/部件状态
   * @param scene 模型根节点
   * @param state 服装状态对象
   */
  applyClothingState(scene: THREE.Object3D, state: any): void

  /**
   * 获取重定向配置
   * 允许适配器提供特定模型的骨骼映射
   */
  getRetargetingConfig(): IRetargetingMap

  /**
   * 获取功能按钮列表
   * 用于 UI 动态生成控制面板
   * @returns 功能按钮定义数组
   */
  getFeatureButtons?(): FeatureButton[]

  /**
   * 获取部件定义列表
   * 声明模型中可控制的部件及其对应的网格
   * @returns 部件定义数组
   */
  getParts?(): PartDefinition[]

  /**
   * 获取完整的清单配置
   * 用于从适配器获取所有配置信息
   * @returns 头像清单对象（不含资源路径）
   */
  getManifest?(): Partial<IAvatarManifest>
}
