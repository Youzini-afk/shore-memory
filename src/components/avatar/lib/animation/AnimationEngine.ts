import * as THREE from 'three'
import { IAnimationData, IKeyframe } from './AnimationTypes'
import { RetargetingManager } from '../retargeting/RetargetingManager'
import { molang, molangContext } from '../Molang'

class AnimationState {
  data: IAnimationData
  time: number = 0
  weight: number = 0
  targetWeight: number = 0
  fadeSpeed: number = 0
  blendWeight: number = 1.0
  loop: boolean = true
  speed: number = 1.0

  constructor(data: IAnimationData) {
    this.data = data
    this.loop = data.loop
  }

  update(dt: number) {
    if (this.weight !== this.targetWeight) {
      const delta = this.fadeSpeed * dt
      if (this.weight < this.targetWeight) {
        this.weight = Math.min(this.targetWeight, this.weight + delta)
      } else {
        this.weight = Math.max(this.targetWeight, this.weight - delta)
      }
    }

    this.time += dt * this.speed

    if (this.loop && this.data.length > 0) {
      this.time = this.time % this.data.length
    } else if (!this.loop && this.time > this.data.length) {
      this.time = this.data.length
    }
  }
}

export class AnimationEngine {
  private activeStates: AnimationState[] = []
  private retargetingManager: RetargetingManager
  public lockRootPosition: boolean = false

  constructor(retargetingManager: RetargetingManager) {
    this.retargetingManager = retargetingManager
  }

  play(anim: IAnimationData, fadeTime: number = 0.2, loop: boolean = true, weight: number = 1.0) {
    let state = this.activeStates.find((s) => s.data.name === anim.name)

    if (!state) {
      state = new AnimationState(anim)
      this.activeStates.push(state)
    }

    state.loop = loop
    state.targetWeight = weight

    if (fadeTime > 0) {
      state.fadeSpeed = 1.0 / fadeTime
    } else {
      state.weight = weight
      state.fadeSpeed = 0
    }
  }

  setBlendWeight(animName: string, weight: number) {
    const state = this.activeStates.find((s) => s.data.name === animName)
    if (state) {
      state.blendWeight = weight
    }
  }

  stop(animName?: string, fadeTime: number = 0.2) {
    if (animName) {
      const state = this.activeStates.find((s) => s.data.name === animName)
      if (state) {
        state.targetWeight = 0.0
        if (fadeTime > 0) {
          state.fadeSpeed = 1.0 / fadeTime
        } else {
          state.weight = 0.0
        }
      }
    } else {
      for (const state of this.activeStates) {
        state.targetWeight = 0.0
        if (fadeTime > 0) {
          state.fadeSpeed = 1.0 / fadeTime
        } else {
          state.weight = 0.0
        }
      }
    }
  }

  update(dt: number) {
    if (this.activeStates.length === 0) return

    for (let i = this.activeStates.length - 1; i >= 0; i--) {
      const state = this.activeStates[i]
      state.update(dt)

      if (state.weight <= 0.0001 && state.targetWeight <= 0.0001) {
        this.activeStates.splice(i, 1)
      }
    }

    if (this.activeStates.length === 0) return

    this.retargetingManager.reset()

    molangContext.query.life_time += dt

    const affectedBones = new Set<string>()
    for (const state of this.activeStates) {
      Object.keys(state.data.bones).forEach((b) => affectedBones.add(b))
    }

    this.applyBlendedAnimation(affectedBones)
  }

  private applyBlendedAnimation(bones: Set<string>) {
    for (const boneName of bones) {
      let totalWeight = 0

      const finalPos = new THREE.Vector3()
      const finalScale = new THREE.Vector3()

      // 旋转增量累加器（欧拉角，弧度）
      const rotDelta = new THREE.Vector3(0, 0, 0)

      let hasPos = false
      let hasScale = false
      let hasRot = false

      // 获取初始旋转（直接使用缓存的欧拉角，避免四元数转换带来的角度歧义）
      const initialEuler = this.retargetingManager.getInitialEuler(boneName)

      const boneObj = this.retargetingManager.getBone(boneName)
      const restPos = boneObj ? boneObj.position.clone() : new THREE.Vector3()
      const restScale = boneObj ? boneObj.scale.clone() : new THREE.Vector3(1, 1, 1)

      for (const state of this.activeStates) {
        const effectiveWeight = state.weight * state.blendWeight
        if (effectiveWeight <= 0.0001) continue

        const tracks = state.data.bones[boneName]
        if (!tracks) continue

        molangContext.query.anim_time = state.time

        // 1. 旋转（动画旋转是相对于初始姿势的增量）
        if (tracks.rotation) {
          const val = this.evaluateTrack(tracks.rotation, state.time)
          if (val) {
            // 基岩版旋转与 Three.js 坐标系转换
            // X 轴取反，Y 轴取反，Z 轴不变
            rotDelta.x += THREE.MathUtils.degToRad(-val[0]) * effectiveWeight
            rotDelta.y += THREE.MathUtils.degToRad(-val[1]) * effectiveWeight
            rotDelta.z += THREE.MathUtils.degToRad(val[2]) * effectiveWeight
            hasRot = true
          }
        }

        // 2. 位移
        if (tracks.position) {
          const val = this.evaluateTrack(tracks.position, state.time)
          if (val) {
            finalPos.addScaledVector(restPos, effectiveWeight)
            finalPos.addScaledVector(new THREE.Vector3(-val[0], val[1], val[2]), effectiveWeight)
            hasPos = true
          }
        }

        // 3. 缩放
        if (tracks.scale) {
          const val = this.evaluateTrack(tracks.scale, state.time)
          if (val) {
            finalScale.addScaledVector(new THREE.Vector3(val[0], val[1], val[2]), effectiveWeight)
            hasScale = true
          }
        }

        totalWeight += effectiveWeight
      }

      // 如果总权重小于 1.0，则与休息姿势混合
      if (totalWeight < 0.999) {
        const restWeight = 1.0 - totalWeight

        // 位移混合
        finalPos.addScaledVector(restPos, restWeight)
        hasPos = true

        // 缩放混合
        finalScale.addScaledVector(restScale, restWeight)
        hasScale = true

        totalWeight = 1.0
      }

      if (totalWeight > 0) {
        // 应用旋转：最终旋转 = 初始旋转 + 动画增量
        if (hasRot) {
          const resultEuler = new THREE.Euler(
            initialEuler.x + rotDelta.x,
            initialEuler.y + rotDelta.y,
            initialEuler.z + rotDelta.z,
            'ZXY'
          )
          this.retargetingManager.applyRotation(boneName, resultEuler)
        }

        // 应用位移
        if (hasPos) {
          if (Math.abs(totalWeight - 1.0) > 0.01) {
            finalPos.divideScalar(totalWeight)
          }

          if (this.lockRootPosition && boneName === 'Root') {
            finalPos.x = 0
            finalPos.z = 0
          }

          this.retargetingManager.applyPosition(boneName, finalPos)
        }

        // 应用缩放
        if (hasScale) {
          if (Math.abs(totalWeight - 1.0) > 0.01) {
            finalScale.divideScalar(totalWeight)
          }
          this.retargetingManager.applyScale(boneName, finalScale)
        }
      }
    }
  }

  private evaluateTrack(keyframes: IKeyframe[], time: number): [number, number, number] | null {
    if (keyframes.length === 0) return null

    if (time <= keyframes[0].time) return this.resolveValue(keyframes[0].value)
    if (time >= keyframes[keyframes.length - 1].time)
      return this.resolveValue(keyframes[keyframes.length - 1].value)

    const nextIdx = keyframes.findIndex((k) => k.time > time)
    const prev = keyframes[nextIdx - 1]
    const next = keyframes[nextIdx]

    const range = next.time - prev.time
    const t = range > 0 ? (time - prev.time) / range : 0

    const v1 = this.resolveValue(prev.value)
    const v2 = this.resolveValue(next.value)

    if (prev.lerpMode === 'catmullrom') {
      const prevPrev = keyframes[nextIdx - 2] || prev
      const nextNext = keyframes[nextIdx + 1] || next

      const v0 = this.resolveValue(prevPrev.value)
      const v3 = this.resolveValue(nextNext.value)

      return [
        this.catmullRom(v0[0], v1[0], v2[0], v3[0], t),
        this.catmullRom(v0[1], v1[1], v2[1], v3[1], t),
        this.catmullRom(v0[2], v1[2], v2[2], v3[2], t)
      ]
    }

    return [v1[0] + (v2[0] - v1[0]) * t, v1[1] + (v2[1] - v1[1]) * t, v1[2] + (v2[2] - v1[2]) * t]
  }

  private catmullRom(p0: number, p1: number, p2: number, p3: number, t: number): number {
    const v0 = (p2 - p0) * 0.5
    const v1 = (p3 - p1) * 0.5
    const t2 = t * t
    const t3 = t * t2
    return (2 * p1 - 2 * p2 + v0 + v1) * t3 + (-3 * p1 + 3 * p2 - 2 * v0 - v1) * t2 + v0 * t + p1
  }

  private resolveValue(val: any): [number, number, number] {
    if (Array.isArray(val)) {
      return [
        typeof val[0] === 'string' ? molang.eval(val[0]) : val[0],
        typeof val[1] === 'string' ? molang.eval(val[1]) : val[1],
        typeof val[2] === 'string' ? molang.eval(val[2]) : val[2]
      ]
    } else if (typeof val === 'string') {
      const v = molang.eval(val)
      return [v, v, v]
    }
    return [val, val, val]
  }
}
