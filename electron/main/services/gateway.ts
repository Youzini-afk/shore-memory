/**
 * Gateway Service — 已嵌入 Python 后端
 *
 * Gateway 已从独立的 Go 进程迁移到 Python 后端内嵌的 WebSocket 端点 (/ws/gateway)。
 * 此文件保留最小化的兼容接口，不再启动/停止任何子进程。
 */

import { logger } from '../utils/logger'

const logHistory: string[] = []
const MAX_LOGS = 1000

export function getGatewayLogs() {
  return [...logHistory]
}

/**
 * startGateway — 现在是空操作。
 * Gateway 已嵌入 Python 后端，随后端一起启动，无需单独管理。
 */
export async function startGateway() {
  logger.info('Gateway', 'Gateway 已嵌入 Python 后端，无需单独启动。')
  logHistory.push('[Info] Gateway 已嵌入 Python 后端')
}

/**
 * stopGateway — 现在是空操作。
 * Gateway 随后端进程一起停止。
 */
export function stopGateway(): Promise<void> {
  logger.info('Gateway', 'Gateway 随后端一起停止（无需单独操作）。')
  return Promise.resolve()
}
