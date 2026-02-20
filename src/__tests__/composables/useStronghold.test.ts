import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { useStronghold } from '@/composables/useStronghold'

// 模拟全局 fetch
const fetchMock = vi.fn()
vi.stubGlobal('fetch', fetchMock)

describe('useStronghold', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    // 默认模拟实现
    fetchMock.mockResolvedValue({
      ok: true,
      json: async () => []
    })
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('应该初始化为空状态', () => {
    const { facilities, rooms, currentRoom, currentFacility, loading, error } = useStronghold()
    expect(facilities.value).toEqual([])
    expect(rooms.value).toEqual([])
    expect(currentRoom.value).toBeNull()
    expect(currentFacility.value).toBeNull()
    expect(loading.value).toBe(false)
    expect(error.value).toBeNull()
  })

  it('fetchFacilities 应该成功获取设施并设置默认选中项', async () => {
    const mockFacilities = [
      { id: '1', name: 'Facility 1', description: 'Desc 1' },
      { id: '2', name: 'Facility 2', description: 'Desc 2' }
    ]
    const mockRooms = [{ id: 'r1', facility_id: '1', name: 'Room 1', description: 'Room Desc 1' }]

    // 模拟 fetch 响应
    fetchMock
      .mockResolvedValueOnce({
        ok: true,
        json: async () => mockFacilities
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => mockRooms
      })

    const { facilities, currentFacility, fetchFacilities, rooms, currentRoom } = useStronghold()

    await fetchFacilities()

    expect(facilities.value).toEqual(mockFacilities)
    // 应该默认选中第一个设施
    expect(currentFacility.value).toEqual(mockFacilities[0])

    // 应该自动获取选中设施的房间
    expect(fetchMock).toHaveBeenCalledTimes(2)
    // 第二次调用应该是获取房间
    expect(fetchMock).toHaveBeenLastCalledWith(
      expect.stringContaining('/stronghold/rooms?facility_id=1')
    )

    // 应该默认选中第一个房间
    expect(rooms.value).toEqual(mockRooms)
    expect(currentRoom.value).toEqual(mockRooms[0])
  })

  it('fetchFacilities 失败时应该设置错误信息', async () => {
    // Suppress console.error for this test
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {})

    fetchMock.mockResolvedValueOnce({
      ok: false
    })

    const { fetchFacilities, error, loading } = useStronghold()

    const promise = fetchFacilities()
    expect(loading.value).toBe(true)
    await promise

    expect(error.value).toBe('获取设施失败')
    expect(loading.value).toBe(false)
    expect(consoleSpy).toHaveBeenCalled()

    consoleSpy.mockRestore()
  })

  it('selectFacility 应该更新当前设施并获取房间', async () => {
    const { selectFacility, currentFacility, rooms, currentRoom } = useStronghold()
    const mockFacility = { id: '2', name: 'Facility 2', description: 'Desc 2' }
    const mockRooms = [{ id: 'r2', facility_id: '2', name: 'Room 2', description: 'Room Desc 2' }]

    // 重置模拟以确保状态干净
    fetchMock.mockReset()
    fetchMock.mockResolvedValue({
      ok: true,
      json: async () => mockRooms
    })

    await selectFacility(mockFacility)

    expect(currentFacility.value).toEqual(mockFacility)
    expect(rooms.value).toEqual(mockRooms)
    expect(currentRoom.value).toEqual(mockRooms[0])
    expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining('facility_id=2'))
  })

  it('selectRoom 应该更新当前房间', () => {
    const { selectRoom, currentRoom } = useStronghold()
    const mockRoom = { id: 'r3', facility_id: '1', name: 'Room 3', description: 'Desc 3' }

    selectRoom(mockRoom)
    expect(currentRoom.value).toEqual(mockRoom)
  })

  it('fetchRooms 失败时应该处理错误', async () => {
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
    fetchMock.mockResolvedValueOnce({ ok: false })

    const { fetchRooms, error, loading } = useStronghold()

    await fetchRooms('123')

    expect(error.value).toBe('获取房间失败')
    expect(loading.value).toBe(false)
    expect(consoleSpy).toHaveBeenCalled()
    consoleSpy.mockRestore()
  })

  it('如果没有设施，fetchFacilities 不应该尝试获取房间', async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => []
    })

    const { fetchFacilities, rooms, currentFacility } = useStronghold()

    await fetchFacilities()

    expect(currentFacility.value).toBeNull()
    expect(rooms.value).toEqual([])
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })
})
