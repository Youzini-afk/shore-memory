import { ref, type Ref } from 'vue'
import { API_BASE } from '../config'
import { fetchJson, fetchWithTimeout } from './dashboard/useDashboard'


interface Facility {
  id: string
  name: string
  description: string
  icon?: string
}

interface Room {
  id: string
  facility_id: string
  name: string
  description: string
}

export function useStronghold() {
  const facilities: Ref<Facility[]> = ref([])
  const rooms: Ref<Room[]> = ref([])
  const currentRoom: Ref<Room | null> = ref(null)
  const currentFacility: Ref<Facility | null> = ref(null)
  const butlerConfig: Ref<any> = ref(null)
  const loading: Ref<boolean> = ref(false)
  const error: Ref<string | null> = ref(null)

  // 获取设施
  const fetchFacilities = async () => {
    loading.value = true
    try {
      facilities.value = await fetchJson<Facility[]>(`${API_BASE}/stronghold/facilities`)

      // 如果未选择，则选择第一个设施
      if (!currentFacility.value && facilities.value.length > 0) {
        currentFacility.value = facilities.value[0]
        await fetchRooms(currentFacility.value.id)
      }
    } catch (err: any) {
      error.value = err.message
      console.error(err)
    } finally {
      loading.value = false
    }
  }

  // 获取设施的房间
  const fetchRooms = async (facilityId?: string) => {
    loading.value = true
    try {
      const url = facilityId
        ? `${API_BASE}/stronghold/rooms?facility_id=${facilityId}`
        : `${API_BASE}/stronghold/rooms`

      rooms.value = await fetchJson<Room[]>(url)

      // 切换设施后，默认选中第一个房间
      if (
        rooms.value.length > 0 &&
        (!currentRoom.value || currentRoom.value.facility_id !== facilityId)
      ) {
        currentRoom.value = rooms.value[0]
      } else if (rooms.value.length === 0) {
        currentRoom.value = null
      }
    } catch (err: any) {
      error.value = err.message
      console.error(err)
    } finally {
      loading.value = false
    }
  }

  // 选择设施
  const selectFacility = async (facility: Facility) => {
    currentFacility.value = facility
    await fetchRooms(facility.id)
  }

  // 选择房间
  const selectRoom = (room: Room) => {
    currentRoom.value = room
  }

  // 创建设施
  const createFacility = async (name: string, description: string, icon?: string) => {
    try {
      await fetchWithTimeout(
        `${API_BASE}/stronghold/facilities?name=${encodeURIComponent(name)}&description=${encodeURIComponent(description)}&icon=${encodeURIComponent(icon || '')}`,
        { method: 'POST', throwOnError: true }
      )
      await fetchFacilities()
    } catch (err: any) {
      error.value = err.message
      throw err
    }
  }

  // 创建房间
  const createRoom = async (facilityId: string, name: string, description: string) => {
    try {
      await fetchWithTimeout(
        `${API_BASE}/stronghold/rooms?facility_id=${facilityId}&name=${encodeURIComponent(name)}&description=${encodeURIComponent(description)}`,
        { method: 'POST', throwOnError: true }
      )
      await fetchRooms(facilityId)
    } catch (err: any) {
      error.value = err.message
      throw err
    }
  }

  // 获取管家配置
  const fetchButler = async () => {
    try {
      butlerConfig.value = await fetchJson(`${API_BASE}/stronghold/butler`)
    } catch (err: any) {
      console.error('获取管家配置失败:', err)
      // 非关键错误，不设置全局错误状态
    }
  }

  // 获取所有智能体状态
  const agentsStatus = ref<any[]>([])
  const fetchAgentsStatus = async () => {
    try {
      agentsStatus.value = await fetchJson(`${API_BASE}/stronghold/agents/status`)
    } catch (err: any) {
      console.error('获取智能体状态失败:', err)
    }
  }

  // 呼叫管家
  const callButler = async (query: string) => {
    try {
      await fetchWithTimeout(`${API_BASE}/stronghold/butler/call`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ agent_id: 'user', query }),
        throwOnError: true
      })
      // 呼叫后可能需要刷新房间状态或历史记录
      if (currentRoom.value) {
        await fetchRooms(currentRoom.value.facility_id)
      }
      await fetchAgentsStatus()
    } catch (err: any) {
      console.error('呼叫管家失败:', err)
      throw err
    }
  }

  return {
    facilities,
    rooms,
    currentRoom,
    currentFacility,
    butlerConfig,
    agentsStatus,
    loading,
    error,
    fetchFacilities,
    fetchRooms,
    selectFacility,
    selectRoom,
    createFacility,
    createRoom,
    fetchButler,
    fetchAgentsStatus,
    callButler
  }
}
