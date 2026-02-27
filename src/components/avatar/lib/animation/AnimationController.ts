import { AnimationEngine } from './AnimationEngine'
import { AnimationLibrary } from './AnimationLibrary'
import { molang } from '../Molang'

// Bedrock JSON 结构定义
interface IBedrockControllerJson {
  format_version: string
  animation_controllers: Record<string, IBedrockControllerDef>
}

interface IBedrockControllerDef {
  initial_state?: string
  states: Record<string, IBedrockStateDef>
}

interface IBedrockStateDef {
  animations?: (string | Record<string, string>)[]
  transitions?: Record<string, string>[]
  on_entry?: string[]
  on_exit?: string[]
  blend_transition?: number // 秒
}

// 运行时状态类
class ControllerState {
  name: string
  def: IBedrockStateDef

  constructor(name: string, def: IBedrockStateDef) {
    this.name = name
    this.def = def
  }
}

/**
 * Bedrock 动画控制器实例
 * 对应 animation_controllers 中的一个控制器条目
 */
export class BedrockAnimationController {
  name: string
  private states: Map<string, ControllerState> = new Map()
  private currentState: ControllerState | null = null
  private engine: AnimationEngine
  private library: AnimationLibrary
  private stateTime: number = 0

  // 当前状态播放的动画列表，用于退出时停止
  private activeAnimations: Set<string> = new Set()

  constructor(
    name: string,
    def: IBedrockControllerDef,
    engine: AnimationEngine,
    library: AnimationLibrary
  ) {
    this.name = name
    this.engine = engine
    this.library = library

    // 解析状态
    for (const [stateName, stateDef] of Object.entries(def.states)) {
      this.states.set(stateName, new ControllerState(stateName, stateDef))
    }

    // 设置初始状态
    if (def.initial_state && this.states.has(def.initial_state)) {
      this.enterState(def.initial_state)
    } else if (this.states.size > 0) {
      // 默认进入第一个定义的状态
      const firstState = this.states.keys().next().value
      if (firstState) this.enterState(firstState)
    }
  }

  update(dt: number) {
    if (!this.currentState) return

    this.stateTime += dt

    // 1. 检查状态转换
    if (this.currentState.def.transitions) {
      for (const trans of this.currentState.def.transitions) {
        // trans 是一个对象: { "目标状态": "条件表达式" }
        for (const [targetStateName, conditionExpr] of Object.entries(trans)) {
          // 评估 Molang 条件
          if (molang.eval(conditionExpr)) {
            this.enterState(targetStateName)
            return // 状态改变，本帧结束
          }
        }
      }
    }

    // 2. 更新当前状态下的动画 (混合逻辑)
    // 某些动画可能有条件表达式，需要动态开启/关闭
    if (this.currentState.def.animations) {
      for (const animEntry of this.currentState.def.animations) {
        if (typeof animEntry === 'string') {
          // 简单动画，已在 enterState 启动，无需每帧处理
          // 除非我们要支持自动重播非循环动画？通常由引擎处理循环 (Loop)
        } else {
          // 对象形式: { "动画名称": "混合表达式" }
          for (const [animName, blendExpr] of Object.entries(animEntry)) {
            const weight = molang.eval(blendExpr)
            const anim = this.library.get(animName)
            if (anim) {
              // 实时更新混合权重 (Blend Weight)，不影响淡入淡出 (Fade Weight)
              this.engine.setBlendWeight(animName, Math.max(0, weight))

              if (weight > 0) {
                // 确保动画在播放 (可能刚从 0 变大，或者还没开始)
                // 如果已经播放，play 会更新状态但不会重置时间
                // play() 方法如果找到现有状态，不会重置时间。
                // 但是，如果 activeAnimations 没追踪它，说明可能是第一次变为 > 0
                if (!this.activeAnimations.has(animName)) {
                  // 启动它。淡入时间为 0，因为我们希望立即响应表达式
                  this.engine.play(anim, 0, true, 1.0)
                  this.activeAnimations.add(animName)
                }
              }
            }
          }
        }
      }
    }
  }

  private enterState(stateName: string) {
    const nextState = this.states.get(stateName)
    if (!nextState) {
      console.warn(`[基岩版动画控制器] 未找到状态: ${stateName}`)
      return
    }

    // 执行当前状态的退出指令 (on_exit)
    if (this.currentState && this.currentState.def.on_exit) {
      this.currentState.def.on_exit.forEach((expr) => molang.eval(expr))
    }

    // 计算淡出时间
    // 基岩版默认混合时间是 0.25s，或者使用 blend_transition 属性
    let fadeTime = 0.2
    if (this.currentState && this.currentState.def.blend_transition !== undefined) {
      fadeTime = this.currentState.def.blend_transition
    }
    // 也可以读取目标状态的 blend_transition，通常是在源状态定义离开的混合时间，或者在 transition 中定义

    // 停止旧状态的动画
    // 注意：基岩版允许动画在状态间平滑过渡。如果新状态也播放同一个动画，不应该停止它。
    // 这里简化处理：
    // 1. 获取新状态将要播放的所有动画名称
    const nextAnimNames = new Set<string>()
    if (nextState.def.animations) {
      nextState.def.animations.forEach((entry) => {
        if (typeof entry === 'string') nextAnimNames.add(entry)
        else Object.keys(entry).forEach((k) => nextAnimNames.add(k))
      })
    }

    // 2. 停止当前正在播放、但新状态不需要的动画
    for (const animName of this.activeAnimations) {
      if (!nextAnimNames.has(animName)) {
        this.engine.stop(animName, fadeTime)
      }
    }

    // 清空当前列表，稍后填充新列表
    this.activeAnimations.clear()

    // 切换状态
    const prevStateName = this.currentState ? this.currentState.name : 'null'
    this.currentState = nextState
    this.stateTime = 0

    console.log(`[控制器: ${this.name}] 转换: ${prevStateName} -> ${stateName}`)

    // 执行新状态的进入指令 (on_entry)
    if (this.currentState.def.on_entry) {
      this.currentState.def.on_entry.forEach((expr) => molang.eval(expr))
    }

    // 播放新状态的动画
    if (this.currentState.def.animations) {
      for (const animEntry of this.currentState.def.animations) {
        if (typeof animEntry === 'string') {
          // 字符串：直接播放
          const anim = this.library.get(animEntry)
          if (anim) {
            // 假设默认循环
            this.engine.play(anim, fadeTime, true, 1.0)
            this.activeAnimations.add(animEntry)
          } else {
            // console.warn(`未找到动画: ${animEntry}`)
          }
        } else {
          // 对象：带条件的混合
          // { "动画名称": "表达式" }
          for (const [animName, expr] of Object.entries(animEntry)) {
            const weight = molang.eval(expr)
            const anim = this.library.get(animName)
            if (anim) {
              // 初始播放，设置基础权重为 1 (由淡入淡出控制)，混合权重为表达式值
              this.engine.play(anim, fadeTime, true, 1.0)
              this.engine.setBlendWeight(animName, Math.max(0, weight))
              this.activeAnimations.add(animName)
            }
          }
        }
      }
    }
  }

  getCurrentStateName(): string {
    return this.currentState ? this.currentState.name : ''
  }
}

/**
 * 动画控制器系统
 * 管理多个控制器并加载 JSON
 */
export class AnimationControllerSystem {
  controllers: BedrockAnimationController[] = []
  engine: AnimationEngine
  library: AnimationLibrary

  constructor(engine: AnimationEngine, library: AnimationLibrary) {
    this.engine = engine
    this.library = library
  }

  async load(url: string) {
    try {
      const response = await fetch(url)
      if (!response.ok) throw new Error(`无法加载控制器: ${url}`)

      const json = (await response.json()) as IBedrockControllerJson
      this.loadFromJson(json)
    } catch (e) {
      console.error(`从 ${url} 加载动画控制器出错:`, e)
    }
  }

  /**
   * 直接从 JSON 对象加载控制器
   */
  loadFromJson(json: IBedrockControllerJson) {
    if (json.animation_controllers) {
      for (const [name, def] of Object.entries(json.animation_controllers)) {
        const ctrl = new BedrockAnimationController(name, def, this.engine, this.library)
        this.controllers.push(ctrl)
      }
    }
  }

  update(dt: number) {
    for (const ctrl of this.controllers) {
      ctrl.update(dt)
    }
  }

  reset() {
    // 停止所有动画
    this.engine.stop()
    this.controllers = []
  }
}
