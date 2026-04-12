/**
 * useTasks.ts
 * 待办任务管理：获取/删除
 */
import { shallowRef, type Ref } from 'vue'
import { API_BASE } from '@/config'
import { fetchWithTimeout } from './useDashboard'
import type { Task, Agent, OpenConfirmFn } from './types'


interface UseTasksOptions {
  activeAgent: Ref<Agent | null>
  openConfirm: OpenConfirmFn
}

const fetchTasksState = {
  isLoading: false,
  lastRequestId: null as symbol | null
}

const deleteTaskState = { isLoading: false }

export function useTasks({ activeAgent, openConfirm }: UseTasksOptions) {
  const tasks = shallowRef<Task[]>([])

  const fetchTasks = async (): Promise<void> => {
    if (fetchTasksState.isLoading) return
    fetchTasksState.isLoading = true
    const currentRequestId = Symbol('fetchTasks')
    fetchTasksState.lastRequestId = currentRequestId

    try {
      let url = `${API_BASE}/maintenance/tasks`

      if (activeAgent.value) url += `?agent_id=${activeAgent.value.id}`
      const res = await fetchWithTimeout(url, {}, 5000)
      const rawTasks = (await res.json()) as Task[]

      if (rawTasks.length < 100) {
        tasks.value = rawTasks.map((t) => Object.freeze(t))
        fetchTasksState.isLoading = false
        return
      }

      const processedTasks: Task[] = []
      const batchSize = 20

      const processBatch = (startIndex: number): void => {
        if (fetchTasksState.lastRequestId !== currentRequestId) {
          fetchTasksState.isLoading = false
          return
        }
        const endIndex = Math.min(startIndex + batchSize, rawTasks.length)
        for (let i = startIndex; i < endIndex; i++) {
          processedTasks.push(Object.freeze(rawTasks[i]))
        }
        tasks.value = [...processedTasks]
        if (endIndex < rawTasks.length) {
          setTimeout(() => processBatch(endIndex), 16)
        } else {
          fetchTasksState.isLoading = false
        }
      }
      processBatch(0)
    } catch (e) {
      console.error(e)
      fetchTasksState.isLoading = false
    }
  }

  const deleteTask = async (taskId: string | number): Promise<void> => {
    if (!taskId || deleteTaskState.isLoading) {
      if (!taskId) window.$notify('无效的任务ID', 'error')
      return
    }
    try {
      await openConfirm('提示', '确定删除此任务？', { type: 'warning' })
      deleteTaskState.isLoading = true
      const res = await fetchWithTimeout(`${API_BASE}/maintenance/tasks/${taskId}`, { method: 'DELETE' }, 5000)

      if (res.ok) {
        await fetchTasks()
        window.$notify('已删除', 'success')
      } else {
        const err = (await res.json()) as { message?: string }
        window.$notify(err.message ?? '操作失败', 'error')
      }
    } catch (e) {
      if ((e as Error).message !== 'User cancelled') {
        console.error(e)
        window.$notify('系统错误: ' + ((e as Error).message ?? '未知错误'), 'error')
      }
    } finally {
      deleteTaskState.isLoading = false
    }
  }

  return { tasks, fetchTasks, deleteTask }
}
