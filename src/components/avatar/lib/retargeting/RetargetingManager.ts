import * as THREE from 'three'
import { IRetargetingMap, StandardBones } from './RetargetingConfig'

interface InitialTransform {
  pos: THREE.Vector3
  rot: THREE.Quaternion
  euler: THREE.Euler
  scale: THREE.Vector3
}

// 预定义的骨骼别名映射（用于模糊匹配）
const BONE_ALIASES: Record<string, string[]> = {
  [StandardBones.Head]: ['AllHead', 'head', 'HeadBone'],
  [StandardBones.Body]: ['UpperBody', 'Torso', 'AllBody', 'body', 'BodyBone'],
  [StandardBones.Root]: ['root', 'RootBone', 'Origin'],
  [StandardBones.LeftArm]: ['LeftArm', 'ArmL', 'arm_left', 'Left_Arm'],
  [StandardBones.RightArm]: ['RightArm', 'ArmR', 'arm_right', 'Right_Arm'],
  [StandardBones.LeftLeg]: ['LeftLeg', 'LegL', 'leg_left', 'Left_Leg'],
  [StandardBones.RightLeg]: ['RightLeg', 'LegR', 'leg_right', 'Right_Leg'],
  [StandardBones.Mouth]: ['Mouth', 'mouth', 'Jaw', 'jaw'],
  [StandardBones.EyeBrow]: ['EyeBrow', 'eyebrow', 'Eyebrow', 'Brow'],
  [StandardBones.LeftEye]: ['LeftEye', 'EyeL', 'eye_left'],
  [StandardBones.RightEye]: ['RightEye', 'EyeR', 'eye_right']
}

/**
 * 标准化骨骼名称（用于模糊匹配）
 */
function normalizeBoneName(name: string): string {
  return name.toLowerCase().replace(/[_\-\s]/g, '')
}

/**
 * 骨骼重定向管理器
 * 负责在运行时将标准动画数据应用到特定模型的骨骼上
 */
export class RetargetingManager {
  private boneMap: Map<string, THREE.Object3D> = new Map()
  private initialTransforms: Map<string, InitialTransform> = new Map()
  private config: IRetargetingMap | null = null
  private modelRoot: THREE.Object3D | null = null
  private allBoneNames: string[] = [] // 缓存所有骨骼名称用于模糊匹配
  private customAliases: Map<string, string[]> = new Map() // 适配器注册的自定义别名

  /**
   * 注册自定义骨骼别名
   * 允许适配器为特定模型注册额外的别名映射
   */
  registerAliases(standardName: string, aliases: string[]) {
    this.customAliases.set(standardName, aliases)
  }

  /**
   * 模糊查找骨骼
   * 尝试通过多种方式匹配骨骼名称
   */
  private fuzzyFindBone(targetName: string): THREE.Object3D | null {
    if (!this.modelRoot) return null

    // 1. 精确匹配
    const exact = this.modelRoot.getObjectByName(targetName)
    if (exact) return exact

    // 2. 标准化后的模糊匹配（去除下划线、连字符、空格后比较）
    const normalizedTarget = normalizeBoneName(targetName)
    for (const boneName of this.allBoneNames) {
      if (normalizeBoneName(boneName) === normalizedTarget) {
        const bone = this.modelRoot.getObjectByName(boneName)
        if (bone) return bone
      }
    }

    // 注意：移除了过于宽松的"包含匹配"
    // 之前的问题：endermanhead.includes('head') 会错误匹配到 Head
    // 如果动画骨骼在模型中不存在，应该直接跳过而不是错误映射

    return null
  }

  /**
   * 初始化骨骼映射
   * @param modelRoot 模型根节点
   * @param config 重定向配置
   */
  init(modelRoot: THREE.Object3D, config: IRetargetingMap) {
    this.config = config
    this.modelRoot = modelRoot
    this.boneMap.clear()
    this.initialTransforms.clear()
    this.allBoneNames = []

    // 预缓存所有骨骼名称
    modelRoot.traverse((obj) => {
      if (obj.name) {
        this.allBoneNames.push(obj.name)
      }
    })

    // 预先查找并缓存所有需要的骨骼
    // 1. 从配置映射中加载
    for (const [standardName, targetName] of Object.entries(config.mapping)) {
      this.findAndCacheBone(modelRoot, standardName, targetName)
    }

    // 2. 自动回退机制 (Fallback)
    // 对于配置中未定义的标准骨骼，尝试多种查找方式
    for (const key of Object.keys(StandardBones)) {
      const standardName = StandardBones[key as keyof typeof StandardBones]
      if (!this.boneMap.has(standardName)) {
        // a. 尝试直接查找 standardName
        if (this.findAndCacheBone(modelRoot, standardName, standardName)) continue

        // b. 尝试预定义别名
        const aliases = BONE_ALIASES[standardName] || []
        let found = false
        for (const alias of aliases) {
          if (this.findAndCacheBone(modelRoot, standardName, alias)) {
            found = true
            break
          }
        }
        if (found) continue

        // c. 尝试自定义别名（由适配器注册）
        const customAliases = this.customAliases.get(standardName) || []
        for (const alias of customAliases) {
          if (this.findAndCacheBone(modelRoot, standardName, alias)) {
            found = true
            break
          }
        }
        if (found) continue

        // d. 尝试模糊查找
        const fuzzyBone = this.fuzzyFindBone(standardName)
        if (fuzzyBone) {
          this.boneMap.set(standardName, fuzzyBone)
          this.cacheInitialTransform(standardName, fuzzyBone)
        }
      }
    }

    // 3. 预缓存所有模型骨骼的初始变换
    // 这确保动态查找的骨骼（如 Left_ear, Right_ear）在动画修改前就有正确的初始状态
    modelRoot.traverse((obj) => {
      if (obj.name && !this.initialTransforms.has(obj.name)) {
        this.initialTransforms.set(obj.name, {
          pos: obj.position.clone(),
          rot: obj.quaternion.clone(),
          euler: obj.rotation.clone(),
          scale: obj.scale.clone()
        })
      }
    })
  }

  /**
   * 缓存骨骼的初始变换
   */
  private cacheInitialTransform(name: string, bone: THREE.Object3D) {
    this.initialTransforms.set(name, {
      pos: bone.position.clone(),
      rot: bone.quaternion.clone(),
      euler: bone.rotation.clone(),
      scale: bone.scale.clone()
    })
  }

  /**
   * 查找并缓存骨骼
   * @returns 是否成功找到
   */
  private findAndCacheBone(
    modelRoot: THREE.Object3D,
    standardName: string,
    targetName: string
  ): boolean {
    const bone = modelRoot.getObjectByName(targetName)
    if (bone) {
      this.boneMap.set(standardName, bone)
      this.initialTransforms.set(standardName, {
        pos: bone.position.clone(),
        rot: bone.quaternion.clone(),
        euler: bone.rotation.clone(),
        scale: bone.scale.clone()
      })
      return true
    }
    return false
  }

  /**
   * 获取标准骨骼对应的实际对象
   * @param standardName 标准骨骼名称
   */
  getBone(standardName: string): THREE.Object3D | undefined {
    const cached = this.boneMap.get(standardName)
    if (cached) return cached

    // 动态查找：对于未预先映射的骨骼，使用模糊查找
    if (this.modelRoot) {
      // 1. 精确查找
      let bone = this.modelRoot.getObjectByName(standardName)

      // 2. 模糊查找
      if (!bone) {
        bone = this.fuzzyFindBone(standardName) ?? undefined
      }

      if (bone) {
        this.boneMap.set(standardName, bone)
        // 只在初始变换不存在时才缓存，避免覆盖预缓存的正确初始状态
        if (!this.initialTransforms.has(standardName)) {
          this.cacheInitialTransform(standardName, bone)
        }
        return bone
      }
    }

    return undefined
  }

  /**
   * 获取所有已映射的骨骼名称
   */
  getMappedBoneNames(): string[] {
    return Array.from(this.boneMap.keys())
  }

  /**
   * 检查骨骼是否已映射
   */
  hasBone(standardName: string): boolean {
    return this.boneMap.has(standardName) || !!this.fuzzyFindBone(standardName)
  }

  /**
   * 获取骨骼的初始旋转（四元数）
   * @param standardName 标准骨骼名称
   * @returns 初始四元数，如果不存在则返回单位四元数
   */
  getInitialRotation(standardName: string): THREE.Quaternion {
    const init = this.initialTransforms.get(standardName)
    return init ? init.rot.clone() : new THREE.Quaternion()
  }

  /**
   * 获取骨骼的初始旋转（欧拉角，ZXY 顺序）
   * 直接返回缓存的欧拉角，避免四元数转换带来的角度歧义
   * @param standardName 标准骨骼名称
   * @returns 初始欧拉角，如果不存在则返回零欧拉角
   */
  getInitialEuler(standardName: string): THREE.Euler {
    const init = this.initialTransforms.get(standardName)
    return init ? init.euler.clone() : new THREE.Euler(0, 0, 0, 'ZXY')
  }

  /**
   * 应用旋转到标准骨骼
   * @param standardName 标准骨骼名称
   * @param rotation 欧拉角或四元数
   */
  applyRotation(standardName: string, rotation: THREE.Euler | THREE.Quaternion) {
    const bone = this.getBone(standardName)
    if (!bone) return

    if (rotation instanceof THREE.Euler) {
      bone.rotation.copy(rotation)
    } else {
      bone.quaternion.copy(rotation)
    }

    // 应用姿态修正 (如果有)
    const restPoseCorrection = this.config?.restPoseCorrection
    if (restPoseCorrection && restPoseCorrection[standardName]) {
      const correction = restPoseCorrection[standardName]
      bone.rotation.x += correction[0]
      bone.rotation.y += correction[1]
      bone.rotation.z += correction[2]
    }
  }

  /**
   * 应用位置到标准骨骼
   * @param standardName 标准骨骼名称
   * @param position 位置向量
   */
  applyPosition(standardName: string, position: THREE.Vector3 | [number, number, number]) {
    const bone = this.getBone(standardName)
    if (!bone) return

    // 注意：Bedrock 动画中的位置通常是相对于初始位置的偏移
    // 或者是绝对位置？这取决于动画文件的定义。通常是相对偏移。
    // 如果是相对偏移，我们需要知道初始位置。

    // 暂时简单实现为直接设置（假设是绝对值或已包含初始值）
    // TODO: 实现初始位置缓存和相对偏移逻辑
    if (Array.isArray(position)) {
      bone.position.set(position[0], position[1], position[2])
    } else {
      bone.position.copy(position)
    }
  }

  /**
   * 应用缩放到标准骨骼
   * @param standardName 标准骨骼名称
   * @param scale 缩放向量
   */
  applyScale(standardName: string, scale: THREE.Vector3 | [number, number, number]) {
    const bone = this.getBone(standardName)
    if (!bone) return

    if (Array.isArray(scale)) {
      bone.scale.set(scale[0], scale[1], scale[2])
    } else {
      bone.scale.copy(scale)
    }
  }

  /**
   * 重置所有骨骼到初始状态
   */
  reset() {
    // 遍历所有已缓存的初始变换，重置对应的骨骼
    this.initialTransforms.forEach((init, name) => {
      // 首先尝试从 boneMap 获取
      let bone = this.boneMap.get(name)
      // 如果不在 boneMap 中，尝试从模型中直接查找
      if (!bone && this.modelRoot) {
        bone = this.modelRoot.getObjectByName(name)
      }
      if (bone) {
        bone.position.copy(init.pos)
        // 使用欧拉角重置而不是四元数，以保持正确的旋转顺序 (ZXY)
        bone.rotation.copy(init.euler)
        bone.scale.copy(init.scale)
      }
    })
  }
}
