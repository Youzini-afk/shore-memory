<template>
  <div ref="container" class="bedrock-avatar-container relative group">
    <div ref="canvasContainer" class="canvas-container w-full h-full"></div>

    <!-- 加载遮罩 -->
    <div
      v-if="loading"
      class="absolute inset-0 flex flex-col items-center justify-center bg-moe-pink/5 backdrop-blur-sm z-10"
    >
      <div class="animate-bounce mb-2">
        <PixelIcon name="loader" size="md" animation="spin" class="text-moe-pink" />
      </div>
      <div
        class="pixel-font text-xs text-moe-pink font-bold bg-white/80 px-3 py-1 pixel-border-sm-moe"
      >
        正在召唤中...
      </div>
    </div>

    <!-- 错误遮罩 -->
    <div
      v-if="errorMsg"
      class="absolute inset-0 flex items-center justify-center bg-red-500/10 backdrop-blur-md z-20 p-4"
    >
      <div
        class="bg-white/90 p-4 pixel-border-sm-dark text-red-500 text-xs font-bold pixel-font text-center max-w-full break-words shadow-lg"
      >
        <div class="mb-2 text-2xl">😵</div>
        {{ errorMsg }}
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, ref, shallowRef, watch } from 'vue'
import * as THREE from 'three'
import { OrbitControls } from 'three/addons/controls/OrbitControls.js'
import PixelIcon from '../ui/PixelIcon.vue'
import { AvatarRenderer } from './lib/AvatarRenderer'
import { StandardBedrockProvider } from './lib/adapter/StandardBedrockProvider'
import { PeroSecureProvider } from './lib/adapter/PeroSecureProvider'
import { PeroContainerProvider } from './lib/adapter/PeroContainerProvider'
import { AnimationEngine } from './lib/animation/AnimationEngine'
import { AnimationLibrary } from './lib/animation/AnimationLibrary'
import { AnimationControllerSystem } from './lib/animation/AnimationController'
import { molangContext } from './lib/Molang'
import { IModelAdapter } from './lib/adapter/IModelAdapter'
import { IModelProvider } from './lib/adapter/IModelProvider'
import { RetargetingManager } from './lib/retargeting/RetargetingManager'
import { StandardBones } from './lib/retargeting/RetargetingConfig'
import { FeatureButton, IAvatarManifest } from './lib/adapter/IAvatarManifest'
import { ManifestBasedAdapter } from './lib/adapter/ManifestBasedAdapter'
import { ManifestLoader } from './lib/adapter/ManifestLoader'
import { initAssetUrlCache } from '../../utils/assetUrl'

const props = defineProps<{
  isDragging?: boolean
  manifestPath?: string
  manifest?: IAvatarManifest
}>()

const emit = defineEmits(['pet', 'hover-start', 'hover-end'])

const container = ref<HTMLElement | null>(null)
const canvasContainer = ref<HTMLElement | null>(null)
const loading = ref(true)
const errorMsg = ref('')
const animList = ref<string[]>([])
const selectedAnim = ref('')

let dragInfluence = 0 // 0 = 正常, 1 = 完全拖拽效果

// 动态部件状态（基于适配器的功能按钮生成）
const clothingState = ref<Record<string, boolean>>({})
// 动态功能按钮列表（供 UI 使用）
const featureButtons = ref<FeatureButton[]>([])
// 表情的派生状态
const isShy = ref(false)
let currentAdapter: IModelAdapter | null = null

/**
 * 根据适配器的功能按钮初始化部件状态
 */
const initFeatureState = (buttons: FeatureButton[]) => {
  const state: Record<string, boolean> = {}
  buttons.forEach((btn) => {
    state[btn.id] = btn.defaultValue ?? true
  })
  clothingState.value = state
  featureButtons.value = buttons
}

const updateClothing = () => {
  if (!characterModel) return

  // 计算害羞状态：如果裙子被脱掉，她会变害羞
  isShy.value = !clothingState.value.dress || !clothingState.value.underwear

  // 委托给适配器处理所有部件可见性逻辑
  if (currentAdapter) {
    currentAdapter.applyClothingState(characterModel, clothingState.value)
  }
}

watch(
  clothingState,
  () => {
    updateClothing()
  },
  { deep: true }
)

watch(
  () => props.manifestPath,
  async (newPath) => {
    if (newPath) {
      loading.value = true
      errorMsg.value = ''
      try {
        if (newPath.endsWith('.pero')) {
          // .pero 容器格式处理
          // 构造一个指向该容器的临时 Manifest
          const manifest: IAvatarManifest = {
            metadata: {
              name: newPath.split('/').pop()?.replace('.pero', '') || 'Unknown',
              version: '1.0.0'
            },
            resources: {
              model: newPath,
              texture: newPath,
              animations: []
            },
            featureButtons: [],
            parts: [],
            retargetingMap: { mapping: {} }
          }
          await loadAvatar(manifest)
        } else {
          // 标准 JSON Manifest
          const manifest = await ManifestLoader.fromJson(newPath)
          await loadAvatar(manifest)
        }
      } catch (e) {
        console.error('Failed to load new manifest path:', e)
        errorMsg.value = `加载模型失败: ${e}`
      } finally {
        loading.value = false
      }
    }
  }
)

// 暴露给父组件的方法
defineExpose({
  playAnimation: (name: string) => {
    const anim = animationLibrary.get(name)
    if (anim) {
      animationEngine.play(anim, 0.2, true)
    }
  },
  resetAnimation: () => {
    // 重置为空闲或控制器的逻辑
    if (lastLoadedConfig) {
      loadControllers(lastLoadedConfig)
    }
  },
  // 暴露状态给父 UI
  clothingState,
  featureButtons,
  updateClothing,
  animList,
  setAnimation: (name: string) => {
    selectedAnim.value = name
  },
  setGlobalMouse: (x: number, y: number) => {
    if (!container.value) return
    const rect = container.value.getBoundingClientRect()
    const centerX = rect.left + rect.width / 2
    const centerY = rect.top + rect.height / 2

    const rawX = (x - centerX) / (rect.width / 2)
    const rawY = (y - centerY) / (rect.height / 2)

    // 允许稍宽的全局追踪范围？还是保持限制？
    mouseInputX = Math.max(-1, Math.min(1, rawX))
    mouseInputY = Math.max(-1, Math.min(1, rawY))

    // 使用原始值更新 Raycaster 的 NDC
    mouseNDC.set(rawX, -rawY)
  },
  setLipSync: (val: number) => {
    lipSyncTarget.value = Math.max(0, Math.min(1, val))
  }
})

// 头部追踪状态
let targetHeadX = 0
let targetHeadY = 0
let currentHeadX = 0
let currentHeadY = 0

// 射线检测 / 交互状态
let characterModel: THREE.Object3D | null = null
const raycaster = new THREE.Raycaster()
const mouseNDC = new THREE.Vector2(999, 999) // 默认在屏幕外
let isHovering = false
let isPetting = false
let currentSquint = 1.0
let initialEyelidScaleY = 1.0 // 睫毛骨骼初始 scale.y（不同模型不一样）
let eyelidInitialized = false
let initialEyebrowY = 0
let currentEyebrowOffset = 0
// 口型同步状态
const lipSyncTarget = ref(0)
const currentLipSync = ref(0)
let mouthBone: THREE.Object3D | null = null

// Three.js 对象
const scene = shallowRef<THREE.Scene | null>(null)
const camera = shallowRef<THREE.PerspectiveCamera | null>(null)
const renderer = shallowRef<THREE.WebGLRenderer | null>(null)
const controls = shallowRef<OrbitControls | null>(null)
// const loader = new BedrockLoader() // 移除旧的 Loader
const retargetingManager = new RetargetingManager()
const animationLibrary = new AnimationLibrary()
const animationEngine = new AnimationEngine(retargetingManager)
const controllerSystem = new AnimationControllerSystem(animationEngine, animationLibrary)

let lastLoadedConfig: any = null

async function loadControllers(config: any, provider?: IModelProvider) {
  controllerSystem.reset()

  // 1. 优先尝试从 Provider 加载所有控制器
  if (provider?.getAnimationControllers) {
    try {
      const controllers = await provider.getAnimationControllers()
      if (controllers.size > 0) {
        console.log(`[BedrockAvatar] 从 Provider 加载了 ${controllers.size} 个动画控制器`)
        controllerSystem.loadFromJson({
          format_version: '1.10.0',
          animation_controllers: Object.fromEntries(controllers)
        } as any)
      }
    } catch (e) {
      console.warn('[BedrockAvatar] 从 Provider 加载控制器失败:', e)
    }
  }

  // 2. 传统路径加载
  if (config.animation_controllers) {
    const paths = Array.isArray(config.animation_controllers)
      ? config.animation_controllers
      : [config.animation_controllers]
    for (const path of paths) {
      await controllerSystem.load(path)
    }
  }
}

watch(selectedAnim, (newVal) => {
  if (newVal === '__NONE__') {
    // 停止所有动画且不恢复控制器
    controllerSystem.reset()
    animationEngine.stop(undefined, 0) // 立即停止，不进行淡出
    // 确保重置骨骼到初始姿态
    retargetingManager.reset()
    // 重置程序化动画变量
    currentHeadX = 0
    currentHeadY = 0
    targetHeadX = 0
    targetHeadY = 0
    molangContext.query.head_x_rotation = 0
    molangContext.query.head_y_rotation = 0
    currentSquint = 1.0
    currentEyebrowOffset = 0
    currentLipSync.value = 0
  } else if (newVal) {
    // 调试模式：播放选中的动画，权重设为 1，淡入 0.2s
    // 为了清晰查看，可能希望停止控制器？暂时保持混合
    const anim = animationLibrary.get(newVal)
    if (anim) {
      // 停止所有其他动画以获得纯净的预览
      animationEngine.stop(undefined, 0.2)
      animationEngine.play(anim, 0.2, true)
    }
  } else {
    // 恢复控制器逻辑
    // 由于我们没有暂停控制器，它们可能还在运行，但被 stop() 影响了权重的动画需要恢复
    // 这是一个复杂点。简单的做法是重置控制器系统
    // 或者我们假设控制器会在 update 中自动恢复状态动画？
    // BedrockAnimationController.update 只处理转换和混合表达式。
    // 如果动画被外部停止了，Controller 并不知道。
    // 这是一个待优化点。目前暂且重置。
    controllerSystem.reset()
    // 重新加载控制器？不，reset 会清空控制器。我们需要 reload。
    // 实际上，我们应该只是重新加载模型时的逻辑。
    // 简单起见，如果取消选择，我们什么都不做，或者需要一种“恢复默认”的方法。
    if (lastLoadedConfig) {
      loadControllers(lastLoadedConfig, currentProvider)
    }
  }
})

let animationFrameId: number
let currentProvider: IModelProvider | undefined

onMounted(async () => {
  // [修复] 预热 appPath 缓存，确保 resolveAssetUrl 能将相对 assets/ 路径转为 asset:// 绝对路径
  await initAssetUrlCache()
  initThree()
  await loadDefaultManifest()
  animate()

  window.addEventListener('resize', onResize)
  window.addEventListener('mousemove', onMouseMove)
  window.addEventListener('mousedown', onMouseDown)
  window.addEventListener('mouseup', onMouseUp)
})

onUnmounted(() => {
  cancelAnimationFrame(animationFrameId)
  window.removeEventListener('resize', onResize)
  window.removeEventListener('mousemove', onMouseMove)
  window.removeEventListener('mousedown', onMouseDown)
  window.removeEventListener('mouseup', onMouseUp)

  // 清理
  if (renderer.value) {
    renderer.value.dispose()
  }
  animationEngine.stop()
})

function initThree() {
  if (!container.value || !canvasContainer.value) return

  // 清理现有的渲染器以避免重复的画布
  if (renderer.value) {
    renderer.value.dispose()
  }

  // 仅清除画布容器内容
  while (canvasContainer.value.firstChild) {
    canvasContainer.value.removeChild(canvasContainer.value.firstChild)
  }

  // 重置角色引用，因为我们要创建一个新场景
  characterModel = null

  // 1. 场景
  const s = new THREE.Scene()
  scene.value = s

  // 2. 相机
  // 使用较窄的 FOV 以获得 2D 外观 (30-45)
  const c = new THREE.PerspectiveCamera(
    40,
    container.value.clientWidth / container.value.clientHeight,
    0.1,
    1000
  )
  // 默认视图：高度 20，距离 70，目标 Y 21
  // 增加 Z 到 90 以缩小（使模型更小）
  c.position.set(0, 20, 90)
  camera.value = c

  // 3. 渲染器
  const r = new THREE.WebGLRenderer({ alpha: true, antialias: true })
  r.setSize(container.value.clientWidth, container.value.clientHeight)
  // 限制最大2倍像素比，平衡清晰度与性能
  r.setPixelRatio(Math.min(window.devicePixelRatio, 2))
  r.shadowMap.enabled = true
  r.shadowMap.type = THREE.PCFSoftShadowMap
  canvasContainer.value.appendChild(r.domElement)
  renderer.value = r

  // 4. 控制器（右键旋转）
  const ctrl = new OrbitControls(c, r.domElement)
  ctrl.target.set(0, 21, 0) // 观察胸部/颈部 (Y=21)
  ctrl.enableDamping = true
  ctrl.dampingFactor = 0.05
  ctrl.enableZoom = false // 禁用缩放（滚轮）

  // 追踪交互状态
  ctrl.addEventListener('start', () => {
    isInteracting = true
  })

  ctrl.addEventListener('end', () => {
    isInteracting = false
  })

  // 鼠标按钮配置
  ctrl.mouseButtons = {
    LEFT: null, // 禁用左键拖拽（保留给窗口拖拽）
    MIDDLE: THREE.MOUSE.DOLLY,
    RIGHT: THREE.MOUSE.ROTATE
  }
  controls.value = ctrl

  // 5. 逼真的灯光设置
  // 环境光（中等强度）
  const ambient = new THREE.AmbientLight(0xffffff, 0.6)
  s.add(ambient)

  // 半球光（自然天空/地面变化）
  const hemi = new THREE.HemisphereLight(0xddeeff, 0x202020, 0.5) // 天蓝色到深灰色
  s.add(hemi)

  // 主定向光（太阳）
  const dirLight = new THREE.DirectionalLight(0xffffff, 1.5)
  dirLight.position.set(20, 50, 30) // 更高的角度以获得更好的阴影
  dirLight.castShadow = true
  dirLight.shadow.mapSize.width = 2048
  dirLight.shadow.mapSize.height = 2048
  dirLight.shadow.bias = -0.0001
  dirLight.shadow.normalBias = 0.05 // 减少阴影伪影
  s.add(dirLight)

  // 补光灯（柔化刺眼的阴影）
  const fillLight = new THREE.DirectionalLight(0xffeedd, 0.5) // 暖色补光
  fillLight.position.set(-20, 20, 20)
  s.add(fillLight)

  // 轮廓光（背光用于分离）
  const rimLight = new THREE.SpotLight(0xffffff, 1.0)
  rimLight.position.set(0, 40, -30)
  rimLight.lookAt(0, 10, 0)
  s.add(rimLight)

  // 地面（阴影捕捉器 - 不可见但接收阴影）
  const groundGeo = new THREE.PlaneGeometry(100, 100)
  const groundMat = new THREE.ShadowMaterial({ opacity: 0.3 })
  const ground = new THREE.Mesh(groundGeo, groundMat)
  ground.rotation.x = -Math.PI / 2
  ground.position.y = 0
  ground.receiveShadow = true
  s.add(ground)
}

async function loadAvatar(manifest: IAvatarManifest) {
  if (!scene.value) return

  try {
    const resources = manifest.resources
    const config = {
      name: manifest.metadata.name,
      model: resources.model,
      texture: resources.texture,
      animation: resources.animations || [],
      animation_controllers: (manifest as any).animation_controllers
    }

    let provider: IModelProvider
    const boneFilterPatterns = manifest.boneFilterPatterns

    // 检测是否为 .pero 容器格式（tar 打包的文件夹）
    // 容器格式：model 和 texture 都指向同一个 .pero 文件
    const isContainerFormat =
      config.model.endsWith('.pero') &&
      (config.texture?.endsWith('.pero') || config.texture === config.model)

    if (isContainerFormat) {
      console.log(`使用容器加载器: ${manifest.metadata.name}`)
      provider = new PeroContainerProvider(config.model, boneFilterPatterns)
    } else if (config.model.endsWith('.pero')) {
      console.log(`使用安全模型加载器: ${manifest.metadata.name}`)
      provider = new PeroSecureProvider(config, boneFilterPatterns)
    } else {
      provider = new StandardBedrockProvider(config, boneFilterPatterns)
    }

    currentProvider = provider

    // 容器格式：从容器内读取 manifest 并合并配置
    let effectiveManifest = manifest
    if (isContainerFormat) {
      try {
        const containerManifest = await provider.getManifest()
        if (containerManifest && containerManifest.featureButtons) {
          // 合并容器内的 manifest 与传入的 manifest
          // 容器内的配置优先（featureButtons, parts, boneFilterPatterns 等）
          effectiveManifest = {
            ...manifest,
            ...containerManifest,
            metadata: {
              ...manifest.metadata,
              ...(containerManifest.metadata || {})
            },
            resources: {
              ...manifest.resources,
              ...(containerManifest.resources || {})
            },
            retargetingMap: containerManifest.retargetingMap || manifest.retargetingMap,
            featureButtons: containerManifest.featureButtons || [],
            parts: containerManifest.parts || [],
            boneFilterPatterns: containerManifest.boneFilterPatterns || manifest.boneFilterPatterns
          }
          console.log(
            `[容器] 从容器内加载 manifest 成功，包含 ${effectiveManifest.featureButtons?.length || 0} 个功能按钮`
          )
        }
      } catch (e) {
        console.warn('[容器] 从容器内加载 manifest 失败，使用默认配置:', e)
      }
    }

    const avatarRenderer = new AvatarRenderer()
    const rootGroup = await avatarRenderer.build(provider)

    if (characterModel && scene.value) {
      scene.value.remove(characterModel)
      characterModel = null
    }

    characterModel = rootGroup

    currentAdapter = new ManifestBasedAdapter(effectiveManifest)

    const retargetConfig = currentAdapter.getRetargetingConfig()
    retargetingManager.init(rootGroup, retargetConfig)

    if (currentAdapter.getFeatureButtons) {
      initFeatureState(currentAdapter.getFeatureButtons())
    }

    mouthBone = retargetingManager.getBone(StandardBones.Mouth) || null
    const eyeBrow = retargetingManager.getBone(StandardBones.EyeBrow)
    if (eyeBrow) {
      initialEyebrowY = eyeBrow.position.y
    }

    scene.value.add(rootGroup)

    animationLibrary.clear()
    const animations = await provider.getAnimations()
    animations.forEach((clip, name) => {
      animationLibrary.add(name, clip)
    })

    lastLoadedConfig = config
    await loadControllers(config)

    animList.value = animationLibrary.getNames().sort()

    if (controllerSystem.controllers.length === 0) {
      const idleAnim =
        animList.value.find((n) => n === 'idle') || animList.value.find((n) => n.includes('idle'))
      if (idleAnim) {
        const anim = animationLibrary.get(idleAnim)
        if (anim) animationEngine.play(anim, 0.2, true)
      }
    }

    setTimeout(() => {
      updateClothing()
    }, 100)

    loading.value = false
    console.log(`模型 ${manifest.metadata.name} 加载成功`)
  } catch (e: any) {
    console.error(`加载模型失败`, e)
    errorMsg.value = `加载模型失败: ${e.message || e}`
    loading.value = false
  }
}

async function loadDefaultManifest() {
  if (props.manifest) {
    await loadAvatar(props.manifest)
    return
  }

  if (props.manifestPath) {
    loading.value = true
    errorMsg.value = ''
    try {
      if (props.manifestPath.endsWith('.pero')) {
        const manifest: IAvatarManifest = {
          metadata: {
            name: props.manifestPath.split('/').pop()?.replace('.pero', '') || 'Unknown',
            version: '1.0.0'
          },
          resources: {
            model: props.manifestPath,
            texture: props.manifestPath,
            animations: []
          },
          featureButtons: [],
          parts: [],
          retargetingMap: { mapping: {} }
        }
        await loadAvatar(manifest)
      } else {
        const manifest = await ManifestLoader.fromJson(props.manifestPath)
        await loadAvatar(manifest)
      }
    } catch (e: any) {
      console.error('Failed to load initial manifest path:', e)
      errorMsg.value = `加载模型失败: ${e.message || e}`
    } finally {
      loading.value = false
    }
    return
  }

  const isElectron = (window as any).electron !== undefined
  const prefix = isElectron ? 'assets/' : '/assets/'
  const isDev = !!import.meta.env.DEV

  const containerPath = `${prefix}3d/Pero.pero`
  const manifestJsonPath = `${prefix}3d/Pero/manifest.json`

  // 开发模式：优先 manifest.json（散文件夹），容器作为后备
  // 生产模式：优先 .pero 容器（加密打包），manifest 作为后备
  const loadContainer = async () => {
    const defaultManifest: IAvatarManifest = {
      metadata: { name: 'Pero', version: '1.0.0' },
      resources: { model: containerPath, texture: containerPath, animations: [] },
      featureButtons: [],
      parts: [],
      retargetingMap: { mapping: {} }
    }
    await loadAvatar(defaultManifest)
  }

  const loadManifest = async () => {
    console.log('加载 Pero manifest.json...')
    const manifest = await ManifestLoader.fromJson(manifestJsonPath)
    await loadAvatar(manifest)
  }

  // 统一策略：优先 manifest.json（散目录），.pero 容器作为后备
  // 因为 Pero 模型当前只有散目录格式，没有 .pero 容器
  const [primary, fallback] = [loadManifest, loadContainer]

  try {
    await primary()
    return
  } catch (e) {
    console.warn('主路径加载失败，尝试备用路径:', e)
  }

  try {
    await fallback()
    return
  } catch (e2) {
    console.error('所有加载路径均失败:', e2)
    errorMsg.value = `加载模型失败: 无可用的模型文件`
    loading.value = false
  }
}

let isInteracting = false

let lastFrameTime = 0

function animate() {
  animationFrameId = requestAnimationFrame(animate)

  const now = performance.now() / 1000
  const dt = now - (lastFrameTime || now)
  lastFrameTime = now
  const safeDt = Math.min(dt, 0.1)

  // 如果没有交互，自动重置相机
  if (!isInteracting && controls.value && camera.value) {
    // 当前偏离目标的偏移量
    const currentOffset = new THREE.Vector3().copy(camera.value.position).sub(controls.value.target)
    const spherical = new THREE.Spherical().setFromVector3(currentOffset)

    // 默认方向（前视图）
    // 相对于目标 (0,21,0)，默认位置为 (0,20,70) -> 偏移 (0, -1, 70)
    // 我们希望重置旋转到此方向，但保持当前半径（缩放）。
    const defaultOffset = new THREE.Vector3(0, -1, 70)
    const defaultSpherical = new THREE.Spherical().setFromVector3(defaultOffset)

    // 插值角度 (Theta/Phi) 但保持半径
    // 处理 Theta 环绕以获得最短路径
    let diff = defaultSpherical.theta - spherical.theta
    if (diff > Math.PI) diff -= 2 * Math.PI
    else if (diff < -Math.PI) diff += 2 * Math.PI

    spherical.theta += diff * 0.05
    spherical.phi += (defaultSpherical.phi - spherical.phi) * 0.05

    // 设置回相机位置
    // 注意：'spherical' 中的半径已经是当前半径，保持不变。
    const newOffset = new THREE.Vector3().setFromSpherical(spherical)
    camera.value.position.copy(controls.value.target).add(newOffset)

    // 如果目标漂移，也重置目标到中心
    const defaultTarget = new THREE.Vector3(0, 21, 0)
    controls.value.target.lerp(defaultTarget, 0.05)
  }

  // 根据相机位置 + 鼠标输入计算目标头部旋转
  if (camera.value && scene.value && selectedAnim.value !== '__NONE__') {
    // 检查射线检测以进行悬停
    if (characterModel) {
      raycaster.setFromCamera(mouseNDC, camera.value)
      // 针对角色模型的递归检查
      const intersects = raycaster.intersectObject(characterModel, true)
      const wasHovering = isHovering
      isHovering = intersects.length > 0

      if (isHovering && !wasHovering) {
        emit('hover-start')
      } else if (!isHovering && wasHovering) {
        emit('hover-end')
      }
    }

    // --- 头部追踪逻辑 ---
    const headBone = retargetingManager.getBone(StandardBones.Head)
    // 如果未找到骨骼，则使用默认头部位置（近似高度）
    const headPos = headBone
      ? headBone.getWorldPosition(new THREE.Vector3())
      : new THREE.Vector3(0, 24, 0)
    const camPos = camera.value.position

    // 从头部到相机的向量
    const dx = camPos.x - headPos.x
    const dy = camPos.y - headPos.y
    const dz = camPos.z - headPos.z

    // 计算偏航角 (Y 轴旋转)
    let camYaw = Math.atan2(dx, dz) * (180 / Math.PI)

    // 计算俯仰角 (X 轴旋转)
    const hDist = Math.sqrt(dx * dx + dz * dz)
    // 修复：用户反馈垂直方向反了，去除负号修正
    let camPitch = Math.atan2(dy, hDist) * (180 / Math.PI)

    // 添加鼠标偏移
    const maxMouseAngle = 15
    const maxHeadAngle = 45

    // 应用悬停逻辑：如果悬停，取消鼠标影响
    const effectiveMouseX = isHovering ? 0 : mouseInputX
    const effectiveMouseY = isHovering ? 0 : mouseInputY

    // 结合相机角度和鼠标偏移
    // 修复：方向修正
    // Yaw (左右):
    // camYaw 计算出的是正向角度 (例如相机在右边，得到 +90 度)
    // 模型向右看需要 +Y 旋转 (Three.js 左手/右手系? 实际上 +Y 是左转，-Y 是右转)
    // 等等，如果相机在右边 (+X)，模型面朝 +Z。
    // 模型需要向左转 (Turn Left) 才能看到 +X 吗？
    // 面朝 +Z。左手边是 +X。
    // 所以 Turn Left (+Y Rotation) 是对的。
    // 所以 camYaw (正值) 直接用即可。
    // 之前是 -camYaw，所以反了。

    let totalYaw = camYaw + effectiveMouseX * maxMouseAngle

    // Pitch (上下):
    // camPitch 计算出的是负向角度 (相机在上方 -> 负值 -> 抬头)
    // Mouse Up -> effectiveMouseY > 0 -> 我们也需要负值 (抬头)
    // 所以 camPitch 保持原样，Mouse 需要反转
    let totalPitch = camPitch + effectiveMouseY * maxMouseAngle * -1

    // 限制到最大限制
    targetHeadY = Math.max(-maxHeadAngle, Math.min(maxHeadAngle, totalYaw))
    targetHeadX = Math.max(-maxHeadAngle, Math.min(maxHeadAngle, totalPitch))
  }

  // 更新头部追踪 (插值)
  // 平滑地将当前值插值向目标值
  if (selectedAnim.value !== '__NONE__') {
    const lerpFactor = 0.1
    currentHeadX += (targetHeadX - currentHeadX) * lerpFactor
    currentHeadY += (targetHeadY - currentHeadY) * lerpFactor

    // 修复：确保 Molang 变量被正确传递
    // query.head_x_rotation 通常对应头部上下 (Pitch)，单位是角度
    // query.head_y_rotation 通常对应头部左右 (Yaw)，单位是角度
    molangContext.query.head_x_rotation = currentHeadX
    molangContext.query.head_y_rotation = currentHeadY
  }

  // 确保 AnimationEngine 知道 Molang 环境已更新
  // (AnimationEngine 每一帧都会读取 molangContext.query)

  if (controls.value) controls.value.update()

  controllerSystem.update(safeDt)
  animationEngine.update(safeDt)

  // 更新 Molang 状态变量
  // 简化的移动检测逻辑
  // 实际上 Bedrock 模型应该在 controller 中检测 query.is_moving
  // 我们只需要确保 query.is_moving 被正确设置
  // 这里我们假设没有外部输入，所以默认不动。
  // 如果有键盘输入，应该在这里更新。
  // 暂时保留旧的硬编码逻辑是不太对的，因为 AnimationStateMachine 已经没了。
  // 我们直接设置 Molang 变量即可。

  // 应用程序化动画覆盖 (更新后)
  if (scene.value && selectedAnim.value !== '__NONE__') {
    // --- 拖拽/被拎起物理效果 ---
    // 平滑过渡拖拽影响 (0.0 到 1.0)
    const targetInfluence = props.isDragging ? 1.0 : 0.0
    // 使用存储在外部作用域或 ref 中的 'dragInfluence' (定义在下面)
    dragInfluence += (targetInfluence - dragInfluence) * 0.1

    if (dragInfluence > 0.01) {
      const time = Date.now() * 0.008
      const swingX = Math.sin(time) * 0.1 // 轻微摆动
      const swingZ = Math.cos(time * 0.8) * 0.05

      // 使用 RetargetingManager 获取骨骼，支持任何兼容的模型
      const body =
        retargetingManager.getBone(StandardBones.Body) || retargetingManager.getBone('AllBody')
      const upperBody = retargetingManager.getBone('UpperBody')

      const armL = retargetingManager.getBone(StandardBones.LeftArm)
      const armR = retargetingManager.getBone(StandardBones.RightArm)

      const legL = retargetingManager.getBone(StandardBones.LeftLeg)
      const legR = retargetingManager.getBone(StandardBones.RightLeg)

      const head = retargetingManager.getBone(StandardBones.Head)

      // 辅助函数：将当前旋转插值到目标旋转
      // 我们加上乘以 dragInfluence 的目标偏移量

      // 身体：轻微前倾（重力）并摆动
      if (body) {
        const targetRotX = THREE.MathUtils.degToRad(15) + swingX * 0.5
        const targetRotZ = swingZ
        body.rotation.x = THREE.MathUtils.lerp(body.rotation.x, targetRotX, dragInfluence)
        body.rotation.z = THREE.MathUtils.lerp(body.rotation.z, targetRotZ, dragInfluence)
      } else if (upperBody) {
        const targetRotX = THREE.MathUtils.degToRad(15) + swingX * 0.5
        const targetRotZ = swingZ
        upperBody.rotation.x = THREE.MathUtils.lerp(upperBody.rotation.x, targetRotX, dragInfluence)
        upperBody.rotation.z = THREE.MathUtils.lerp(upperBody.rotation.z, targetRotZ, dragInfluence)
      }

      // 手臂：松散下垂
      if (armL) {
        const targetRotZ = THREE.MathUtils.degToRad(20)
        const targetRotX = THREE.MathUtils.degToRad(10) + swingX
        armL.rotation.z = THREE.MathUtils.lerp(armL.rotation.z, targetRotZ, dragInfluence)
        armL.rotation.x = THREE.MathUtils.lerp(armL.rotation.x, targetRotX, dragInfluence)
      }
      if (armR) {
        const targetRotZ = THREE.MathUtils.degToRad(-20)
        const targetRotX = THREE.MathUtils.degToRad(10) + swingX
        armR.rotation.z = THREE.MathUtils.lerp(armR.rotation.z, targetRotZ, dragInfluence)
        armR.rotation.x = THREE.MathUtils.lerp(armR.rotation.x, targetRotX, dragInfluence)
      }

      // 腿部：垂直下垂
      if (legL) {
        const targetRotX = THREE.MathUtils.degToRad(15) + swingX * 1.5
        const targetRotZ = THREE.MathUtils.degToRad(5)
        legL.rotation.x = THREE.MathUtils.lerp(legL.rotation.x, targetRotX, dragInfluence)
        legL.rotation.z = THREE.MathUtils.lerp(legL.rotation.z, targetRotZ, dragInfluence)
      }
      if (legR) {
        const targetRotX = THREE.MathUtils.degToRad(15) + swingX * 1.5
        const targetRotZ = THREE.MathUtils.degToRad(-5)
        legR.rotation.x = THREE.MathUtils.lerp(legR.rotation.x, targetRotX, dragInfluence)
        legR.rotation.z = THREE.MathUtils.lerp(legR.rotation.z, targetRotZ, dragInfluence)
      }

      // 头部：向上看/环顾四周（试图看谁抓住了她）
      if (head) {
        const targetRotX = THREE.MathUtils.degToRad(-45)
        const targetRotZ = swingZ * 0.5

        // 随着拖拽影响增加，淡出头部追踪
        // 但这里我们是在动画管理器更新之上应用的。
        // 由于 AnimationManager 重置骨骼或应用动画，我们正在覆盖。

        // 为了正确混合，我们需要知道来自动画的“原始”旋转。
        // AnimationManager.update() 已经运行。所以 head.rotation 包含动画 + 头部追踪。

        head.rotation.x = THREE.MathUtils.lerp(head.rotation.x, targetRotX, dragInfluence)
        head.rotation.z = THREE.MathUtils.lerp(head.rotation.z, targetRotZ, dragInfluence)
      }
    }

    // --- 通用 LookAt (头部追踪) ---
    // 即使在非拖拽状态下，也要应用 LookAt
    // 只有当拖拽影响较小时才生效
    if (dragInfluence < 0.9) {
      const head = retargetingManager.getBone(StandardBones.Head)
      if (head) {
        // currentHeadX/Y 是角度 (Degree)
        // Bedrock 坐标系通常是 ZYX 顺序
        // Pitch (上下) -> X轴
        // Yaw (左右) -> Y轴
        // 叠加旋转
        const lookAtX = THREE.MathUtils.degToRad(currentHeadX)
        const lookAtY = THREE.MathUtils.degToRad(currentHeadY)

        // 我们创建一个只包含 LookAt 旋转的欧拉角
        const lookAtEuler = new THREE.Euler(lookAtX, lookAtY, 0, 'ZYX')
        const lookAtQuat = new THREE.Quaternion().setFromEuler(lookAtEuler)

        // 叠加到当前旋转
        // head.quaternion = head.quaternion * lookAtQuat (局部旋转)
        head.quaternion.multiply(lookAtQuat)
      }
    }

    const leftEyelid =
      retargetingManager.getBone('LeftEyelid') || retargetingManager.getBone('LeftEyelidBase')
    const rightEyelid =
      retargetingManager.getBone('RightEyelid') || retargetingManager.getBone('RightEyelidBase')
    const eyeBrow = retargetingManager.getBone('EyeBrow')

    // 首帧记录睫毛骨骼初始 scale.y（不同模型默认值不同）
    if (!eyelidInitialized && (leftEyelid || rightEyelid)) {
      initialEyelidScaleY = leftEyelid?.scale.y ?? rightEyelid?.scale.y ?? 1.0
      eyelidInitialized = true
    }

    // 目标缩放比例：1.0=正常, <1=眯眼, >1=睁大
    // 如果害羞，使用部分眯眼 (例如 0.8) 表现“害羞/尴尬”的样子
    // 如果拖拽中，睁大眼睛（惊讶）
    let targetSquint = isPetting ? 0.7 : isShy.value ? 0.85 : 1.0
    if (props.isDragging) targetSquint = 1.2

    currentSquint += (targetSquint - currentSquint) * 0.2

    if (leftEyelid) leftEyelid.scale.y = initialEyelidScaleY * currentSquint
    if (rightEyelid) rightEyelid.scale.y = initialEyelidScaleY * currentSquint

    // 眉毛动画 (抚摸时下拉)
    if (eyeBrow) {
      // 首帧记录眉毛骨骼真实初始 Y 位置
      if (initialEyebrowY === 0 && eyeBrow.position.y !== 0) {
        initialEyebrowY = eyeBrow.position.y
      }
      // 抚摸优先级高于害羞
      const targetOffset = isPetting ? -1.5 : isShy.value ? 0.5 : 0
      currentEyebrowOffset += (targetOffset - currentEyebrowOffset) * 0.2

      // 使用存储的初始 Y 以避免漂移
      eyeBrow.position.y = initialEyebrowY + currentEyebrowOffset
    }

    // 口型同步 (下巴开合)
    if (mouthBone) {
      // 平滑地将当前值插值向目标值
      currentLipSync.value += (lipSyncTarget.value - currentLipSync.value) * 0.3

      // 映射 0-1 到旋转角度 (例如 0 到 30 度)
      const maxOpenAngle = THREE.MathUtils.degToRad(30)
      mouthBone.rotation.x = currentLipSync.value * maxOpenAngle
    }
  }

  if (renderer.value && scene.value && camera.value) {
    renderer.value.render(scene.value, camera.value)
  }
}

function onResize() {
  if (!container.value || !camera.value || !renderer.value) return

  const width = container.value.clientWidth
  const height = container.value.clientHeight

  camera.value.aspect = width / height
  camera.value.updateProjectionMatrix()
  renderer.value.setSize(width, height)
  renderer.value.setPixelRatio(Math.min(window.devicePixelRatio, 2)) // 限制最大2倍以兼顾性能
}

function onMouseMove(event: MouseEvent) {
  if (!container.value) return

  const rect = container.value.getBoundingClientRect()
  const centerX = rect.left + rect.width / 2
  const centerY = rect.top + rect.height / 2

  // 计算相对于中心的鼠标位置 (-1 到 1)
  // 当鼠标在窗口外时，限制以避免极值
  const rawX = (event.clientX - centerX) / (rect.width / 2)
  const rawY = (event.clientY - centerY) / (rect.height / 2)

  const x = Math.max(-1, Math.min(1, rawX))
  const y = Math.max(-1, Math.min(1, rawY))

  // 更新动画循环的全局鼠标输入
  mouseInputX = x
  mouseInputY = y

  // 更新 Raycaster NDC (Y 相对于 Raycaster 的屏幕坐标是反转的)
  // rawX 是 -1(左) 到 1(右) -> 匹配 NDC X
  // rawY 是 -1(上) 到 1(下) -> NDC Y 需要 1(上) 到 -1(下) => -rawY
  mouseNDC.set(x, -y)
}

// 全局鼠标输入存储
let mouseInputX = 0
let mouseInputY = 0

function onMouseDown(event: MouseEvent) {
  if (event.button === 0) {
    // 左键

    // 立即检查点击相交以获得快速响应
    if (camera.value && characterModel && container.value) {
      // 确保 raycaster 使用来自事件的当前鼠标位置进行更新
      const rect = container.value.getBoundingClientRect()
      const x = ((event.clientX - rect.left) / rect.width) * 2 - 1
      const y = -((event.clientY - rect.top) / rect.height) * 2 + 1
      const clickNDC = new THREE.Vector2(x, y)

      raycaster.setFromCamera(clickNDC, camera.value)
      const intersects = raycaster.intersectObject(characterModel, true)

      if (intersects.length > 0) {
        const hit = intersects[0]
        // 向上遍历以查找骨骼名称
        let currentObj = hit.object
        let partName = ''

        for (let i = 0; i < 5; i++) {
          if (!currentObj) break
          if (
            currentObj.name &&
            (currentObj.name.includes('Head') ||
              currentObj.name.includes('Body') ||
              currentObj.name.includes('Arm') ||
              currentObj.name.includes('Leg') ||
              currentObj.name.includes('Chest') ||
              currentObj.name.includes('Waist') ||
              // 配饰与服装
              currentObj.name.includes('Hair') ||
              currentObj.name.includes('Hat') ||
              currentObj.name.includes('Ribbon') ||
              currentObj.name.includes('Face') ||
              currentObj.name.includes('Eye') ||
              currentObj.name.includes('Dress') ||
              currentObj.name.includes('Skirt') ||
              currentObj.name.includes('Cloth') ||
              currentObj.name.includes('Apron') ||
              currentObj.name.includes('Breast') ||
              currentObj.name.includes('Hand') ||
              currentObj.name.includes('Sleeve') ||
              currentObj.name.includes('Foot') ||
              currentObj.name.includes('Shoe') ||
              currentObj.name.includes('Boot') ||
              currentObj.name.includes('Sock'))
          ) {
            partName = currentObj.name
            break
          }
          if (currentObj.parent) {
            currentObj = currentObj.parent
          } else {
            break
          }
        }

        if (partName) {
          // 离散点击事件，触发不需要状态保持
          isPetting = true
          let type = 'body'

          if (
            partName.includes('Head') ||
            partName.includes('Hair') ||
            partName.includes('Hat') ||
            partName.includes('Ribbon') ||
            partName.includes('Face') ||
            partName.includes('Eye')
          ) {
            type = 'head'
          } else if (
            partName.includes('Arm') ||
            partName.includes('Hand') ||
            partName.includes('Sleeve')
          ) {
            type = 'arm'
          } else if (
            partName.includes('Leg') ||
            partName.includes('Foot') ||
            partName.includes('Shoe') ||
            partName.includes('Boot') ||
            partName.includes('Sock')
          ) {
            type = 'leg'
          } else if (
            partName.includes('Chest') ||
            partName.includes('Waist') ||
            partName.includes('Body') ||
            partName.includes('Dress') ||
            partName.includes('Skirt') ||
            partName.includes('Cloth') ||
            partName.includes('Apron') ||
            partName.includes('Breast')
          ) {
            type = 'body'
          }

          emit('pet', { type: type, rawPart: partName })
        }
      }
    }
  }
}

function onMouseUp(event: MouseEvent) {
  if (event.button === 0) {
    isPetting = false // 释放时重置抚摸状态
  }
}
</script>

<style scoped>
.bedrock-avatar-container {
  width: 100%;
  height: 100%;
  position: relative;
  overflow: hidden;
}

.canvas-container {
  width: 100%;
  height: 100%;
  position: absolute;
  top: 0;
  left: 0;
}

.debug-controls {
  position: absolute;
  top: 10px;
  right: 10px;
  background: rgba(0, 0, 0, 0.5);
  padding: 10px;
  border-radius: 4px;
  z-index: 10;
}

.debug-controls select {
  padding: 5px;
  border-radius: 4px;
  background: white;
  color: #333;
  border: none;
  cursor: pointer;
  font-size: 14px;
}

.clothing-controls {
  margin-top: 10px;
  display: flex;
  flex-direction: column;
  gap: 5px;
  color: white;
  font-size: 12px;
  background: rgba(0, 0, 0, 0.3);
  padding: 5px;
  border-radius: 4px;
}

.clothing-controls label {
  display: flex;
  align-items: center;
  gap: 5px;
  cursor: pointer;
}

.loading-overlay {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  color: white;
  font-family: sans-serif;
  background: rgba(0, 0, 0, 0.5);
  padding: 10px 20px;
  border-radius: 8px;
}

.error-overlay {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  color: white;
  font-family: sans-serif;
  background: rgba(255, 0, 0, 0.7);
  padding: 10px 20px;
  border-radius: 8px;
  max-width: 80%;
  word-wrap: break-word;
}
</style>
