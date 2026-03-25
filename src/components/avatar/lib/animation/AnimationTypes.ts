/**
 * 动画数据接口
 * 描述一段标准动画的数据结构
 */
export interface IAnimationData {
  name: string
  loop: boolean
  length: number
  bones: Record<string, IBoneTrack>
}

export interface IBoneTrack {
  rotation?: IKeyframe[]
  position?: IKeyframe[]
  scale?: IKeyframe[]
}

export interface IKeyframe {
  time: number
  value: [number, number, number] | number
  lerpMode?: 'linear' | 'catmullrom'
}
