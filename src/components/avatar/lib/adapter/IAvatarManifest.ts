import { IRetargetingMap } from '../retargeting/RetargetingConfig'

/**
 * 功能按钮定义
 * 用于 UI 动态生成控制按钮
 */
export interface FeatureButton {
  /**
   * 功能唯一标识符
   * 用于在状态对象中查找对应的布尔值
   */
  id: string

  /**
   * 显示名称（支持多语言）
   */
  label: string

  /**
   * 按钮图标（可选）
   */
  icon?: string

  /**
   * 所属分组（可选，用于 UI 分类）
   */
  group?: string

  /**
   * 默认状态
   */
  defaultValue?: boolean
}

/**
 * 部件定义
 * 用于声明模型中可控制的部件
 */
export interface PartDefinition {
  /**
   * 部件唯一标识符
   */
  id: string

  /**
   * 对应的网格名称列表
   */
  meshes: string[]

  /**
   * 是否默认可见
   */
  defaultVisible?: boolean
}

/**
 * 模型元数据
 */
export interface AvatarMetadata {
  /**
   * 模型名称
   */
  name: string

  /**
   * 模型版本
   */
  version?: string

  /**
   * 作者信息
   */
  author?: string

  /**
   * 模型描述
   */
  description?: string

  /**
   * 缩略图路径（可选）
   */
  thumbnail?: string
}

/**
 * 害羞部件配置
 * 用于定义在特定状态下触发的部件行为
 */
export interface ShyPartConfig {
  meshPattern: string
  zOffset?: number
  zThreshold?: number
}

/**
 * 头像清单接口
 * 定义模型的所有配置信息
 * 未来将打包进 .pero 文件
 */
export interface IAvatarManifest {
  metadata: AvatarMetadata
  featureButtons: FeatureButton[]
  parts?: PartDefinition[]
  retargetingMap: IRetargetingMap

  resources: {
    model: string
    texture: string
    animations?: string[]
  }

  boneFilterPatterns?: string[]
  shyParts?: ShyPartConfig[]
  shyTriggerParts?: string[]
  animation_controllers?: string | string[]
}
