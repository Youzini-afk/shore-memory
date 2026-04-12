from typing import List, Optional

from fastapi import APIRouter, HTTPException

from core.asset_registry import get_asset_registry

router = APIRouter(prefix="/api/assets", tags=["assets"])


@router.get("/", response_model=List[dict])
async def list_assets(type: Optional[str] = None):
    """
    获取资产列表
    :param type: 资产类型过滤 (plugin, model_3d, persona, etc.)
    """
    registry = get_asset_registry()
    if type:
        assets = registry.get_assets_by_type(type)
    else:
        assets = list(registry.assets.values())

    return [asset.to_dict() for asset in assets]


@router.get("/{asset_id}", response_model=dict)
async def get_asset(asset_id: str):
    """
    获取指定资产详情
    """
    registry = get_asset_registry()
    asset = registry.get_asset(asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    return asset.to_dict()


@router.post("/scan")
async def trigger_scan():
    """
    触发重新扫描
    """
    registry = get_asset_registry()
    registry.scan_all()
    return {"status": "ok", "count": len(registry.assets)}
