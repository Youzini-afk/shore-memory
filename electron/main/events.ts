import { EventEmitter } from 'events'

/**
 * 全局应用事件总线，用于协调主进程中的各个服务
 */
export const appEvents = new EventEmitter()
