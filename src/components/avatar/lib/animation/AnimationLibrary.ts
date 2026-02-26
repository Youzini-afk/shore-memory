import { IAnimationData, IKeyframe } from './AnimationTypes'

/**
 * 动画库
 * 用于存储和检索加载的动画数据
 */
export class AnimationLibrary {
  private animations: Map<string, IAnimationData> = new Map()

  /**
   * 添加动画数据
   * @param name 动画名称
   * @param data 原始动画数据
   */
  add(name: string, data: any) {
    if (data && typeof data === 'object' && !('name' in data)) {
      // 假设是原始 Bedrock 动画数据，需要解析
      this.animations.set(name, this.parseAnimation(name, data))
    } else {
      // 假设已经是 IAnimationData
      this.animations.set(name, data as IAnimationData)
    }
  }

  /**
   * 获取动画数据
   * @param name 动画名称
   */
  get(name: string): IAnimationData | undefined {
    return this.animations.get(name)
  }

  /**
   * 移除动画数据
   * @param name 动画名称
   */
  remove(name: string) {
    this.animations.delete(name)
  }

  /**
   * 获取所有动画名称
   */
  getNames(): string[] {
    return Array.from(this.animations.keys())
  }

  /**
   * 清空库
   */
  clear() {
    this.animations.clear()
  }

  /**
   * 从 URL 加载动画数据 (Bedrock 格式)
   * @param url 动画文件 URL
   */
  async loadFromUrl(url: string): Promise<void> {
    try {
      const response = await fetch(url)
      if (!response.ok) {
        console.warn(`Failed to load animation: ${url}`)
        return
      }
      const json = await response.json()
      const anims = json.animations
      if (anims) {
        for (const [name, data] of Object.entries(anims)) {
          this.add(name, data) // Use updated add method
        }
      }
    } catch (e) {
      console.error(`Error loading animation from ${url}:`, e)
    }
  }

  private parseAnimation(name: string, data: any): IAnimationData {
    const parsedBones: any = {}

    if (data.bones) {
      for (const [boneName, tracks] of Object.entries(data.bones) as [string, any][]) {
        parsedBones[boneName] = {}
        if (tracks.rotation) parsedBones[boneName].rotation = this.parseTrack(tracks.rotation)
        if (tracks.position) parsedBones[boneName].position = this.parseTrack(tracks.position)
        if (tracks.scale) parsedBones[boneName].scale = this.parseTrack(tracks.scale)
      }
    }

    return {
      name,
      loop: data.loop !== false,
      length: data.animation_length || 0,
      bones: parsedBones
    }
  }

  private parseTrack(trackData: any): IKeyframe[] {
    if (typeof trackData === 'string' || typeof trackData === 'number') {
      // 保留原始值，让 evaluateTrack 中的 resolveValue 处理 Molang 表达式
      const val = trackData
      return [{ time: 0, value: [val, val, val] }]
    }

    // Check if it's a vector [x, y, z]
    if (Array.isArray(trackData)) {
      // It could be a single keyframe value [x,y,z] at time 0,
      // OR it could be array of keyframes? No, bedrock spec says array is value.
      // But wait, parseTrack in old manager handles it as single keyframe.
      return [{ time: 0, value: trackData as [number, number, number] }]
    }

    if (typeof trackData === 'object') {
      const keyframes: IKeyframe[] = []
      for (const [timeStr, value] of Object.entries(trackData) as [string, any][]) {
        let vec = value
        let lerpMode: 'linear' | 'catmullrom' = 'linear'

        if (value && typeof value === 'object' && !Array.isArray(value)) {
          if (value.post) vec = value.post
          if (value.lerp_mode) lerpMode = value.lerp_mode
        }

        if (Array.isArray(vec)) {
          keyframes.push({
            time: parseFloat(timeStr),
            value: vec as [number, number, number],
            lerpMode: lerpMode
          })
        }
      }
      keyframes.sort((a, b) => a.time - b.time)
      return keyframes
    }
    return []
  }
}
