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

  // Fetch facilities
  const fetchFacilities = async () => {
    loading.value = true
    try {
      const res = await fetch(`${API_BASE}/stronghold/facilities`)
      if (!res.ok) throw new Error('Failed to fetch facilities')
      facilities.value = await res.json()

      // Select first facility if none selected
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

  // Fetch rooms for a facility
  const fetchRooms = async (facilityId?: string) => {
    loading.value = true
    try {
      // If facilityId is not provided, fetch all or handle error?
      // API supports optional facility_id
      const url = facilityId
        ? `${API_BASE}/stronghold/rooms?facility_id=${facilityId}`
        : `${API_BASE}/stronghold/rooms`

      const res = await fetch(url)
      if (!res.ok) throw new Error('Failed to fetch rooms')
      rooms.value = await res.json()

      // If we switched facility, maybe auto-select first room?
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

  // Select a facility
  const selectFacility = async (facility: Facility) => {
    currentFacility.value = facility
    await fetchRooms(facility.id)
  }

  // Select a room
  const selectRoom = (room: Room) => {
    currentRoom.value = room
  }

  // Create Facility
  const createFacility = async (name: string, description: string, icon?: string) => {
    try {
      const res = await fetch(
        `${API_BASE}/stronghold/facilities?name=${encodeURIComponent(name)}&description=${encodeURIComponent(description)}&icon=${encodeURIComponent(icon || '')}`,
        {
          method: 'POST'
        }
      )
      if (!res.ok) throw new Error('Failed to create facility')
      await fetchFacilities()
    } catch (err: any) {
      error.value = err.message
      throw err
    }
  }

  // Create Room
  const createRoom = async (facilityId: string, name: string, description: string) => {
    try {
      const res = await fetch(
        `${API_BASE}/stronghold/rooms?facility_id=${facilityId}&name=${encodeURIComponent(name)}&description=${encodeURIComponent(description)}`,
        {
          method: 'POST'
        }
      )
      if (!res.ok) throw new Error('Failed to create room')
      await fetchRooms(facilityId)
    } catch (err: any) {
      error.value = err.message
      throw err
    }
  }

  // Fetch Butler Config
  const fetchButler = async () => {
    try {
      const res = await fetch(`${API_BASE}/stronghold/butler`)
      if (!res.ok) throw new Error('Failed to fetch butler config')
      butlerConfig.value = await res.json()
    } catch (err: any) {
      console.error('Failed to fetch butler config:', err)
      // Non-critical error, don't set global error state
    }
  }

  // Fetch All Agents Status
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

  // Call Butler
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
      if (!res.ok) throw new Error('Failed to call butler')
      // Maybe refresh room state or history after call
      if (currentRoom.value) {
        await fetchRooms(currentRoom.value.facility_id)
      }
      await fetchAgentsStatus()
    } catch (err: any) {
      console.error('Failed to call butler:', err)
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
