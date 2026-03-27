export const molangContext: any = {
  query: new Proxy(
    {
      anim_time: 0,
      life_time: 0,
      head_x_rotation: 0,
      head_y_rotation: 0,
      is_sneaking: 0,
      is_moving: 0,
      ground_speed: 0,
      yaw_speed: 0,
      is_on_ground: 1, // 默认为在地面上
      vertical_speed: 0,
      is_riding: 0,
      is_sprinting: 0,
      is_holding_right: 0,
      is_holding_left: 0
    },
    {
      get: (target: any, prop: string) => {
        return prop in target ? target[prop] : 0
      }
    }
  ),
  variable: new Proxy(
    {},
    {
      get: (target: any, prop: string) => {
        return prop in target ? target[prop] : 0
      },
      set: (target: any, prop: string, value: any) => {
        target[prop] = value
        return true
      }
    }
  ),
  temp: new Proxy(
    {},
    {
      get: (target: any, prop: string) => {
        return prop in target ? target[prop] : 0
      },
      set: (target: any, prop: string, value: any) => {
        target[prop] = value
        return true
      }
    }
  ),
  control: new Proxy(
    {},
    {
      get: (target: any, prop: string) => {
        return prop in target ? target[prop] : 0
      }
    }
  ),
  math: {
    sin: (deg: number) => Math.sin((deg * Math.PI) / 180),
    cos: (deg: number) => Math.cos((deg * Math.PI) / 180),
    tan: (deg: number) => Math.tan((deg * Math.PI) / 180),
    asin: (x: number) => (Math.asin(x) * 180) / Math.PI,
    acos: (x: number) => (Math.acos(x) * 180) / Math.PI,
    atan: (x: number) => (Math.atan(x) * 180) / Math.PI,
    atan2: (y: number, x: number) => (Math.atan2(y, x) * 180) / Math.PI,
    clamp: (val: number, min: number, max: number) => Math.min(Math.max(val, min), max),
    lerp: (a: number, b: number, t: number) => a + (b - a) * t,
    lerprotate: (a: number, b: number, t: number) => {
      // 角度的最短路径插值
      let diff = b - a
      while (diff > 180) diff -= 360
      while (diff < -180) diff += 360
      return a + diff * t
    },
    abs: Math.abs,
    min: Math.min,
    max: Math.max,
    pow: Math.pow,
    sqrt: Math.sqrt,
    round: Math.round,
    ceil: Math.ceil,
    floor: Math.floor,
    mod: (a: number, b: number) => a % b,
    random: (min: number, max: number) => Math.random() * (max - min) + min,
    die_roll: (num: number, low: number, high: number) => {
      let sum = 0
      for (let i = 0; i < num; i++) {
        sum += Math.floor(Math.random() * (high - low + 1)) + low
      }
      return sum
    },
    die_roll_integer: (num: number, low: number, high: number) => {
      let sum = 0
      for (let i = 0; i < num; i++) {
        sum += Math.floor(Math.random() * (high - low + 1)) + low
      }
      return sum
    }
  }
}

export class Molang {
  cache: Map<string, (...args: any[]) => any>

  constructor() {
    this.cache = new Map()
  }

  parse(expression: any) {
    if (typeof expression === 'number') return () => expression
    if (this.cache.has(expression)) return this.cache.get(expression)

    let jsExpr = expression

    // 处理 Bedrock Molang 的怪癖
    // 1. 隐式返回
    // 2. 允许 Snake_case 变量

    // 处理 'return' - 移除所有 return 关键字，因为我们将整个表达式作为返回值
    jsExpr = jsExpr.replace(/\breturn\s+/g, '')

    // 处理多语句
    if (jsExpr.includes(';')) {
      jsExpr = jsExpr
        .split(';')
        .filter((p: string) => p.trim() !== '')
        .join(',')
    }

    try {
      // 创建带有上下文别名的函数
      // 避免对 v., q. 等进行正则替换
      const funcBody = `
                const query = context.query;
                const q = context.query;
                const variable = context.variable;
                const v = context.variable;
                const V = context.variable; // 别名 V
                const temp = context.temp;
                const t = context.temp;
                const T = context.temp; // 别名 T
                const ctrl = context.control; // 别名 ctrl
                const c = context.control;
                const math = context.math;
                const Math = context.math; // 允许大写 Math
                const Q = context.query; // 别名 Q

                try { 
                    return ${jsExpr}; 
                } catch(e) { 
                    return 0; 
                }
            `

      const func = new Function('context', funcBody) as (...args: any[]) => any
      this.cache.set(expression, func)
      return func
    } catch (e) {
      // 只警告一次，然后缓存返回 0 的函数，避免每帧重复编译+报错
      console.warn(`编译 Molang 失败 (已静默): ${expression}`, e)
      const fallback = () => 0
      this.cache.set(expression, fallback)
      return fallback
    }
  }

  eval(expression: any) {
    if (typeof expression === 'number') return expression
    if (!expression) return 0
    const func = this.parse(expression)
    if (func) {
      return func(molangContext)
    }
    return 0
  }
}

export const molang = new Molang()
