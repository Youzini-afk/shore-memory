import { API_BASE } from '../config'
import { fetchWithTimeout } from '@/composables/dashboard/useDashboard'

export interface Asset {
  asset_id: string
  type: string
  source: string
  display_name: string
  path: string
  version?: string
  description?: string
  tags?: string[]
}

export const fetchAssets = async (type?: string): Promise<Asset[]> => {
  const url = type ? `${API_BASE}/assets/?type=${type}` : `${API_BASE}/assets/`
  const response = await fetchWithTimeout(url)
  return await response.json()
}
