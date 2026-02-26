import * as THREE from 'three'
import { IModelProvider, ParsedModelData, ParsedBone } from './adapter/IModelProvider'

/**
 * 虚拟人渲染器
 * 负责将 IModelProvider 提供的数据转换为 Three.js 场景对象
 * Replaces the old BedrockLoader with a cleaner architecture
 */
export class AvatarRenderer {
  boneMap: Map<string, THREE.Group[]> = new Map()
  textureWidth: number = 64
  textureHeight: number = 64

  /**
   * 从 Provider 构建场景
   */
  async build(provider: IModelProvider): Promise<THREE.Group> {
    this.boneMap.clear()
    const rootGroup = new THREE.Group()

    // 1. 获取所有数据
    // 并行获取以提高速度
    const [modelData, texture] = await Promise.all([provider.getModelData(), provider.getTexture()])

    this.textureWidth = modelData.textureWidth
    this.textureHeight = modelData.textureHeight

    // 2. 创建材质
    const material = new THREE.MeshStandardMaterial({
      map: texture,
      alphaTest: 0.5,
      side: THREE.DoubleSide, // 强制双面渲染，解决法线反向问题
      roughness: 0.4,
      metalness: 0.1,
      emissive: 0x000000,
      emissiveIntensity: 0
    })

    // 3. 构建骨骼层级
    this.buildSkeleton(modelData.bones, rootGroup, material)

    // Bedrock 根骨骼通常需要绕 Y 轴旋转 180 度适配 Three.js 坐标系
    rootGroup.rotation.y = Math.PI
    // 移除全局 scale(-1, 1, 1)，改为在底层坐标计算中处理镜像，防止贴图错误
    rootGroup.scale.set(1, 1, 1)

    return rootGroup
  }

  private buildSkeleton(bones: ParsedBone[], rootGroup: THREE.Group, material: THREE.Material) {
    const localBoneMap = new Map<string, THREE.Group>()
    // 创建一个不区分大小写的映射用于查找
    const caseInsensitiveBoneMap = new Map<string, string>()

    // 预处理：第一遍扫描，创建所有骨骼对象
    // Pre-processing: Create all bone objects
    bones.forEach((boneData) => {
      // 1. 解析 cubesJson (Rust 兼容层)
      if (boneData.cubesJson && !boneData.cubes) {
        try {
          boneData.cubes = JSON.parse(boneData.cubesJson)
        } catch (e) {
          console.error(`Failed to parse cubesJson for bone ${boneData.name}`, e)
        }
      }

      const boneName = boneData.name
      const lowerName = boneName.toLowerCase()
      caseInsensitiveBoneMap.set(lowerName, boneName)

      let boneGroup: THREE.Group

      // 检查是否已经存在同名骨骼 (多部位共用骨骼的情况)
      if (localBoneMap.has(boneName)) {
        boneGroup = localBoneMap.get(boneName)!
      } else {
        boneGroup = new THREE.Group()
        boneGroup.name = boneName
        // 存储原始数据用于后续计算
        boneGroup.userData = {
          pivot: boneData.pivot,
          rotation: boneData.rotation,
          bindPose: {
            position: new THREE.Vector3(),
            quaternion: new THREE.Quaternion(),
            scale: new THREE.Vector3(1, 1, 1)
          }
        }

        localBoneMap.set(boneName, boneGroup)

        // 添加到全局骨骼映射
        if (!this.boneMap.has(boneName)) {
          this.boneMap.set(boneName, [])
        }
        this.boneMap.get(boneName)!.push(boneGroup)
      }
    })

    // 第二遍：建立父子关系和添加几何体
    // Second pass: Build hierarchy and add geometry
    const processedBones = new Set<string>()

    bones.forEach((boneData) => {
      const boneName = boneData.name
      const boneGroup = localBoneMap.get(boneName)!

      // 1. 设置父子关系和变换 (仅对每个骨骼名处理一次)
      if (!processedBones.has(boneName)) {
        if (boneData.parent) {
          const parentName = boneData.parent
          let parentGroup = localBoneMap.get(parentName)

          // 尝试不区分大小写的匹配
          if (!parentGroup) {
            const actualParentName = caseInsensitiveBoneMap.get(parentName.toLowerCase())
            if (actualParentName) {
              parentGroup = localBoneMap.get(actualParentName)
            }
          }

          if (parentGroup) {
            parentGroup.add(boneGroup)
          } else {
            // 孤儿骨骼，但有 parent 定义 (可能 parent 未在此次加载的骨骼列表中)
            // 暂时挂载到 root
            console.warn(`Parent bone ${boneData.parent} not found for ${boneData.name}`)
            rootGroup.add(boneGroup)
          }
        } else {
          // 根骨骼
          rootGroup.add(boneGroup)
        }

        // 2. 计算初始变换 (Bind Pose)
        // Bedrock Pivot 处理逻辑:
        // Bone Position = (Pivot - ParentPivot)

        let parentPivot = [0, 0, 0]
        if (boneData.parent) {
          const parentName = boneData.parent
          let parentBone = bones.find((b) => b.name === parentName)

          // 尝试不区分大小写的匹配
          if (!parentBone) {
            const lowerParentName = parentName.toLowerCase()
            parentBone = bones.find((b) => b.name.toLowerCase() === lowerParentName)
          }

          if (parentBone) {
            parentPivot = parentBone.pivot
          }
        }

        const pivot = boneData.pivot
        // 设置骨骼位置 (基岩版 X 轴与 Three.js 相反，需取反以维持层级结构)
        boneGroup.position.set(
          -(pivot[0] - parentPivot[0]),
          pivot[1] - parentPivot[1],
          pivot[2] - parentPivot[2]
        )

        // 设置骨骼旋转
        if (boneData.rotation) {
          const rot = boneData.rotation
          // Bedrock 旋转顺序是 ZXY
          boneGroup.rotation.order = 'ZXY'
          // X 轴取反后，Y 和 Z 的旋转方向需要反转以维持镜像后的正确朝向
          boneGroup.rotation.x = THREE.MathUtils.degToRad(-rot[0])
          boneGroup.rotation.y = THREE.MathUtils.degToRad(-rot[1])
          boneGroup.rotation.z = THREE.MathUtils.degToRad(rot[2])
        }

        // 保存 Bind Pose
        boneGroup.updateMatrix()
        boneGroup.userData.bindPose.position.copy(boneGroup.position)
        boneGroup.userData.bindPose.quaternion.copy(boneGroup.quaternion)
        boneGroup.userData.bindPose.scale.copy(boneGroup.scale)

        processedBones.add(boneName)
      }

      // 3. 生成几何体 (所有定义中的几何体都应该被添加)
      if (boneData.vertices && boneData.uvs && boneData.indices) {
        // 使用 Native Geometry (高性能路径)
        const geometry = new THREE.BufferGeometry()

        geometry.setAttribute('position', new THREE.BufferAttribute(boneData.vertices, 3))
        geometry.setAttribute('uv', new THREE.BufferAttribute(boneData.uvs, 2))
        geometry.setIndex(new THREE.BufferAttribute(boneData.indices, 1))

        // 自动计算法线 (因为 Rust 侧未生成法线)
        // 确保光照计算正确
        geometry.computeVertexNormals()

        const mesh = new THREE.Mesh(geometry, material)
        mesh.castShadow = true
        mesh.receiveShadow = true
        mesh.name = `${boneData.name}_Mesh`

        // Native geometry 已经在 Bone Local Space 中 (相对于 Pivot)
        // 所以直接添加到 Bone Group，位置为 (0,0,0)
        boneGroup.add(mesh)
      } else if (boneData.cubes && boneData.cubes.length > 0) {
        // 回退：使用 JS 侧 Cube 解析 (低性能路径)
        boneData.cubes.forEach((cubeData: any) => {
          this.addCubeToBone(boneGroup, cubeData, boneData.pivot, material)
        })
      }
    })
  }

  // 保留用于非 Native 数据源的回退支持
  private addCubeToBone(
    boneGroup: THREE.Group,
    cubeData: any,
    bonePivot: number[],
    material: THREE.Material
  ) {
    // Bedrock Cube 定义:
    // origin: [x, y, z] (方块左下角坐标)
    // size: [w, h, d]
    // pivot: [x, y, z] (方块旋转中心，可选)
    // rotation: [x, y, z] (方块旋转角度，可选)

    const size = cubeData.size || [0, 0, 0]
    const origin = cubeData.origin || [0, 0, 0]
    const inflate = cubeData.inflate || 0
    const mirror = cubeData.mirror || false

    // 创建几何体
    // Three.js BoxGeometry 默认中心在 (0,0,0)
    // 我们需要调整位置使其匹配 Bedrock 的 origin 定义
    const geometry = new THREE.BoxGeometry(
      size[0] + inflate * 2,
      size[1] + inflate * 2,
      size[2] + inflate * 2
    )

    // UV 映射
    if (cubeData.uv) {
      this.applyBedrockUV(geometry, cubeData.uv, size, mirror)
    }

    const mesh = new THREE.Mesh(geometry, material)
    mesh.castShadow = true
    mesh.receiveShadow = true
    mesh.name = 'Cube'

    // 计算 Cube 相对于 Bone 的位置
    // Bedrock Cube Origin 是绝对坐标
    // Bone Pivot 也是绝对坐标
    // Cube 在 Bone 局部空间的位置 = Cube Center - Bone Pivot

    // 处理 Cube 自身的旋转
    if (cubeData.rotation) {
      // 如果 Cube 没有定义自己的 pivot，则默认使用骨骼的 pivot (即相对于骨骼 pivot 偏移为 0)
      // If cube has no own pivot, use bone pivot (offset 0)
      const cubePivot = cubeData.pivot || bonePivot
      const pivotGroup = new THREE.Group()

      // PivotGroup 的位置是相对于 Bone Pivot 的
      pivotGroup.position.set(
        -(cubePivot[0] - bonePivot[0]),
        cubePivot[1] - bonePivot[1],
        cubePivot[2] - bonePivot[2]
      )

      pivotGroup.rotation.order = 'ZXY'
      pivotGroup.rotation.x = THREE.MathUtils.degToRad(-cubeData.rotation[0])
      pivotGroup.rotation.y = THREE.MathUtils.degToRad(-cubeData.rotation[1])
      pivotGroup.rotation.z = THREE.MathUtils.degToRad(cubeData.rotation[2])

      // Mesh 在 PivotGroup 内的位置
      // Mesh Center - Cube Pivot
      mesh.position.set(
        -(origin[0] + size[0] / 2 - cubePivot[0]),
        origin[1] + size[1] / 2 - cubePivot[1],
        origin[2] + size[2] / 2 - cubePivot[2]
      )

      pivotGroup.add(mesh)
      boneGroup.add(pivotGroup)
    } else {
      // 无旋转，直接挂在 Bone Group 下
      // Mesh Center - Bone Pivot
      mesh.position.set(
        -(origin[0] + size[0] / 2 - bonePivot[0]),
        origin[1] + size[1] / 2 - bonePivot[1],
        origin[2] + size[2] / 2 - bonePivot[2]
      )
      boneGroup.add(mesh)
    }
  }

  private applyBedrockUV(
    geometry: THREE.BoxGeometry,
    uvData: any,
    size: number[],
    mirror: boolean = false
  ) {
    const uvAttribute = geometry.attributes.uv
    const textureWidth = this.textureWidth
    const textureHeight = this.textureHeight

    // 基岩版 Box UV 布局:
    // 东 (+x), 西 (-x), 上 (+y), 下 (-y), 南 (+z), 北 (-z)
    // 0,    1,    2,  3,    4,     5

    // 辅助函数：设置面的 UV
    // u, v: 纹理起始坐标 (像素)
    // w, h: 纹理宽高 (像素)
    // faceIndex: 面索引 (0-5)
    const setFaceUV = (faceIndex: number, u: number, v: number, w: number, h: number) => {
      // 归一化 UV
      let u0 = u / textureWidth
      let u1 = (u + w) / textureWidth

      let v0 = (textureHeight - v - h) / textureHeight // 底部 (UV 中 Y 轴是反向的)
      let v1 = (textureHeight - v) / textureHeight // 顶部

      if (mirror) {
        // 镜像翻转 X
        ;[u0, u1] = [u1, u0]
      }

      // Three.js BoxGeometry UV 顺序:
      // 0: 左上 (0, 1)
      // 1: 右上 (1, 1)
      // 2: 左下 (0, 0)
      // 3: 右下 (1, 0)

      // BoxGeometry 面顺序:
      // +x, -x, +y, -y, +z, -z
      // 右, 左, 上, 下, 前, 后
      // 基岩版映射需要与此对齐

      // BufferGeometry from BoxGeometry 是非索引的 (24 个顶点)
      // 每个面 4 个顶点
      // 顶点顺序: 0: 左上, 1: 右上, 2: 左下, 3: 右下 (标准矩形)

      const offset = faceIndex * 4

      // 设置 UV 坐标
      uvAttribute.setXY(offset + 0, u0, v1) // 左上
      uvAttribute.setXY(offset + 1, u1, v1) // 右上
      uvAttribute.setXY(offset + 2, u0, v0) // 左下
      uvAttribute.setXY(offset + 3, u1, v0)
    }

    if (Array.isArray(uvData)) {
      // Box UV (标准基岩版)
      // [u, v] 原点
      const u = uvData[0]
      const v = uvData[1]

      // 尺寸
      const w = Math.ceil(size[0])
      const h = Math.ceil(size[1])
      const d = Math.ceil(size[2])

      // 基于基岩版规范的映射
      // 上 (Up): 2
      // 下 (Down): 3
      // 前 (North/South): 5 或 4
      // 右 (West): 1
      // 左 (East): 0
      // 后: 4 或 5

      // Three.js 面索引:
      // 0: 右 (+x)
      // 1: 左 (-x)
      // 2: 上 (+y)
      // 3: 下 (-y)
      // 4: 前 (+z)
      // 5: 后 (-z)

      // 基岩版布局:
      // 上: [u+d, v, w, d]
      // 下: [u+d+w, v, w, d]
      // 前: [u+d, v+d, w, h]
      // 后: [u+d+w+d, v+d, w, h]
      // 右: [u, v+d, d, h]
      // 左: [u+d+w, v+d, d, h]

      // 映射 Three.js 面索引到基岩版分片
      // 0 (右 +x) -> 基岩版 West (纹理左侧?) 不，基岩版 West 是 -x。
      // 假设标准映射：
      // 基岩版 北 = -z, 南 = +z, 西 = -x, 东 = +x

      // 如果 mirror 为 false:
      // 面 0 (右, +x) = 基岩版 南 (4) ? 不。
      // 复制旧版加载器逻辑:
      // setFaceUV(2, u + d, v, w, d) // 上 (Top)
      // setFaceUV(3, u + d + w, v, w, d) // 下 (Bottom)
      // setFaceUV(1, u, v + d, d, h) // 西 (Left, -x) -> Three.js Face 1
      // setFaceUV(5, u + d, v + d, w, h) // 北 (Front, -z) -> Three.js Face 5 (Back)
      // setFaceUV(0, u + d + w, v + d, d, h) // 东 (Right, +x) -> Three.js Face 0
      // setFaceUV(4, u + d + w + d, v + d, w, h) // 南 (Back, +z) -> Three.js Face 4 (Front)

      // 注意：Three.js BoxGeometry 面索引:
      // 0: +x (右)
      // 1: -x (左)
      // 2: +y (上)
      // 3: -y (Bottom)
      // 4: +z (Front)
      // 5: -z (Back)

      setFaceUV(2, u + d, v, w, d) // Top
      setFaceUV(3, u + d + w, v, w, d) // Bottom
      setFaceUV(1, u, v + d, d, h) // West -> Three.js Face 1 (-X)
      setFaceUV(5, u + d, v + d, w, h) // North -> Three.js Face 5 (-Z)
      setFaceUV(0, u + d + w, v + d, d, h) // East -> Three.js Face 0 (+X)
      setFaceUV(4, u + d + w + d, v + d, w, h) // South -> Three.js Face 4 (+Z)
    } else {
      // Per-face UV
      // Object: { up: { uv: [u, v], uv_size: [w, h] }, ... }
      const map: Record<string, number> = {
        east: 0,
        west: 1,
        up: 2,
        down: 3,
        south: 4,
        north: 5
      }

      for (const [faceName, faceData] of Object.entries(uvData) as [string, any][]) {
        const faceIndex = map[faceName]
        if (faceIndex === undefined) continue

        const u = faceData.uv[0]
        const v = faceData.uv[1]
        const w = faceData.uv_size[0]
        const h = faceData.uv_size[1]

        setFaceUV(faceIndex, u, v, w, h)
      }
    }

    uvAttribute.needsUpdate = true
  }
}
