/**
 * injectionKeys.ts
 * Dashboard provide/inject 的键定义
 */
import type { InjectionKey } from 'vue'

// 每个 composable 的返回值类型通过 ReturnType<typeof useXxx> 来推断
// 这里只定义 Symbol keys，实际类型由各 composable 导出
export const DASHBOARD_KEY = Symbol('dashboard') as InjectionKey<any>
export const AGENT_CONFIG_KEY = Symbol('agentConfig') as InjectionKey<any>
export const DASHBOARD_DATA_KEY = Symbol('dashboardData') as InjectionKey<any>
export const LOGS_KEY = Symbol('logs') as InjectionKey<any>
export const MEMORIES_KEY = Symbol('memories') as InjectionKey<any>
export const TASKS_KEY = Symbol('tasks') as InjectionKey<any>
export const MODEL_CONFIG_KEY = Symbol('modelConfig') as InjectionKey<any>
