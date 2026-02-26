import { describe, it, expect, beforeEach } from 'vitest'
import { molang, molangContext } from '@/components/avatar/lib/Molang'

describe('Molang Parser', () => {
  beforeEach(() => {
    // 重置上下文
    molangContext.variable = new Proxy(
      {},
      {
        get: (target: any, prop: string) => (prop in target ? target[prop] : 0),
        set: (target: any, prop: string, value: any) => {
          target[prop] = value
          return true
        }
      }
    )
    molangContext.temp = new Proxy(
      {},
      {
        get: (target: any, prop: string) => (prop in target ? target[prop] : 0),
        set: (target: any, prop: string, value: any) => {
          target[prop] = value
          return true
        }
      }
    )
  })

  describe('Basic Evaluation', () => {
    it('应该能计算简单的数学表达式', () => {
      expect(molang.eval('1 + 1')).toBe(2)
      expect(molang.eval('2 * 3')).toBe(6)
      expect(molang.eval('10 / 2')).toBe(5)
      expect(molang.eval('5 - 2')).toBe(3)
    })

    it('应该能处理括号优先级', () => {
      expect(molang.eval('(1 + 2) * 3')).toBe(9)
      expect(molang.eval('1 + 2 * 3')).toBe(7)
    })
  })

  describe('Context Variables', () => {
    it('应该能读写变量 (variable/v)', () => {
      molang.eval('variable.test = 10')
      expect(molang.eval('variable.test')).toBe(10)
      expect(molang.eval('v.test')).toBe(10) // Alias check

      molang.eval('v.test2 = 20')
      expect(molang.eval('variable.test2')).toBe(20)
    })

    it('应该能读写临时变量 (temp/t)', () => {
      molang.eval('temp.foo = 5')
      expect(molang.eval('temp.foo')).toBe(5)
      expect(molang.eval('t.foo')).toBe(5)

      molang.eval('t.bar = 15')
      expect(molang.eval('temp.bar')).toBe(15)
    })

    it('应该能读取查询变量 (query/q)', () => {
      molangContext.query.life_time = 100
      expect(molang.eval('query.life_time')).toBe(100)
      expect(molang.eval('q.life_time')).toBe(100)
    })
  })

  describe('Math Functions', () => {
    it('应该支持基础三角函数', () => {
      // sin(90) = 1 (Molang uses degrees)
      expect(molang.eval('math.sin(90)')).toBeCloseTo(1)
      expect(molang.eval('Math.cos(0)')).toBeCloseTo(1)
    })

    it('应该支持 clamp', () => {
      expect(molang.eval('math.clamp(10, 0, 5)')).toBe(5)
      expect(molang.eval('math.clamp(-5, 0, 5)')).toBe(0)
      expect(molang.eval('math.clamp(3, 0, 5)')).toBe(3)
    })

    it('应该支持 lerp', () => {
      expect(molang.eval('math.lerp(0, 10, 0.5)')).toBe(5)
      expect(molang.eval('math.lerp(0, 10, 0)')).toBe(0)
      expect(molang.eval('math.lerp(0, 10, 1)')).toBe(10)
    })

    it('应该支持 lerprotate (角度插值)', () => {
      // 0 -> 360 is same as 0 -> 0
      expect(molang.eval('math.lerprotate(0, 360, 0.5)')).toBe(0)
      // 350 -> 10 (crosses 0, short path is +20 deg) -> 350 + 10 = 360/0
      // diff = 10 - 350 = -340 -> +360 = 20
      // 350 + 20 * 0.5 = 360 -> 0
      expect(molang.eval('math.lerprotate(350, 10, 0.5)') % 360).toBe(0)
    })

    it('应该支持 die_roll (随机骰子)', () => {
      // Mock Math.random for deterministic testing if needed,
      // but for now just check range
      const result = molang.eval('math.die_roll(1, 1, 6)')
      expect(result).toBeGreaterThanOrEqual(1)
      expect(result).toBeLessThanOrEqual(6)
    })
  })

  describe('Molang Quirks', () => {
    it('应该能处理分号分隔的多语句，并返回最后一个值', () => {
      expect(molang.eval('v.a=1; v.b=2; v.a+v.b')).toBe(3)
    })

    it('应该能处理 return 关键字', () => {
      expect(molang.eval('return 42')).toBe(42)
      expect(molang.eval('v.x=10; return v.x * 2')).toBe(20)
    })

    it('应该能处理异常并返回 0', () => {
      // Invalid syntax
      expect(molang.eval('1 +')).toBe(0)
      // Undefined function
      expect(molang.eval('math.nonexistent(1)')).toBe(0)
    })

    it('应该能处理空表达式', () => {
      expect(molang.eval('')).toBe(0)
      expect(molang.eval(null)).toBe(0)
    })
  })
})
