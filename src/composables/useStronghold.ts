import { ref, type Ref } from 'vue'
import { API_BASE } from '../config'

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
      const res = await fetch(`${API_BASE}/stronghold/facilities`)
      if (!res.ok) throw new Error('获取设施失败')
      facilities.value = await res.json()

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
      // 若未提供 facilityId，则获取所有设施的房间（需确认后端 API 行为）
      // API 支持通过 facility_id 参数筛选
      const url = facilityId
        ? `${API_BASE}/stronghold/rooms?facility_id=${facilityId}`
        : `${API_BASE}/stronghold/rooms`

      const res = await fetch(url)
      if (!res.ok) throw new Error('获取房间失败')
      rooms.value = await res.json()

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
      const res = await fetch(
        `${API_BASE}/stronghold/facilities?name=${encodeURIComponent(name)}&description=${encodeURIComponent(description)}&icon=${encodeURIComponent(icon || '')}`,
        {
          method: 'POST'
        }
      )
      if (!res.ok) throw new Error('创建设施失败')
      await fetchFacilities()
    } catch (err: any) {
      error.value = err.message
      throw err
    }
  }

  // 创建房间
  const createRoom = async (facilityId: string, name: string, description: string) => {
    try {
      const res = await fetch(
        `${API_BASE}/stronghold/rooms?facility_id=${facilityId}&name=${encodeURIComponent(name)}&description=${encodeURIComponent(description)}`,
        {
          method: 'POST'
        }
      )
      if (!res.ok) throw new Error('创建房间失败')
      await fetchRooms(facilityId)
    } catch (err: any) {
      error.value = err.message
      throw err
    }
  }

  // 获取管家配置
  const fetchButler = async () => {
    try {
      const res = await fetch(`${API_BASE}/stronghold/butler`)
      if (!res.ok) throw new Error('Failed to fetch butler config')
      butlerConfig.value = await res.json()
    } catch (err: any) {
      console.error('Failed to fetch butler config:', err)
      // 非关键错误，不设置全局错误状态
    }
  }

  // 获取所有智能体状态
  const agentsStatus = ref<any[]>([])
  const fetchAgentsStatus = async () => {
    try {
      const res = await fetch(`${API_BASE}/stronghold/agents/status`)
      if (!res.ok) throw new Error('Failed to fetch agents status')
      agentsStatus.value = await res.json()
    } catch (err: any) {
      console.error('Failed to fetch agents status:', err)
    }
  }

  // 呼叫管家
  const callButler = async (query: string) => {
    try {
      const res = await fetch(`${API_BASE}/stronghold/butler/call`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          agent_id: 'user',
          query: query
        })
      })
      if (!res.ok) throw new Error('呼叫管家失败')
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
