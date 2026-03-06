import { API_BASE } from '../config'

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
  const response = await fetch(url)
  if (!response.ok) {
    throw new Error(`Failed to fetch assets: ${response.statusText}`)
  }
  return await response.json()
}
