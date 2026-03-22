import * as THREE from 'three'

/**
 * 统一的模型数据结构
 * 对应 Rust Native 模块输出的 ParsedModelData
 */
export interface ParsedModelData {
  textureWidth: number
  textureHeight: number
  bones: ParsedBone[]
}

export interface ParsedBone {
  name: string
  parent?: string
  pivot: number[] // [number, number, number] but flexibility for Float64Array from Rust
  rotation?: number[]
  // 几何数据 (可选，如果为空则需要从 cubes 生成)
  // 几何体数据（可选，为空时从 cubes 生成）
  vertices?: Float32Array
  uvs?: Float32Array
  indices?: Uint16Array
  // 原始 Cube 数据 (用于未预计算几何体的情况)
  cubes?: any[]
  // Rust 返回的 JSON 字符串形式的 Cube 数据
  cubesJson?: string
}

/**
 * 模型提供者接口
 * 负责从不同来源 (JSON, .pero, Blockbench) 获取统一的数据结构
 */
export interface IModelProvider {
  /**
   * 获取模型清单/元数据
   */
  getManifest(): Promise<any>

  /**
   * 获取解析后的几何数据
   */
  getModelData(): Promise<ParsedModelData>

  /**
   * 获取纹理
   */
  getTexture(): Promise<THREE.Texture>

  /**
   * 获取动画数据
   */
  getAnimations(): Promise<Map<string, any>>

  /**
   * 获取动画控制器
   */
  getAnimationControllers?(): Promise<Map<string, any>>
}
