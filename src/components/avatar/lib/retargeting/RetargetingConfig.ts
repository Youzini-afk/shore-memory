/**
 * 骨骼重定向配置接口
 * 用于定义标准骨骼与特定模型骨骼的映射关系
 */
export interface IRetargetingMap {
  /**
   * 映射表
   * Key: 标准骨骼名称 (如 'Head', 'LeftArm')
   * Value: 目标模型中的实际骨骼名称 (如 'head_bone', 'l_arm')
   */
  mapping: Record<string, string>

  /**
   * 默认姿态修正 (T-Pose -> A-Pose 等)
   * Key: 骨骼名称
   * Value: [x, y, z] 旋转角度修正 (弧度)
   */
  restPoseCorrection?: Record<string, [number, number, number]>
}

/**
 * 标准骨骼名称定义
 * 所有动画和逻辑应基于这些标准名称编写
 */
export const StandardBones = {
  Root: 'Root',
  Body: 'Body',
  Head: 'Head',
  LeftArm: 'LeftArm',
  RightArm: 'RightArm',
  LeftLeg: 'LeftLeg',
  RightLeg: 'RightLeg',
  // 面部交互
  Mouth: 'Mouth',
  EyeBrow: 'EyeBrow',
  LeftEye: 'LeftEye',
  RightEye: 'RightEye'
  // ... 可以根据需要扩展更多标准骨骼
}
