from fastapi import APIRouter, Body

from core.nit_manager import get_nit_manager

router = APIRouter(prefix="/api/nit", tags=["nit"])


@router.get("/settings")
async def get_nit_settings():
    """获取所有 NIT 调度设置"""
    return get_nit_manager().get_all_settings()


@router.post("/settings/category")
async def set_nit_category(
    category: str = Body(..., embed=True), enabled: bool = Body(..., embed=True)
):
    """设置分类开关 (Level 1)"""
    get_nit_manager().set_category_status(category, enabled)
    return {
        "status": "success",
        "message": f"Category {category} set to {enabled}. Restart required for some changes.",
    }


@router.post("/settings/plugin")
async def set_nit_plugin(
    plugin_name: str = Body(..., embed=True), enabled: bool = Body(..., embed=True)
):
    """设置插件开关 (Level 2)"""
    get_nit_manager().set_plugin_status(plugin_name, enabled)
    return {
        "status": "success",
        "message": f"Plugin {plugin_name} set to {enabled}. Restart required for some changes.",
    }
